"""Evidence report for one location and month: one data dict -> sidecar JSON + HTML (Jinja2) -> PDF (Playwright).

The sidecar JSON is the single source of every number printed. The HTML marks each number with a
`data-metric` attribute, so tests can check that the rendered page shows exactly the sidecar values.
tests/integration/test_report.py checks the sidecar against independent SQL.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.api import service
from app.api.db import SCHEMA, query, query_one

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reports" / "evidence"
TEMPLATES = Path(__file__).resolve().parent / "templates"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")
REPORT_ID = re.compile(r"^VP-\d{1,9}-\d{6}-[0-9a-f]{8}$")
S = SCHEMA

REDRESS_TEXT = (
    "A consumer can raise supply complaints with the distribution company. In Uttar Pradesh, the State "
    "Electricity Regulatory Commission's regulations made under Section 42(5) to (8) of the Electricity Act, 2003 "
    "provide a Consumer Grievance Redressal Forum to be constituted by each distribution licensee (Section 42(5)) "
    "and an Electricity Ombudsman appointed or designated by the Commission (Section 42(6)); their 2003 "
    "definition of a deficiency includes interruption or failure of power supply and voltage complaints. "
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
    groups = []
    for key in sorted({e["group_key"] for e in m["events"] if e.get("group_key")}):
        g = service.group(key)
        if g:
            groups.append({k: g[k] for k in ("group_key", "district", "start_ts", "end_ts", "n_locations", "n_members",
                                             "n_pairs", "district_locations_with_interruptions")}
                          | {"members": g["members"]})
    params = {r["name"]: (r["num_value"] if r["num_value"] is not None else r["str_value"])
              for r in query(f"SELECT NAME, NUM_VALUE, STR_VALUE FROM {S}.PARAMS")}
    meta = service.meta()
    prov = service.provenance(["030_unpivot.sql", "040_clean.sql", "050_segments.sql", "060_events.sql",
                               "070_uncertain_claims.sql", "080_daily.sql", "090_monthly.sql", "100_coincidence.sql"])
    files = [f for f in meta["files"] if f["file_kind"] == "readings" and f.get("minutes_in_scope")]
    mo = m["month"]
    data = {
        "report_version": 1,
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
            "limitations": LIMITATIONS,
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
        "redress": REDRESS_TEXT,
        "disclaimer": DISCLAIMER,
        # Monday = 0; places the first day of the window in the calendar grid
        "calendar_offset": dt.date.fromisoformat(m["days"][0]["cal_day"]).weekday() if m["days"] else 0,
    }
    return data


def _report_id(location_id: int, month_key: str, data: dict) -> str:
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:8]
    return f"VP-{location_id}-{month_key.replace('-', '')}-{digest}"


def path_for(report_id: str, ext: str) -> Path | None:
    if not REPORT_ID.match(report_id) or ext not in ("pdf", "html", "json"):
        return None
    return OUT_DIR / f"{report_id}.{ext}"


def render_html(data: dict) -> str:
    return _env().get_template("report.html").render(d=data)


def generate(location_id: int, month_key: str, pdf: bool = True) -> dict:
    data = build_data(location_id, month_key)
    rid = _report_id(location_id, month_key, data)
    data["report_id"] = rid
    data["generated_at_ist"] = dt.datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{rid}.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    html_path = OUT_DIR / f"{rid}.html"
    html_path.write_text(render_html(data), encoding="utf-8")
    out = {"report_id": rid, "html_url": f"/api/reports/{rid}.html", "json_url": f"/api/reports/{rid}.json"}
    if pdf:
        _pdf(html_path, OUT_DIR / f"{rid}.pdf")
        out["pdf_url"] = f"/api/reports/{rid}.pdf"
    return out


def _pdf(html_path: Path, pdf_path: Path) -> None:
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
                     footer_template='<div style="font-size:7px;width:100%;text-align:center;color:#555">'
                                     'VoltProof evidence report &middot; page <span class="pageNumber"></span> of '
                                     '<span class="totalPages"></span></div>')
        finally:
            browser.close()
