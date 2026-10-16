"""Uploading through the website, as a user would: choose the files, see the preview, check, analyse, open the new
dataset, and delete it. The upload is labelled as an upload on every page and in its report, never as Prayas data;
the dataset switcher and links keep the chosen dataset; the claims scan passes on every page.

Uses the SYNTHETIC demo files as the upload (their results equal the command-line demo build: see
tests/integration/test_uploads.py) and a small one-reading-per-line file with typed district and state.
"""

from __future__ import annotations

import pytest

from pipeline import synthetic, upload
from tests.support.appserver import REPO_ROOT, app_server, get_json
from tests.support.claims import forbidden_hits

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
PRAYAS_DATA = ["Electricity Supply Monitoring Initiative", "doi:10.7910", "DVN/CLLZZM", "CC0", "Harvard Dataverse",
               "Prayas (Energy Group) ESMI, Uttar Pradesh"]


@pytest.fixture(scope="module")
def base():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    if not (synthetic.OUT_DIR / synthetic.READINGS_FILE).exists():
        synthetic.generate()
    with app_server() as b:
        yield b


@pytest.fixture(scope="module")
def page(base):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1366, "height": 860})
        pg.set_default_timeout(60_000)
        yield pg
        browser.close()


def _upload_page_check(pg, where: str):
    text = pg.inner_text("body")
    assert not forbidden_hits(text), f"{where}: {forbidden_hits(text)}"


def _check_upload_page(pg, where: str):
    banner = pg.get_by_test_id("upload-banner")
    banner.wait_for()
    assert "Uploaded data — not verified by VoltProof" in banner.inner_text(), where
    text = pg.inner_text("body")
    assert not forbidden_hits(text), f"{where}: {forbidden_hits(text)}"
    leaked = [t for t in PRAYAS_DATA if t in text]
    assert not leaked, f"{where}: Prayas data attribution on an upload page: {leaked}"
    assert "UPLOADED DATA" in pg.inner_text("footer"), where


def test_upload_the_demo_files_through_the_website_and_use_the_new_dataset(page, base):
    pg = page
    pg.goto(base + "/upload")
    pg.get_by_test_id("upload-privacy").wait_for()
    assert "stays on this computer" in pg.get_by_test_id("upload-privacy").inner_text()
    _upload_page_check(pg, "upload page")
    pg.get_by_test_id("upload-readings").set_input_files(str(synthetic.OUT_DIR / synthetic.READINGS_FILE))
    pg.get_by_test_id("upload-locations").set_input_files(str(synthetic.OUT_DIR / synthetic.LOCATION_FILE))
    pg.get_by_test_id("upload-send").click()
    pg.get_by_test_id("upload-preview").wait_for()
    assert "ESMI layout" in pg.get_by_test_id("upload-preview").inner_text()
    pg.get_by_test_id("upload-check").click()
    pg.get_by_test_id("upload-summary").wait_for()
    summary = pg.get_by_test_id("upload-summary").inner_text()
    assert "14,759 lines" in summary and "20 monitor(s)" in summary and "2030-01-01 to 2030-01-31" in summary
    pg.get_by_test_id("upload-build").click()
    pg.get_by_test_id("upload-done").wait_for(timeout=180_000)
    done = pg.get_by_test_id("upload-done").inner_text()
    assert "20 monitor(s)" in done and "8,85,480 measured minutes" in done
    assert "0 different, 0 missing" in pg.get_by_test_id("upload-same-method").inner_text()
    _upload_page_check(pg, "upload done")

    pg.get_by_test_id("upload-open").click()
    pg.wait_for_url("**/?ds=VP_USER_*")
    ds = pg.url.split("ds=")[1]
    _check_upload_page(pg, "start page")
    assert pg.get_by_test_id("dataset-select").input_value() == ds
    # the guided demo on the upload: its window is the upload's month, so it lands on the designed shared event
    pg.get_by_test_id("guided-demo").click()
    pg.wait_for_url("**/location/**")
    assert f"ds={ds}" in pg.url
    _check_upload_page(pg, "month view")
    pg.get_by_test_id("demo-next-day").click()
    pg.wait_for_url("**/day/**")
    assert f"ds={ds}" in pg.url
    _check_upload_page(pg, "day view")
    pg.get_by_test_id("open-selected-event").click()
    pg.wait_for_url("**/event/**")
    assert f"ds={ds}" in pg.url
    _check_upload_page(pg, "event view")
    for path in ("/sources", "/methodology"):
        pg.goto(f"{base}{path}?ds={ds}")
        pg.get_by_role("heading", level=1).wait_for()
        _check_upload_page(pg, path)
    pg.goto(f"{base}/sources?ds={ds}")
    pg.get_by_role("heading", level=1).wait_for()
    assert "SHA-256 of the uploaded file" in pg.inner_text("body")

    # the report of an uploaded month says UPLOADED DATA and carries no Prayas data attribution
    rec = next(r for r in upload.list_uploads() if r["schema"] == ds)
    loc = get_json(base, f"/api/locations?ds={ds}")[0]
    pg.goto(f"{base}/location/{loc['location_id']}/2030-01?ds={ds}")
    _check_upload_page(pg, "month view (report)")
    pg.get_by_test_id("generate-report").click()
    link = pg.get_by_test_id("report-pdf")
    link.wait_for(timeout=120_000)
    href = link.get_attribute("href")
    assert href.startswith(f"/api/reports/VP-USER-{rec['id']}-")
    html = pg.request.get(base + href.replace(".pdf", ".html")).text()
    assert "UPLOADED DATA" in html and not [t for t in PRAYAS_DATA if t in html]

    # delete through the page: two clicks (Delete, then Yes), then the dataset is gone
    pg.goto(base + "/upload")
    pg.get_by_test_id(f"delete-{rec['id']}").click()
    pg.get_by_test_id("delete-yes").click()
    pg.get_by_test_id("delete-confirm").wait_for(state="detached")
    assert not (upload.UPLOAD_DIR / rec["id"]).exists()
    assert not upload.schema_exists(ds)


