"""Evidence report for one location and month: one data dict -> sidecar JSON + HTML (Jinja2) -> PDF (Playwright).

The sidecar JSON is the single source of every number printed. The HTML marks each number with a
`data-metric` attribute, so tests can check that the rendered page shows exactly the sidecar values.
tests/integration/test_report.py checks the sidecar against independent SQL.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api import service
from app.api.db import CURRENT, current_schema, query, query_one
from pipeline import upload

REPO_ROOT = Path(__file__).resolve().parents[2]
# VOLTPROOF_REPORT_DIR: the test suite sets it (tests/conftest.py) so test renders never sit next to real reports
OUT_DIR = Path(os.environ.get("VOLTPROOF_REPORT_DIR") or REPO_ROOT / "reports" / "evidence")
TEMPLATES = Path(__file__).resolve().parent / "templates"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")
# VP-DEMO-...: SYNTHETIC demo data (D-033). VP-USER-<upload id>-...: uploaded data, stored in the upload's own folder
# (data/uploads/<id>/reports), so deleting the upload deletes its reports too.
REPORT_ID = re.compile(r"^VP-(DEMO-|USER-[0-9a-f]{8}-)?\d{1,9}-\d{6}-[0-9a-f]{8}$")
S = CURRENT  # the current request's dataset (app/api/db.py)

REDRESS_TEXT = (
    "A consumer can raise supply complaints with the distribution company. In Uttar Pradesh, the State "
    "Electricity Regulatory Commission's 2003 regulations provide a Consumer Grievance Redressal Forum to be "
    "constituted by each distribution licensee and an Electricity Ombudsman appointed or designated by the "
    "Commission; their definition of a deficiency includes interruption or failure of power supply and voltage "
    "complaints. "
    "A consumer whose grievance is not redressed may make a representation to the Ombudsman. Sources: UPERC "
    "(Consumer Grievance Redressal Forum & Electricity Ombudsman) Regulations, 2003, clauses 2.1(i), (l) and (n); "
    "Press Information Bureau, Ministry of Power, 30 December 2010. Check the Commission's current regulations "
    "for the procedure in force. VoltProof does not determine whether any standard of performance was breached, "
    "or what remedy, if any, applies."
)
DISCLAIMER = "VoltProof is an evidence-analysis aid, not legal advice or an official determination."
LIMITATIONS = [
    "A plug-in monitor records the supply at one socket in the premises; it is not the utility's meter. An outage "
    "recorded here may also come from a tripped breaker, wiring or the monitor itself.",
    "The data are historical (ESMI, 2014-2019); they describe supply at that time, not today.",
    "Missing readings are never counted as outage; where an outage borders missing data, its true length lies "
    "between the lower bound (measured minutes) and the stated upper bound.",
    "Monitor accuracy is +/- 4 V (Prayas), so readings within 4 V of a class boundary are sensitive.",
    "Potential shared supply events are coincidences between independent monitors; they are not proof of a "
    "common cause, and chance or independent local causes remain possible.",
]


SYNTHETIC_LIMITATION = ("SYNTHETIC demo data: the monitors, districts and readings in this report are invented "
                        "(pipeline/synthetic.py); no figure describes real electricity supply.")


UPLOAD_LIMITATIONS = [
    "UPLOADED DATA, not verified by VoltProof: the readings come from a file uploaded on this computer. VoltProof "
    "analysed them with the same method as every dataset in the app; nobody has checked where they came from or how "
    "they were recorded.",
    "A monitor records the supply where it is connected; it is not the utility's meter. An outage recorded here may "
    "also come from a tripped breaker, wiring or the monitor itself.",
    LIMITATIONS[2],
    "The accuracy of the device that recorded these readings is not known; readings close to a class boundary are "
    "sensitive. A monitor behind a UPS, inverter or stabiliser keeps showing about 230 V during a cut and cannot "
    "record it.",
    "Districts and states in an uploaded dataset come from the location file or were typed by the person who "
    "uploaded it. Potential shared supply events are grouped by those entries.",
    LIMITATIONS[4],
]
# Outside Uttar Pradesh (uploads only): one general sentence, no citation (owner decision, Checkpoint A).
REDRESS_GENERAL = (
    "A consumer can raise supply complaints with the distribution company. For the grievance procedure that applies "
    "in this state, check the current regulations of the State Electricity Regulatory Commission. VoltProof does not "
    "determine whether any standard of performance was breached, or what remedy, if any, applies."
)


def _limitations(synthetic: bool, kind: str = "real") -> list[str]:
    if kind == "upload":
        return UPLOAD_LIMITATIONS
    if not synthetic:
        return LIMITATIONS
    return [SYNTHETIC_LIMITATION] + [x for x in LIMITATIONS if not x.startswith("The data are historical")]


def _upload_id() -> str | None:
    """The upload id of the current request's dataset (VP_USER_<ID>), or None for the Prayas and synthetic data."""
    schema = current_schema()
    return schema[len("VP_USER_"):].lower() if upload.is_upload_schema(schema) else None


