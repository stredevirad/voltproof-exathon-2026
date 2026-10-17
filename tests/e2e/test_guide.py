"""The beginner's guide and the optional first-visit tour (Part 4).

The "How to use VoltProof" page explains the app in plain words on every dataset, names the Prayas data only when it
shows Prayas data, passes the claims scan and WCAG AA contrast, and fits a phone. The tour appears on a person's first
visit to the start page, can be skipped or finished, is remembered in this browser, can be reopened from the guide,
works on the SYNTHETIC set too, and still works when the browser blocks storage. Automated browsers never get it
unless the address asks for it (?tour=1), so screenshots and the other tests see the plain page.
"""

from __future__ import annotations

import pytest

from tests.support.appserver import REPO_ROOT, app_server
from tests.support.claims import forbidden_hits
from tests.support.contrast import contrast_failures

pytestmark = [pytest.mark.e2e, pytest.mark.exasol]
SECTIONS = ["guide-what", "guide-colours", "guide-pick", "guide-day", "guide-shared", "guide-report", "guide-upload",
            "guide-limits"]
PRAYAS = "Electricity Supply Monitoring Initiative"
# what a person's own browser looks like to the page (Playwright's browser reports itself as automated)
PERSON = "Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false });"
NO_STORAGE = ("Storage.prototype.getItem = Storage.prototype.setItem = function () { "
              "throw new DOMException('blocked', 'SecurityError'); };")


@pytest.fixture(scope="module")
def base():
    if not (REPO_ROOT / "app" / "web" / "dist" / "index.html").exists():
        pytest.skip("web app not built (npm run build in app/web)")
    with app_server() as b:
        yield b


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _guide(pg, url: str) -> str:
    pg.goto(url)
    pg.get_by_test_id("guide").wait_for()
    pg.get_by_test_id("guide-data").filter(has_text="data").wait_for()
    for s in SECTIONS:
        assert pg.get_by_test_id(s).inner_text().strip(), s
    text = pg.inner_text("main")
    assert not forbidden_hits(text), forbidden_hits(text)
    return text


def test_guide_on_the_prayas_data(base, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    text = _guide(pg, base + "/guide")
    assert PRAYAS in pg.get_by_test_id("guide-data").inner_text()
    assert "Coincidence is not cause" in text and "130 V or less" in text
    assert "not legal advice or an official determination" in text
    fails = []
    for scheme in ("light", "dark"):
        pg.emulate_media(color_scheme=scheme)
        fails += [f"{scheme}: {f}" for f in contrast_failures(pg)]
    assert not fails, "\n".join(fails)
    # every page links here: the nav, and the month page's "How to read this page"
    pg.get_by_test_id("nav-guide").click()
    pg.get_by_test_id("guide").wait_for()
    ctx.close()


def test_guide_on_the_synthetic_set_names_no_prayas_data(base, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    text = _guide(pg, base + "/guide?ds=VOLTPROOF_DEMO")
    assert "SYNTHETIC" in pg.get_by_test_id("guide-data").inner_text()
    assert PRAYAS not in text, "Prayas attribution on a SYNTHETIC page"
    # the start page's "who recorded this" line names Prayas, so it appears only on the Prayas data
    pg.goto(base + "/?ds=VOLTPROOF_DEMO")
    pg.get_by_test_id("synthetic-banner").wait_for()
    pg.get_by_test_id("location-table").wait_for()
    assert pg.get_by_test_id("home-scope").count() == 0 and pg.get_by_test_id("home-2019-note").count() == 0
    pg.goto(base + "/")
    pg.get_by_test_id("home-scope").wait_for()
    assert "historical records" in pg.get_by_test_id("home-scope").inner_text()
    assert "lower bounds" in pg.get_by_test_id("home-2019-note").inner_text()
    ctx.close()


def test_guide_fits_a_phone(base, browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    pg = ctx.new_page()
    _guide(pg, base + "/guide")
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375
    ctx.close()


def test_no_tour_for_automated_browsers_unless_asked(base, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    pg.goto(base + "/")
    pg.get_by_test_id("location-table").wait_for()
    assert pg.get_by_test_id("tour").count() == 0
    ctx.close()


def test_first_visit_tour_can_be_finished_and_is_remembered(base, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    ctx.add_init_script(PERSON)
    pg = ctx.new_page()
    pg.goto(base + "/")
    tour = pg.get_by_test_id("tour")
    tour.wait_for()
    pg.get_by_test_id("dataset-select").wait_for()   # two datasets here, so the tour has its dataset step
    assert "step 1 of 5" in tour.inner_text()
    seen_targets = []
    while pg.get_by_test_id("tour-next").count():
        pg.get_by_test_id("tour-next").click()
        assert "of 5" in tour.inner_text()           # the count never changes during the tour
        seen_targets.append(pg.evaluate("[...document.querySelectorAll('.tour-target')].map(e => e.dataset.testid)"))
    assert seen_targets == [["guided-demo"], ["state-select"], ["dataset-select"], ["nav-guide"]], seen_targets
    pg.get_by_test_id("tour-done").click()
    assert tour.count() == 0 and pg.locator(".tour-target").count() == 0
    pg.reload()
    pg.get_by_test_id("location-table").wait_for()
    pg.wait_for_timeout(300)
    assert pg.get_by_test_id("tour").count() == 0, "the tour came back after it was finished"
    ctx.close()


def test_tour_can_be_skipped_with_a_button_or_escape_and_reopened_from_the_guide(base, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 860})
    ctx.add_init_script(PERSON)
    pg = ctx.new_page()
    pg.goto(base + "/")
    pg.get_by_test_id("tour").wait_for()
    pg.keyboard.press("Escape")
    assert pg.get_by_test_id("tour").count() == 0
    # reopen from the guide; it lands on the start page with the tour open, then the skip button closes it
    pg.goto(base + "/guide")
    pg.get_by_test_id("guide-open-tour").click()
    pg.get_by_test_id("tour").wait_for()
    pg.get_by_test_id("tour-skip").click()
    assert pg.get_by_test_id("tour").count() == 0
    assert "tour=1" not in pg.url
    ctx.close()


def test_tour_works_on_the_synthetic_set_and_with_storage_blocked(base, browser):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    ctx.add_init_script(PERSON)
    ctx.add_init_script(NO_STORAGE)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base + "/?ds=VOLTPROOF_DEMO")
    pg.get_by_test_id("synthetic-banner").wait_for()
    tour = pg.get_by_test_id("tour")
    tour.wait_for()
    assert not forbidden_hits(tour.inner_text())
    while pg.get_by_test_id("tour-next").count():
        pg.get_by_test_id("tour-next").click()
    pg.get_by_test_id("tour-done").click()
    assert tour.count() == 0
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375
    assert not errors, errors
    ctx.close()
