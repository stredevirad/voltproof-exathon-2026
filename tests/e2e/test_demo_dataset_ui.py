"""The app on the SYNTHETIC demo set (D-033): a persistent banner on every page, the guided demo lands on the
synthetic shared interruption, the claims scan passes, and no real-data figure or place appears.

Uses schema VOLTPROOF_DEMO and builds it first if it is missing (scripts/load.ps1 -Set demo does the same).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from pipeline.db import connect, schema_dataset
from tests.support.appserver import REPO_ROOT, app_server, get_json
from tests.support.claims import forbidden_hits
from tests.support.contrast import contrast_failures

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
SCHEMA = "VOLTPROOF_DEMO"
REAL_TOKENS = ["102,845,781", "10,28,45,781", "408,223", "4,08,223", "3,945", "1,827.5", "21,970", "366.2",
               "Bahraich", "Huzurpur", "Lucknow", "Prayas, Energy Group, 2019"]
SHOTS = REPO_ROOT / "reports" / "screenshots-synthetic"


@pytest.fixture(scope="module")
def demo_server():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    with connect() as c:
        built = schema_dataset(c, SCHEMA)
    if built["real_files"]:
        pytest.fail(f"{SCHEMA} holds real data; it is reserved for the synthetic demo set")
    if not built["built"]:
        subprocess.run([sys.executable, "-m", "pipeline.build", "--schema", SCHEMA, "--demo"], cwd=REPO_ROOT,
                       check=True, capture_output=True)
    with app_server(SCHEMA) as base:
        yield base


@pytest.fixture(scope="module")
def page(demo_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1366, "height": 860})
        pg.set_default_timeout(30_000)
        yield pg
        browser.close()


def _check(pg, where: str):
    banner = pg.get_by_test_id("synthetic-banner")
    banner.wait_for()
    assert "SYNTHETIC DEMO DATA" in banner.inner_text(), where
    text = pg.inner_text("body")
    assert not forbidden_hits(text), f"{where}: {forbidden_hits(text)}"
    leaked = [t for t in REAL_TOKENS if t in text]
    assert not leaked, f"{where}: real-data tokens on a synthetic page: {leaked}"


def test_meta_says_synthetic(demo_server):
    m = get_json(demo_server, "/api/meta")
    assert m["synthetic"] is True and "SYNTHETIC" in m["attribution"]


def test_every_page_of_the_guided_demo_is_labelled_synthetic(page, demo_server):
    pg = page
    pg.goto(demo_server + "/")
    pg.get_by_test_id("guided-demo").wait_for()
    pg.get_by_test_id("location-table").wait_for()
    _check(pg, "home")
    placeholder = pg.get_by_test_id("location-search").get_attribute("placeholder") or ""
    assert not [t for t in REAL_TOKENS if t in placeholder]
    SHOTS.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(SHOTS / "demo_home.png"))
    pg.get_by_test_id("guided-demo").click()
    pg.get_by_test_id("calendar").wait_for()
    assert "SYNTHETIC" in pg.get_by_test_id("location-title").inner_text()
    _check(pg, "month")
    demo_banner = pg.get_by_test_id("demo-banner").inner_text()  # names the synthetic month, not the real window
    assert "January 2030" in demo_banner and "2018" not in demo_banner, demo_banner
    pg.get_by_test_id("demo-next-day").click()
    pg.get_by_test_id("voltage-trace").wait_for()
    _check(pg, "day")
    pg.get_by_test_id("open-selected-event").click()
    panel = pg.get_by_test_id("coincidence-panel")
    panel.wait_for()
    assert "8 other monitors lost supply within 2 minutes" in panel.inner_text()
    _check(pg, "event")
    pg.get_by_test_id("provenance").locator("summary").click()  # "How was this computed?"
    assert "measured by Exasol" in pg.get_by_test_id("measured-by-exasol").inner_text()
    times = pg.get_by_test_id("provenance").locator("tbody tr td:nth-child(5)").all_inner_texts()
    assert times and all(float(t) >= 0 for t in times), times  # every statement has Exasol's measured duration
    for route in ("/sources", "/methodology"):
        pg.goto(demo_server + route)
        pg.get_by_role("heading").first.wait_for()
        _check(pg, route)


def test_synthetic_pages_meet_wcag_aa_contrast_in_light_and_dark(page, demo_server):
    """The SYNTHETIC banner and pages are readable in both colour schemes (Part 3 UI pass)."""
    d = get_json(demo_server, "/api/demo")
    paths = {"start": ("/", "location-table"),
             "month": (f"/location/{d['location_id']}/{d['month']}?demo=1&day={d['day']}&event={d['event_key']}", "calendar"),
             "day": (f"/location/{d['location_id']}/day/{d['day']}?event={d['event_key']}", "voltage-trace"),
             "event": (f"/event/{d['event_key']}", "event-details")}
    pg = page
    fails = []
    for scheme in ("light", "dark"):
        pg.emulate_media(color_scheme=scheme)
        for name, (path, testid) in paths.items():
            pg.goto(demo_server + path)
            pg.get_by_test_id(testid).wait_for()
            pg.get_by_test_id("synthetic-banner").wait_for()
            pg.wait_for_load_state("networkidle")
            fails += [f"{name} ({scheme}): {f}" for f in contrast_failures(pg)]
    pg.emulate_media(color_scheme="light")
    assert not fails, "\n".join(fails)
