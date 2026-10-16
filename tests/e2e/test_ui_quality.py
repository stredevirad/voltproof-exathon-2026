"""How the pages read, not what they say (Part 3 UI pass). On every main screen, in the light and the dark colour
scheme: text contrast meets WCAG AA, and a 375 px phone screen never scrolls sideways. The month page leads with one
number (outage time, at least) and offers one filled button (the evidence report); every number tile carries a plain
caption. Table rows that open something hold a real link or button, so keyboard and screen-reader users can reach
them (audit F-14). No number is checked here: the API and text comparisons do that.
"""

from __future__ import annotations

import urllib.parse

import pytest

from tests.support.appserver import REPO_ROOT, app_server, get_json
from tests.support.contrast import contrast_failures

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
TILES = ["kpi-outage", "kpi-interruptions", "kpi-longest", "kpi-low", "kpi-coverage"]


@pytest.fixture(scope="module")
def base():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    with app_server() as b:
        yield b


@pytest.fixture(scope="module")
def screens(base) -> dict[str, tuple[str, str]]:
    """name -> (path, test id that marks the page as loaded)."""
    d = get_json(base, "/api/demo")
    lid, month, day, ek, gk = d["location_id"], d["month"], d["day"], d["event_key"], d["group_key"]
    return {
        "start": ("/", "location-table"),
        "month": (f"/location/{lid}/{month}?demo=1&day={day}&event={ek}", "calendar"),
        "day": (f"/location/{lid}/day/{day}?event={ek}", "voltage-trace"),
        "event": (f"/event/{ek}", "event-details"),
        "group": (f"/group?key={urllib.parse.quote(gk)}", "coincidence-panel"),
        "methodology": ("/methodology", ""),
        "sources": ("/sources", "files-table"),
        "upload": ("/upload", "upload-privacy"),
    }


def _open(pg, base: str, path: str, testid: str):
    pg.goto(base + path)
    if testid:
        pg.get_by_test_id(testid).wait_for()
    pg.wait_for_load_state("networkidle")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_text_contrast_meets_wcag_aa_on_every_screen(base, screens, browser, scheme):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860}, color_scheme=scheme)
    pg = ctx.new_page()
    pg.set_default_timeout(60_000)
    failures = []
    for name, (path, testid) in screens.items():
        _open(pg, base, path, testid)
        failures += [f"{name}: {f}" for f in contrast_failures(pg)]
    ctx.close()
    assert not failures, f"{scheme} scheme, text below WCAG AA contrast:\n" + "\n".join(failures)


def test_phone_width_never_scrolls_sideways(base, screens, browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    pg = ctx.new_page()
    pg.set_default_timeout(60_000)
    wide = []
    for name, (path, testid) in screens.items():
        _open(pg, base, path, testid)
        width = pg.evaluate("document.documentElement.scrollWidth")
        if width > 375:
            wide.append(f"{name}: page is {width} px wide")
    ctx.close()
    assert not wide, "\n".join(wide)


def test_month_page_leads_with_the_outage_lower_bound_and_one_action(base, screens, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    _open(pg, base, *screens["month"])
    sizes = {t: pg.get_by_test_id(t).locator(".value").evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
             for t in TILES}
    assert all(sizes["kpi-outage"] > s for t, s in sizes.items() if t != "kpi-outage"), sizes
    assert "at least" in pg.get_by_test_id("kpi-outage").inner_text().lower()
    first = pg.locator(".kpis .kpi").first.get_attribute("data-testid")
    assert first == "kpi-outage", f"the first tile is {first}"
    for t in TILES:
        assert pg.get_by_test_id(f"{t}-plain").inner_text().strip(), f"{t} has no plain caption"
    filled = pg.locator("button.primary:visible, a.button.primary:visible")
    assert filled.count() == 1 and filled.first.get_attribute("data-testid") == "generate-report"
    legend = pg.get_by_test_id("calendar-legend").inner_text()
    assert "no outage" in legend and "≥ 12 h" in legend
    ctx.close()


def test_table_rows_open_through_a_real_link_or_button(base, screens, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    pg.set_default_timeout(60_000)
    # start page: a monitor is chosen with a button (keyboard: focus it, press Enter)
    _open(pg, base, "/", "location-table")
    row = pg.get_by_test_id("location-table").locator("tbody tr").first
    choose = row.get_by_role("button")
    assert choose.count() == 1
    choose.focus()
    pg.keyboard.press("Enter")
    assert choose.get_attribute("aria-pressed") == "true"
    months = pg.get_by_test_id("month-table")
    months.wait_for()
    links = months.locator("tbody tr").first.get_by_role("link")
    assert links.count() == 1 and "/location/" in links.first.get_attribute("href")
    # month page and day page: every event row holds one link to its evidence page
    for name, table in (("month", "event-table"), ("day", "day-events")):
        _open(pg, base, *screens[name])
        rows = pg.get_by_test_id(table).locator("tbody tr")
        n = rows.count()
        hrefs = [rows.nth(i).get_by_role("link").first.get_attribute("href") for i in range(min(n, 25))]
        assert n and all(h and "/event/" in h for h in hrefs), f"{name}: {hrefs}"
    # keyboard: the first link of the day's outage table opens the event page
    pg.get_by_test_id("day-events").locator("tbody tr").first.get_by_role("link").first.focus()
    pg.keyboard.press("Enter")
    pg.get_by_test_id("event-details").wait_for()
    assert "/event/" in pg.url
    ctx.close()
