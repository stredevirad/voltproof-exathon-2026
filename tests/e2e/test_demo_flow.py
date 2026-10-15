"""End-to-end UI test (spec 9.7): the guided demo workflow in a real browser against a real server.

Starts uvicorn on a free port, drives Chromium through the judge's workflow, checks the claims vocabulary on
every page, and saves screenshots to reports/screenshots/ (gitignored). Set VOLTPROOF_UPDATE_SCREENSHOTS=1 to
refresh the committed screenshots in docs/deliverables/screenshots/ for the README and deck instead.
Set VOLTPROOF_RECORD_VIDEO=1 to also record a silent video of the flow (reports/video-run/raw/, gitignored),
paced by docs/deliverables/video_timeline.json (see pipeline/video.py).

Precondition: VOLTPROOF built (scripts\\load.ps1), web app built (app/web/dist).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

import pytest

from tests.support.appserver import app_server, get_json
from tests.support.claims import forbidden_hits

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
REPO_ROOT = Path(__file__).resolve().parents[2]
SHOTS = REPO_ROOT / "reports" / "screenshots"
DOC_SHOTS = REPO_ROOT / "docs" / "deliverables" / "screenshots"  # committed; only with VOLTPROOF_UPDATE_SCREENSHOTS=1
VIDEO = REPO_ROOT / "reports" / "video-run" / "raw"
TIMELINE_FILE = REPO_ROOT / "docs" / "deliverables" / "video_timeline.json"
ACTUAL_FILE = REPO_ROOT / "reports" / "video-run" / "timeline_actual.json"


_STATE = {"synthetic": False}


@pytest.fixture(scope="module")
def server():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    try:
        with app_server() as base:
            # on the SYNTHETIC demo set, screenshots never replace the real ones in docs (D-033)
            _STATE["synthetic"] = bool(get_json(base, "/api/meta").get("synthetic"))
            yield base
    except RuntimeError as e:
        pytest.fail(str(e))


@pytest.fixture(scope="module")
def page(server):
    from playwright.sync_api import sync_playwright

    record = os.environ.get("VOLTPROOF_RECORD_VIDEO") == "1"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx_args = {"viewport": {"width": 1366, "height": 860}, "accept_downloads": True}
        if record:
            VIDEO.mkdir(parents=True, exist_ok=True)
            ctx_args["record_video_dir"] = str(VIDEO)
            ctx_args["record_video_size"] = {"width": 1366, "height": 860}
        ctx = browser.new_context(**ctx_args)
        pg = ctx.new_page()
        _REC["t0"] = time.monotonic()  # the recording starts with the page
        pg.set_default_timeout(30_000)
        yield pg
        ctx.close()
        browser.close()


def _check_wording(pg, where: str):
    hits = forbidden_hits(pg.inner_text("body"))
    assert not hits, f"{where}: " + "; ".join(hits)


def _shot(pg, name: str):
    if _STATE["synthetic"]:
        target = REPO_ROOT / "reports" / "screenshots-synthetic"
    else:
        target = DOC_SHOTS if os.environ.get("VOLTPROOF_UPDATE_SCREENSHOTS") == "1" else SHOTS
    target.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(target / f"{name}.png"), full_page=False)


RECORDING = os.environ.get("VOLTPROOF_RECORD_VIDEO") == "1"
_REC: dict = {"t0": time.monotonic(), "marks": {}}


def _segment(seg_id: str):
    """While recording: a narration segment starts now (offset from the start of the video is logged)."""
    if RECORDING:
        _REC["marks"][seg_id] = round(time.monotonic() - _REC["t0"], 2)


def _hold(pg, seg_id: str, share: float = 1.0):
    """While recording: wait until `share` of the segment's hold (video_timeline.json) has passed since the
    segment started, so slow or fast page actions never shift later segments. No effect on normal runs."""
    if not RECORDING:
        return
    segments = json.loads(TIMELINE_FILE.read_text(encoding="utf-8"))["segments"]
    hold = {s["id"]: s for s in segments}[seg_id]["hold"]
    wait = _REC["marks"][seg_id] + hold * share - (time.monotonic() - _REC["t0"])
    if wait > 0:
        pg.wait_for_timeout(int(wait * 1000))


def _caption(pg, text: str | None):
    """While recording: a visible caption (e.g. 'Illustrative example') over the page; None removes it."""
    if not RECORDING:
        return
    if text is None:
        pg.evaluate("() => document.getElementById('vp-caption')?.remove()")
        return
    pg.evaluate("""t => { const d = document.createElement('div'); d.id = 'vp-caption'; d.textContent = t;
        Object.assign(d.style, {position: 'fixed', right: '28px', bottom: '28px', padding: '10px 16px',
          background: 'rgba(11,11,11,.78)', color: '#fff', font: '600 18px Segoe UI, sans-serif',
          borderRadius: '6px', zIndex: 9999}); document.body.appendChild(d); }""", text)


def _save_marks():
    if RECORDING:
        ACTUAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        ACTUAL_FILE.write_text(json.dumps({"segments": _REC["marks"]}, indent=1), encoding="utf-8")


def test_guided_demo_workflow(page, server):
    pg = page
    pg.goto(server + "/")
    pg.get_by_test_id("guided-demo").wait_for()
    pg.get_by_test_id("location-table").wait_for()
    _check_wording(pg, "home")
    _shot(pg, "01_home")
    _segment("intro")
    _caption(pg, "Illustrative example")
    _hold(pg, "intro")
    _caption(pg, None)

    # 1. guided demo -> location-month dashboard with KPIs and calendar
    pg.get_by_test_id("guided-demo").click()
    _segment("month")
    pg.get_by_test_id("demo-banner").wait_for()
    pg.get_by_test_id("calendar").wait_for()
    assert pg.get_by_test_id("kpi-interruptions").inner_text().strip()
    assert "comparable" in pg.get_by_test_id("quality-badge").inner_text()
    pg.wait_for_timeout(600)  # let the canvas paint for the screenshot
    _check_wording(pg, "month")
    _shot(pg, "02_month_calendar")
    month_url = pg.url
    _hold(pg, "month")

    # 2. the demo day: minute-by-minute trace with the selected outage
    pg.get_by_test_id("demo-next-day").click()
    _segment("day")
    pg.get_by_test_id("voltage-trace").wait_for()
    pg.get_by_test_id("day-events").wait_for()
    pg.wait_for_timeout(600)
    _check_wording(pg, "day")
    _shot(pg, "03_day_trace")
    _hold(pg, "day")

    # 3. the selected event: timestamps, certainty, provenance, coincidence panel
    pg.get_by_test_id("open-selected-event").click()
    _segment("event")
    pg.get_by_test_id("event-details").wait_for()
    assert pg.get_by_test_id("event-start").inner_text().strip()
    assert pg.get_by_test_id("start-certainty").inner_text().strip()
    panel = pg.get_by_test_id("coincidence-panel")
    panel.wait_for()
    assert "potential shared supply event" in panel.inner_text().lower()
    assert "Coincidence is not cause" in panel.inner_text()
    pg.get_by_test_id("provenance").locator("summary").click()
    assert "line" in pg.get_by_test_id("provenance").inner_text()
    _check_wording(pg, "event")
    _shot(pg, "04_event_evidence")
    if RECORDING:  # show the provenance table, then come back to the panel of other monitors
        _hold(pg, "event", 0.45)
        pg.mouse.wheel(0, 500)
        _hold(pg, "event", 0.8)
        pg.mouse.wheel(0, -500)
        _hold(pg, "event")

    # 4. back to the month: generate and download the evidence report
    pg.goto(month_url)
    _segment("report")
    pg.get_by_test_id("generate-report").click()
    pg.get_by_test_id("report-links").wait_for(timeout=120_000)
    with pg.expect_download() as dl:
        pg.get_by_test_id("report-pdf").click()
    path = dl.value.path()
    assert Path(path).read_bytes()[:4] == b"%PDF"
    _shot(pg, "05_report_ready")
    _hold(pg, "report")

    if RECORDING:  # data and sources (the 2019 files), then the start page
        pg.goto(server + "/sources")
        _segment("sources")
        pg.get_by_test_id("files-table").wait_for()
        _hold(pg, "sources", 0.25)
        warning = pg.get_by_test_id("file-data-warning")
        (warning if warning.count() else pg.get_by_test_id("files-table")).scroll_into_view_if_needed()
        _hold(pg, "sources")
        pg.goto(server + "/")
        _segment("close")
        pg.get_by_test_id("guided-demo").wait_for()
        _hold(pg, "close")
        _save_marks()


def test_methodology_and_sources_pages(page, server):
    pg = page
    for route, marker in (("/methodology", "Voltage classes"), ("/sources", "Source files")):
        pg.goto(server + route)
        pg.get_by_text(marker).first.wait_for()
        _check_wording(pg, route)
    # What the Sources page must show depends on which files this build loaded (README minimum set vs full UP)
    with urllib.request.urlopen(server + "/api/meta", timeout=30) as r:
        files = [f for f in json.loads(r.read())["files"] if f["file_kind"] == "readings"]
    table = pg.get_by_test_id("files-table").inner_text()
    if any(f.get("exclude_reason") for f in files):  # 2019 July-Dec loaded: excluded with its reason (D-026)
        assert "Excluded" in table
    if any(f.get("data_warning") for f in files):  # 2019 Jan-June loaded: lower-bound warning (D-031)
        assert "lower bounds" in pg.get_by_test_id("file-data-warning").inner_text()
    else:
        assert pg.get_by_test_id("file-data-warning").count() == 0
    _shot(pg, "06_sources")


def test_error_and_empty_states(page, server):
    pg = page
    pg.goto(server + "/event/1-201801010000")
    assert "Could not load" in pg.get_by_role("alert").inner_text()
    pg.goto(server + "/location/999999/2018-07")
    assert "Could not load" in pg.get_by_role("alert").inner_text()
    pg.goto(server + "/")
    pg.get_by_test_id("location-search").fill("zzzz-no-such-place")
    pg.get_by_text("No monitored location matches").wait_for()


def test_lower_bound_banner_on_2019_month(page, server):
    """D-031: months covered by the defective 2019 Jan-Jun file show the lower-bound warning."""
    try:
        urllib.request.urlopen(server + "/api/locations/90/months/2019-01", timeout=30)
    except Exception:
        pytest.skip("Biswan-Sitapur 2019-01 not in this build")
    pg = page
    pg.goto(server + "/location/90/2019-01")
    banner = pg.get_by_test_id("data-warning")
    banner.wait_for()
    assert "lower bounds" in banner.inner_text()
    pg.get_by_test_id("calendar").wait_for()
    pg.wait_for_timeout(600)
    _check_wording(pg, "2019 month")
    _shot(pg, "07_lower_bound_2019")