def _out_dir(report_id: str) -> Path:
    if report_id.startswith("VP-USER-"):
        return upload.UPLOAD_DIR / report_id.split("-")[2] / "reports"
    return OUT_DIR


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    env.filters["mins"] = lambda m: "-" if m is None else f"{int(m) // 60} h {int(m) % 60:02d} min"
    env.filters["pct"] = lambda x: "-" if x is None else f"{100 * float(x):.1f}%"
    env.filters["num"] = lambda x: "-" if x is None else f"{x:,}" if isinstance(x, int) else f"{x}"
    return env


def build_data(location_id: int, month_key: str) -> dict:
    m = service.month(location_id, month_key)
    if not m:
        raise LookupError("location-month not found")
    quality = query_one(f"SELECT * FROM {S}.QUALITY_LOCATION WHERE LOCATION_ID = {{id!d}}", {"id": location_id})
    groups = [{k: g[k] for k in ("group_key", "district", "start_ts", "end_ts", "n_locations", "n_members",
                                 "n_pairs", "district_locations_with_interruptions")} | {"members": g["members"]}
              for g in service.groups([e["group_key"] for e in m["events"] if e.get("group_key")])]
    params = {r["name"]: (r["num_value"] if r["num_value"] is not None else r["str_value"])
              for r in query(f"SELECT NAME, NUM_VALUE, STR_VALUE FROM {S}.PARAMS")}
    meta = service.meta()
    prov = service.provenance(["030_unpivot.sql", "040_clean.sql", "050_segments.sql", "060_events.sql",
                               "070_uncertain_claims.sql", "080_daily.sql", "090_monthly.sql", "100_coincidence.sql"])
    files = [f for f in meta["files"] if f["file_kind"] == "readings" and f.get("minutes_in_scope")]
    mo = m["month"]
    data = {
        "report_version": 1,
        "synthetic": bool(meta["synthetic"]),
        "location": m["location"],
        "period": {"month": month_key, "first_day": m["days"][0]["cal_day"] if m["days"] else None,
                   "last_day": m["days"][-1]["cal_day"] if m["days"] else None},
        "summary": {
            "interruptions": mo["interruptions"],
            "outage_minutes_lower": mo["outage_min_lower"],
            "outage_minutes_upper": mo["outage_min_upper"],
            "outage_zero_volt_minutes": mo["outage_zero_minutes"],
            "longest_interruption_minutes": mo["longest_interruption"],
            "low_voltage_minutes": mo["low_minutes"],
            "high_voltage_minutes": mo["high_minutes"],
            "evening_outage_minutes_lower": mo["evening_outage_lower"],
            "evening_outage_minutes_upper": mo["evening_outage_upper"],
            "observed_minutes": mo["observed_minutes"],
            "expected_minutes_in_window": mo["expected_minutes"],
            "calendar_minutes": mo["calendar_minutes"],
            "coverage_calendar": mo["coverage_calendar"],
            "coverage_window": mo["coverage_window"],
            "is_comparable": mo["is_comparable"],
            "events_bounded": sum(1 for e in m["events"] if "bounded" in (e["start_certainty"], e["end_certainty"])),
            "events_censored": sum(1 for e in m["events"] if "censored" in (e["start_certainty"], e["end_certainty"])),
        },
        "days": m["days"],
        "events": m["events"],
        "groups": groups,
        "baseline": m["baseline"],
        "quality": quality,
        "method": {
            "version": meta["method_version"],
            "thresholds": {"outage_max_v": params.get("classification.outage_max_v"),
                           "normal_min_v": params.get("classification.normal_min_v"),
                           "normal_max_v": params.get("classification.normal_max_v")},
            "threshold_source": params.get("classification.source_url"),
            "params": params,
            "limitations": _limitations(meta["synthetic"], meta["dataset_kind"])
            + ([f"Source-file data defect: {m['data_warning']}"] if m["data_warning"] else []),
        },
        "provenance": {
            "app_commit": service.git_commit(),
            "pipeline_commit": (meta["last_run"] or {}).get("pipeline_commit"),
            "data_manifest_sha256": (meta["last_run"] or {}).get("manifest"),
            "run_id": (meta["last_run"] or {}).get("run_id"),
            "statements": prov,
            "source_files": files,
            "citation": meta["citation"],
            "attribution": meta["attribution"],
            "licence": meta["licence"],
            "regenerate": f"scripts\\load.ps1 ; then POST /api/reports {{\"location_id\": {location_id}, "
                          f"\"month\": \"{month_key}\"}}",
        },
        "data_warning": m["data_warning"],
        "redress": REDRESS_TEXT,
        "disclaimer": DISCLAIMER,
        # Monday = 0; places the first day of the window in the calendar grid
        "calendar_offset": dt.date.fromisoformat(m["days"][0]["cal_day"]).weekday() if m["days"] else 0,
    }
    if meta["dataset_kind"] == "upload":  # only uploads get these keys; Prayas and synthetic reports are unchanged
        uid = _upload_id()
        data["upload"] = {**meta["upload"], "upload_id": uid}
        data["provenance"]["regenerate"] = (f"python -m pipeline.upload build {uid} ; then POST /api/reports "
                                            f"{{\"location_id\": {location_id}, \"month\": \"{month_key}\"}}")
        if not upload.is_uttar_pradesh(m["location"].get("state_name")):
            data["redress"] = REDRESS_GENERAL
    return data


