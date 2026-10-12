"""Report consistency (spec 9.3): every number in an evidence report equals an independent SQL query, and the
rendered HTML shows exactly the sidecar values. Also checks the claims vocabulary and the PDF.

Precondition: the production schema VOLTPROOF is built (scripts\\load.ps1) with the 2018 June-Aug data.
"""

from __future__ import annotations

import json
import re
import uuid
from html import unescape
from pathlib import Path

import pytest

from app.api import report, service
from pipeline.db import DEFAULT_SCHEMA, connect
from tests.support.claims import forbidden_hits

pytestmark = pytest.mark.exasol
S = DEFAULT_SCHEMA


@pytest.fixture(scope="module")
def generated():
    demo = service.demo()
    if not demo:
        pytest.skip("demo preset not available (build VOLTPROOF with the 2018 June-Aug data)")
    out = report.generate(demo["location_id"], demo["month"], pdf=True, reuse=False)  # always a fresh render
    rid = out["report_id"]
    side = json.loads(report.path_for(rid, "json").read_text(encoding="utf-8"))
    html = report.path_for(rid, "html").read_text(encoding="utf-8")
    return {"demo": demo, "out": out, "side": side, "html": html, "pdf": report.path_for(rid, "pdf")}


def test_sidecar_summary_equals_independent_sql(generated):
    side, demo = generated["side"], generated["demo"]
    lid, month = demo["location_id"], demo["month"]
    with connect(schema=S) as c:
        # independent path: sums over DAILY and counts over EVENT (the report reads MONTHLY)
        d = c.execute(
            f"""SELECT SUM(OUTAGE_MIN_LOWER), SUM(OUTAGE_MIN_UPPER), SUM(OUTAGE_ZERO_MINUTES), SUM(LOW_MINUTES),
                       SUM(HIGH_MINUTES), SUM(EVENING_OUTAGE_LOWER), SUM(EVENING_OUTAGE_UPPER), SUM(OBSERVED_MINUTES),
                       SUM(EXPECTED_MINUTES), MAX(LONGEST_INTERRUPTION)
                FROM DAILY WHERE LOCATION_ID = {lid} AND TO_CHAR(CAL_DAY, 'YYYY-MM') = '{month}'""").fetchone()
        n_int = c.execute(f"""SELECT COUNT(*) FROM EVENT WHERE LOCATION_ID = {lid} AND IS_INTERRUPTION
                              AND TO_CHAR(START_TS, 'YYYY-MM') = '{month}'""").fetchval()
        n_events = c.execute(f"""SELECT COUNT(*) FROM EVENT WHERE LOCATION_ID = {lid}
                                 AND TO_CHAR(START_TS, 'YYYY-MM') = '{month}'""").fetchval()
        dup, conf, quar = c.execute(f"""SELECT COALESCE(SUM(DUPLICATE_COUNT),0),
                                          (SELECT COUNT(*) FROM READING_CONFLICT WHERE LOCATION_ID = {lid}),
                                          (SELECT COUNT(*) FROM VALUE_QUARANTINE WHERE LOCATION_ID = {lid})
                                        FROM READING_CLEAN WHERE LOCATION_ID = {lid}""").fetchone()
        base = c.execute(f"""SELECT OBSERVED_PAIRS FROM COINCIDENCE_BASELINE b JOIN LOCATION l ON l.DISTRICT = b.DISTRICT
                             WHERE l.LOCATION_ID = {lid} AND b.MONTH_KEY = '{month}'""").fetchval()
    s = side["summary"]
    expected = {
        "outage_minutes_lower": d[0], "outage_minutes_upper": d[1], "outage_zero_volt_minutes": d[2],
        "low_voltage_minutes": d[3], "high_voltage_minutes": d[4], "evening_outage_minutes_lower": d[5],
        "evening_outage_minutes_upper": d[6], "observed_minutes": d[7], "expected_minutes_in_window": d[8],
        "longest_interruption_minutes": d[9], "interruptions": n_int,
    }
    problems = [f"{k}: report={s[k]} sql={int(v)}" for k, v in expected.items() if int(s[k]) != int(v)]
    if len(side["events"]) != int(n_events):
        problems.append(f"events listed {len(side['events'])} != {n_events}")
    q = side["quality"]
    for k, v in (("duplicate_readings", dup), ("conflict_minutes", conf), ("quarantined_values", quar)):
        if int(q[k]) != int(v):
            problems.append(f"quality.{k}: report={q[k]} sql={v}")
    if side["baseline"] and int(side["baseline"]["observed_pairs"]) != int(base):
        problems.append(f"baseline.observed_pairs {side['baseline']['observed_pairs']} != {base}")
    assert not problems, "\n".join(problems)


