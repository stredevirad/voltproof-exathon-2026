"""The day view draws every recorded minute, whatever time zone the viewer's computer is in (audit F-09). Before the
fix, a browser in a daylight-saving zone lost an hour of minutes on its own clock-change day, because the chart built
its minute keys through the browser's local clock. Checked on the clock-change days of New York and London, with a
monitor that has readings on those days (Prayas data only; skipped on the SYNTHETIC set, which has no such day)."""

from __future__ import annotations

import pytest

from tests.support.appserver import REPO_ROOT, app_server, get_json

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
CASES = [("America/New_York", "2018-03-11"), ("Europe/London", "2018-03-25"), ("Asia/Kolkata", "2018-03-11")]


@pytest.fixture(scope="module")
def base():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    with app_server() as b:
        yield b


def _location_with_readings(base: str, day: str) -> tuple[int, int] | None:
    for loc in get_json(base, "/api/locations"):
        if not (loc["first_ts"] <= f"{day}T23:59" and loc["last_ts"] >= f"{day}T00:00"):
            continue
        n = len({r["ts"] for r in get_json(base, f"/api/locations/{loc['location_id']}/days/{day}")["readings"]})
        if n > 1300:
            return loc["location_id"], n
    return None


@pytest.mark.parametrize("zone,day", CASES)
def test_every_recorded_minute_is_drawn_in_any_viewer_time_zone(base, zone, day):
    found = _location_with_readings(base, day)
    if not found:
        pytest.skip(f"no monitor with readings on {day} in this build")
    location_id, minutes = found
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(timezone_id=zone, viewport={"width": 1366, "height": 860})
        pg = ctx.new_page()
        pg.goto(f"{base}/location/{location_id}/day/{day}")
        pg.get_by_test_id("voltage-trace").wait_for()
        charted = int(pg.get_by_test_id("day-minutes-charted").text_content())
        browser.close()
    assert charted == minutes, f"{zone} {day}: {charted} minutes drawn, {minutes} recorded"