def _report_id(location_id: int, month_key: str, data: dict) -> str:
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:8]
    prefix = f"VP-USER-{data['upload']['upload_id']}" if data.get("upload") else \
        "VP-DEMO" if data.get("synthetic") else "VP"
    return f"{prefix}-{location_id}-{month_key.replace('-', '')}-{digest}"


def path_for(report_id: str, ext: str) -> Path | None:
    if not REPORT_ID.fullmatch(report_id) or ext not in ("pdf", "html", "json"):
        return None
    return _out_dir(report_id) / f"{report_id}.{ext}"


def render_html(data: dict) -> str:
    return _env().get_template("report.html").render(d=data)


def _links(rid: str, pdf: bool) -> dict:
    out = {"report_id": rid, "html_url": f"/api/reports/{rid}.html", "json_url": f"/api/reports/{rid}.json"}
    if pdf:
        out["pdf_url"] = f"/api/reports/{rid}.pdf"
    return out


def _reusable(rid: str, data: dict, pdf: bool) -> dict | None:
    """A report rendered earlier (e.g. by scripts\\warmup.ps1) is served again only if its stored numbers equal
    the freshly built data exactly. That data includes the app commit and the last pipeline run, so any code
    change or rebuild gives a fresh render."""
    files = [_out_dir(rid) / f"{rid}.{ext}" for ext in (("json", "html", "pdf") if pdf else ("json", "html"))]
    if not all(f.exists() for f in files):
        return None
    stored = json.loads(files[0].read_text(encoding="utf-8"))
    generated_at = stored.pop("generated_at_ist", None)
    stored.pop("report_id", None)
    if stored != json.loads(json.dumps(data, default=str)):
        return None
    return {**_links(rid, pdf), "generated_at_ist": generated_at, "reused": True}


def generate(location_id: int, month_key: str, pdf: bool = True, reuse: bool = True) -> dict:
    data = build_data(location_id, month_key)
    rid = _report_id(location_id, month_key, data)
    if reuse:
        existing = _reusable(rid, data, pdf)
        if existing:
            return existing
    data["report_id"] = rid
    data["generated_at_ist"] = dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    out = _out_dir(rid)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{rid}.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    html_path = out / f"{rid}.html"
    html_path.write_text(render_html(data), encoding="utf-8")
    if pdf:
        _pdf(html_path, out / f"{rid}.pdf", _footer(data))
    return {**_links(rid, pdf), "generated_at_ist": data["generated_at_ist"], "reused": False}


def _footer(data: dict) -> str:
    """PDF page footer, so every printed page carries the disclaimer and the data source: the disclaimer and the
    attribution (the SYNTHETIC label on the demo set, which has no Prayas attribution), then the page number."""
    synthetic, uploaded = bool(data.get("synthetic")), bool(data.get("upload"))
    first = escape(data["disclaimer"]) + ("" if synthetic else " " + escape(data["provenance"]["attribution"]))
    if uploaded:
        first = escape(data["disclaimer"]) + " Source: uploaded file " + escape(str(data["upload"]["file_name"])) + "."
    return ('<div style="font-size:7px;width:100%;text-align:center;color:#555">'
            f'<div>{first}</div><div>'
            + ('<b>SYNTHETIC DEMO DATA, not ESMI data</b> &middot; ' if synthetic else '')
            + ('<b>UPLOADED DATA, not verified by VoltProof</b> &middot; ' if uploaded else '')
            + 'VoltProof evidence report &middot; page <span class="pageNumber"></span> of '
            '<span class="totalPages"></span></div></div>')


def _pdf(html_path: Path, pdf_path: Path, footer: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.pdf(path=str(pdf_path), format="A4", print_background=True,
                     margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
                     display_header_footer=True,
                     header_template="<div></div>",
                     footer_template=footer)
        finally:
            browser.close()