def _metrics(html: str) -> dict[str, str]:
    return {m.group(1): unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
            for m in re.finditer(r'data-metric="([^"]+)"[^>]*>(.*?)</', html, re.S)}


def _fmt(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def test_rendered_html_shows_exactly_the_sidecar_numbers(generated):
    side, html = generated["side"], generated["html"]
    shown = _metrics(html)
    assert len(shown) > 50, "the template must tag its numbers with data-metric"
    problems = []
    for key, text in shown.items():
        node = side
        for part in key.split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        if key.endswith("coverage_calendar"):
            want = f"{100 * float(node):.1f}%"
        elif key.endswith("expected_pairs"):
            want = f"{float(node):.1f}"
        elif key.endswith("observed_minutes") and key.startswith("days."):
            want = f"{node}/1440"
        elif key.startswith("days.") or key.startswith("events."):
            want = str(node)
        else:
            want = _fmt(node)
        if text != want:
            problems.append(f"{key}: html={text!r} sidecar={want!r}")
    assert not problems, "\n".join(problems[:30])


def test_report_uses_only_allowed_wording(generated):
    text = unescape(re.sub(r"<[^>]+>", " ", generated["html"]))
    hits = forbidden_hits(text)
    assert not hits, "\n".join(hits)
    assert "not legal advice" in text
    assert "Prayas" in text and "doi.org/10.7910/DVN/CLLZZM" in text


def test_pdf_is_written(generated):
    pdf: Path = generated["pdf"]
    data = pdf.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 20_000


def test_data_warning_only_in_reports_for_affected_months(generated):
    """D-031: a report for a 2019 Jan-Jun month carries the source-file warning; the 2018 demo report does not."""
    assert generated["side"]["data_warning"] is None
    assert 'data-testid="data-warning"' not in generated["html"]
    assert not any(l.startswith("Source-file data defect") for l in generated["side"]["method"]["limitations"])
    with connect(schema=S) as c:
        row = c.execute("SELECT LOCATION_ID, MONTH_KEY FROM MONTHLY WHERE MONTH_KEY = '2019-01' "
                        "ORDER BY LOCATION_ID LIMIT 1").fetchone()
    if not row:
        pytest.skip("no 2019 month in this build")
    out = report.generate(int(row[0]), row[1], pdf=False, reuse=False)
    side = json.loads(report.path_for(out["report_id"], "json").read_text(encoding="utf-8"))
    html = report.path_for(out["report_id"], "html").read_text(encoding="utf-8")
    assert side["data_warning"] and "lower bounds" in side["data_warning"]
    assert 'data-testid="data-warning"' in html
    assert any(l.startswith("Source-file data defect") for l in side["method"]["limitations"])
    assert not forbidden_hits(unescape(re.sub(r"<[^>]+>", " ", html)))


def test_unchanged_report_is_reused_with_its_generation_time(generated):
    """scripts/warmup.ps1 pre-renders the demo report; the app serves it again only for identical data."""
    demo = generated["demo"]
    again = report.generate(demo["location_id"], demo["month"], pdf=True)
    assert again["reused"] is True
    assert again["report_id"] == generated["out"]["report_id"]
    assert again["generated_at_ist"] == generated["out"]["generated_at_ist"]


def test_changed_data_is_never_served_from_an_earlier_render(generated, monkeypatch):
    demo = generated["demo"]
    real = report.build_data

    nonce = uuid.uuid4().hex  # unique per run: identical data rendered by an earlier run may rightly be reused

    def changed(location_id, month_key):
        d = real(location_id, month_key)
        d["summary"]["interruptions"] = int(d["summary"]["interruptions"]) + 1
        d["summary"]["test_nonce"] = nonce
        return d

    monkeypatch.setattr(report, "build_data", changed)
    out = report.generate(demo["location_id"], demo["month"], pdf=False)
    assert out["reused"] is False
    assert out["report_id"] != generated["out"]["report_id"]
