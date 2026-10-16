"""The web API with several datasets: every request names its dataset with `ds` (checked against a whitelist),
answers never mix datasets (also under concurrent requests), uploads are labelled as uploads everywhere (no Prayas,
ESMI, DOI or CC0 text), and the Prayas data and the SYNTHETIC set answer exactly as before."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pipeline import synthetic, upload
from pipeline.db import DEMO_SCHEMA, connect, schema_dataset
from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER
from tests.support.appserver import app_server, get_json

pytestmark = pytest.mark.exasol
DATA_ATTRIBUTION = ["Electricity Supply Monitoring Initiative", "doi.org/10.7910", "DVN/CLLZZM", "CC0",
                    "Harvard Dataverse", "Prayas"]


def _upload(readings: Path, locations: Path) -> dict:
    rec = upload.new_upload()
    upload.receive_path(rec["id"], "readings", readings)
    upload.receive_path(rec["id"], "locations", locations)
    upload.preview(rec["id"])
    assert upload.validate(rec["id"])["ready_to_build"]
    return upload.build(rec["id"])


def _small_files(folder: Path, state: str, days: list[str]) -> tuple[Path, Path]:
    r, lo = folder / f"{state}.csv", folder / f"{state} locations.csv"
    with open(r, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(READINGS_HEADER)
        for name in ("Shop A", "Shop B"):
            for d in days:
                for h in range(24):
                    w.writerow([name, d, h] + (["0"] * 60 if h == 19 else ["231"] * 60))
    with open(lo, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(LOCATIONS_HEADER)
        for name in ("Shop A", "Shop B"):
            w.writerow([name, "", "", "Test District", state, "", ""])
    return r, lo


@pytest.fixture(scope="module")
def uploads(tmp_path_factory):
    folder = tmp_path_factory.mktemp("uploads")
    if not (synthetic.OUT_DIR / synthetic.READINGS_FILE).exists():
        synthetic.generate()
    demo = _upload(synthetic.OUT_DIR / synthetic.READINGS_FILE, synthetic.OUT_DIR / synthetic.LOCATION_FILE)
    # dates inside the period of Prayas's 2019 January-June file, whose known defect must not be shown here
    up = _upload(*_small_files(folder, "Uttar Pradesh", ["13-02-2019", "14-02-2019", "15-02-2019"]))
    other = _upload(*_small_files(folder, "Maharashtra", ["13-02-2019", "14-02-2019"]))
    yield {"demo": demo, "up": up, "other": other}
    for rec in (demo, up, other):
        if (upload.UPLOAD_DIR / rec["id"]).exists():
            upload.delete(rec["id"])


@pytest.fixture(scope="module")
def base(uploads):
    with app_server() as b:
        yield b


def _status(base: str, path: str, method: str = "GET", body: dict | None = None) -> int:
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_the_dataset_list_names_every_built_dataset_and_its_kind(base, uploads):
    items = {d["ds"]: d for d in get_json(base, "/api/datasets")}
    for key in ("demo", "up", "other"):
        rec = uploads[key]
        assert items[rec["schema"]]["kind"] == "upload"
        assert items[rec["schema"]]["sha256"] == rec["readings"]["sha256"]
    with connect() as c:
        if schema_dataset(c, DEMO_SCHEMA)["built"]:
            assert items[DEMO_SCHEMA]["kind"] == "synthetic"
    assert sum(1 for d in items.values() if d["default"]) == 1


def test_a_request_without_ds_answers_exactly_as_the_server_dataset(base):
    default = next(d["ds"] for d in get_json(base, "/api/datasets") if d["default"])
    for path in ["/api/meta", "/api/states", "/api/locations", "/api/demo"]:
        sep = "&" if "?" in path else "?"
        assert get_json(base, path) == get_json(base, f"{path}{sep}ds={default}")


def test_unknown_or_hostile_dataset_names_are_refused_before_any_query(base):
    for ds in ["VOLTPROOF2", "VP_USER_00000000", "EXA_STATISTICS", "SYS", "VOLTPROOF;DROP%20SCHEMA%20X",
               "%27%20OR%201=1--", "VP_BASECHECK", "VP_TEST_1", "x" * 41]:
        for path in ["/api/meta", "/api/locations", "/api/locations/1", "/api/demo",
                     "/api/locations/1/months/2018-07", "/api/events/1-201807251827"]:
            code = _status(base, f"{path}?ds={ds}")
            assert code in (404, 422), (path, ds, code)
        assert _status(base, f"/api/reports?ds={ds}", "POST", {"location_id": 1, "month": "2018-07"}) in (404, 422)


def test_uploads_are_labelled_as_uploads_and_never_as_prayas_data(base, uploads):
    rec = uploads["other"]
    m = get_json(base, f"/api/meta?ds={rec['schema']}")
    assert m["dataset_kind"] == "upload" and m["synthetic"] is False
    assert m["attribution"] == "UPLOADED DATA: not verified by VoltProof."
    assert rec["readings"]["name"] in m["citation"] and rec["readings"]["sha256"] in m["citation"]
    for field in ("citation", "attribution", "licence", "dataset_label"):
        for token in DATA_ATTRIBUTION:
            assert token not in m[field], (field, token)
    loc = get_json(base, f"/api/locations?ds={rec['schema']}")[0]
    month = get_json(base, f"/api/locations/{loc['location_id']}/months/2019-02?ds={rec['schema']}")
    assert month["data_warning"] is None  # Prayas's 2019 file defect never shown on an upload


def _report(base: str, rec: dict) -> dict:
    loc = get_json(base, f"/api/locations?ds={rec['schema']}")[0]
    month = get_json(base, f"/api/locations/{loc['location_id']}?ds={rec['schema']}")["months"][0]["month_key"]
    req = urllib.request.Request(f"{base}/api/reports?ds={rec['schema']}", method="POST",
                                 data=json.dumps({"location_id": loc["location_id"], "month": month}).encode(),
                                 headers={"Content-Type": "application/json"})
    links = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return {"links": links, "data": get_json(base, links["json_url"]),
            "html": urllib.request.urlopen(base + links["html_url"], timeout=60).read().decode("utf-8")}


def test_upload_reports_are_marked_kept_with_the_upload_and_use_the_right_grievance_text(base, uploads):
    other, up = _report(base, uploads["other"]), _report(base, uploads["up"])
    for r, rec in ((other, uploads["other"]), (up, uploads["up"])):
        rid = r["links"]["report_id"]
        assert rid.startswith(f"VP-USER-{rec['id']}-")
        assert (upload.UPLOAD_DIR / rec["id"] / "reports" / f"{rid}.pdf").exists()
        assert "UPLOADED DATA" in r["html"] and 'data-testid="upload-banner"' in r["html"]
        assert r["data"]["provenance"]["attribution"] == "UPLOADED DATA: not verified by VoltProof."
        for token in ["Electricity Supply Monitoring Initiative", "doi.org", "CC0", "Harvard Dataverse", "(ESMI)"]:
            assert token not in r["html"], token
        assert not any("ESMI, 2014-2019" in x for x in r["data"]["method"]["limitations"])
    assert other["data"]["redress"].startswith("A consumer can raise supply complaints with the distribution "
                                               "company. For the grievance procedure that applies in this state")
    assert "UPERC" not in other["data"]["redress"]
    assert "UPERC (Consumer Grievance Redressal Forum & Electricity Ombudsman) Regulations, 2003" in up["data"]["redress"]


def test_upload_reports_carry_a_diagonal_mark_and_cannot_load_anything_from_outside(base, uploads):
    r = _report(base, uploads["other"])
    html = r["html"]
    assert 'class="watermark"' in html and "UPLOADED DATA &mdash; NOT VERIFIED" in html
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    assert "uploaded data" in " ".join(r["data"]["method"]["limitations"]).lower()
    assert any("UPS, inverter or stabiliser" in x for x in r["data"]["method"]["limitations"])
    assert any("grouped by those entries" in x for x in r["data"]["method"]["limitations"])
    pdftotext = shutil.which("pdftotext") or (r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"
                                             if Path(r"C:\Program Files\Git\mingw64\bin\pdftotext.exe").exists() else None)
    if pdftotext:   # the mark and the footer are on every printed page
        pdf = upload.UPLOAD_DIR / uploads["other"]["id"] / "reports" / f"{r['links']['report_id']}.pdf"
        text = subprocess.run([pdftotext, "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
        pages = [p for p in text.split("\f") if p.strip()]
        assert len(pages) >= 2
        for i, p in enumerate(pages, start=1):
            assert "NOT VERIFIED" in p.upper().replace("—", " ") and "UPLOADED DATA" in p, f"page {i}"


def test_sample_files_can_be_downloaded_from_the_upload_page_and_are_invented(base):
    for which, name in (("readings", "voltage data 2030 Jan.csv"), ("locations", "location information.csv"),
                        ("long", "one reading per line.csv")):
        resp = urllib.request.urlopen(f"{base}/api/uploads/sample/{which}", timeout=60)
        body = resp.read().decode("utf-8")
        assert name in urllib.parse.unquote(resp.headers["content-disposition"]) and "SYNTHETIC" in body
    assert _status(base, "/api/uploads/sample/passwd") == 404
    assert _status(base, "/api/uploads/sample/..%2F..%2Fsecrets") in (404, 422)


def test_changing_requests_without_the_page_header_or_from_another_site_are_refused(base):
    assert _status(base, "/api/uploads", "POST") == 403
    req = urllib.request.Request(f"{base}/api/uploads", method="POST",
                                 headers={"X-VoltProof": "1", "Origin": "http://evil.example"})
    try:
        urllib.request.urlopen(req, timeout=30)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 403
    assert _status(base, "/api/uploads/bebad8f4", "DELETE") == 403
    assert _status(base, "/api/uploads/00000000/validate", "POST", {"mapping": {}}) == 403


def test_concurrent_requests_to_different_datasets_never_mix(base, uploads):
    expected = {}
    for key in ("demo", "up", "other"):
        schema = uploads[key]["schema"]
        expected[schema] = sorted((x["display_name"], x["state_name"]) for x in get_json(base, f"/api/locations?ds={schema}"))
    default = sorted((x["display_name"], x["state_name"]) for x in get_json(base, "/api/locations"))
    jobs = [s for _ in range(12) for s in [*expected, None]]

    def ask(schema):
        path = "/api/locations" + (f"?ds={schema}" if schema else "")
        names = sorted((x["display_name"], x["state_name"]) for x in get_json(base, path))
        return schema, names == (expected[schema] if schema else default)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(ask, jobs))
    assert all(ok for _, ok in results), [s for s, ok in results if not ok]
    assert len({tuple(v) for v in expected.values()}) == 3  # the three uploads really differ


def test_a_deleted_upload_disappears_from_the_app(base, tmp_path):
    rec = _upload(*_small_files(tmp_path, "Kerala", ["13-03-2024", "14-03-2024"]))
    assert _status(base, f"/api/meta?ds={rec['schema']}") == 200
    report = _report(base, rec)["links"]
    upload.delete(rec["id"])
    import time
    time.sleep(6)  # the app re-reads the dataset list every 5 seconds
    assert _status(base, f"/api/meta?ds={rec['schema']}") == 404
    assert _status(base, report["pdf_url"]) == 404
    assert rec["schema"] not in {d["ds"] for d in get_json(base, "/api/datasets")}