def test_a_one_reading_per_line_file_with_typed_locations(page, base, tmp_path):
    lines = ["meter,timestamp,volts"] + [f"Shop counter,2024-03-{d:02d} {h:02d}:{m:02d},{0 if h == 19 else 228}"
                                    for d in (13, 14) for h in range(24) for m in range(60)]
    f = tmp_path / "shop readings.csv"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pg = page
    pg.goto(base + "/upload")
    pg.get_by_test_id("upload-readings").set_input_files(str(f))
    pg.get_by_test_id("upload-send").click()
    pg.get_by_test_id("upload-mapping").wait_for()
    assert pg.get_by_test_id("map-time").input_value() == "1" and pg.get_by_test_id("map-voltage").input_value() == "2"
    assert pg.get_by_test_id("map-order").input_value() == "YMD"
    pg.get_by_test_id("upload-check").click()
    pg.get_by_test_id("question-typed_locations").wait_for()
    pg.get_by_test_id("question-clock_local").wait_for()   # one-reading-per-line files: are these local clock times?
    assert pg.get_by_test_id("upload-build").is_disabled()
    pg.get_by_label("Yes, local clock time").check()
    pg.get_by_label("District of Shop counter").fill("Pune")
    pg.get_by_label("State of Shop counter").fill("up")      # typed in short form: stored as Uttar Pradesh
    pg.get_by_test_id("upload-recheck").click()
    pg.wait_for_function("() => !document.querySelector('[data-testid=question-typed_locations]')")
    summary = pg.get_by_test_id("upload-summary").inner_text()
    assert "2,880 lines" in summary and "Uttar Pradesh" in summary
    assert "read as 13 March 2024" in pg.get_by_test_id("upload-reads-as").inner_text()   # the worked date example
    pg.get_by_test_id("upload-build").click()
    pg.get_by_test_id("upload-done").wait_for(timeout=180_000)
    assert "1 monitor(s)" in pg.get_by_test_id("upload-done").inner_text()
    pg.get_by_test_id("upload-open").click()
    pg.wait_for_url("**/?ds=VP_USER_*")
    ds = pg.url.split("ds=")[1]
    _check_upload_page(pg, "start page (long)")
    rec = next(r for r in upload.list_uploads() if r["schema"] == ds)
    upload.delete(rec["id"])


def test_wrong_files_get_a_plain_message_on_the_page(page, base, tmp_path):
    f = tmp_path / "us meter.csv"
    f.write_text("time,volts\n" + "\n".join(f"2024-03-13 {h:02d}:{m:02d},119" for h in range(5) for m in range(60))
                 + "\n", encoding="utf-8")
    pg = page
    pg.goto(base + "/upload")
    pg.get_by_test_id("upload-readings").set_input_files(str(f))
    pg.get_by_test_id("upload-send").click()
    pg.get_by_test_id("upload-mapping").wait_for()
    pg.get_by_test_id("map-single-name").fill("Kitchen")
    pg.get_by_test_id("upload-check").click()
    pg.get_by_test_id("upload-refusals").wait_for()
    assert "is 130 V or less" in pg.get_by_test_id("upload-refusals").inner_text()
    assert pg.get_by_test_id("upload-build").is_disabled()
    _upload_page_check(pg, "refused upload")
    pg.get_by_role("button", name="Cancel and delete").click()
    pg.wait_for_function("() => !document.querySelector('[data-testid=upload-refusals]')")
