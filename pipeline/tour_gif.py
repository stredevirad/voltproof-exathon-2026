"""Record the README's animated tour (docs/deliverables/tour.gif) on the real Prayas build: Playwright screenshots of the
guided demo, the demo day (25 July 2018), the 18:27 outage's evidence page with "How was this computed?" open, the
evidence report and the upload page, joined by ffmpeg into a palette GIF of about 20 s, under 5 MB.

    .venv\\Scripts\\python.exe -m pipeline.tour_gif        # needs VOLTPROOF built, app/web/dist built, .tools\\ffmpeg
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.video import ff
from tests.support.appserver import app_server

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "docs" / "deliverables" / "tour.gif"
WIDTH, MAX_BYTES = 800, 5 * 1024 * 1024


def _frames(base: str, folder: Path) -> list[tuple[Path, float]]:
    """Screenshots and how long each one stays on screen (seconds)."""
    from playwright.sync_api import sync_playwright

    shots: list[tuple[Path, float]] = []

    def shot(pg, seconds: float) -> None:
        p = folder / f"f{len(shots):03d}.png"
        pg.screenshot(path=str(p))
        shots.append((p, seconds))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1280, "height": 800})
        pg.set_default_timeout(60_000)
        pg.goto(base + "/")
        pg.get_by_test_id("guided-demo").wait_for()
        pg.get_by_test_id("location-table").wait_for()
        shot(pg, 2.0)
        pg.get_by_test_id("guided-demo").click()
        pg.get_by_test_id("calendar").wait_for()
        pg.wait_for_timeout(800)
        shot(pg, 3.5)
        month_url = pg.url
        pg.get_by_test_id("demo-next-day").click()
        pg.get_by_test_id("voltage-trace").wait_for()
        pg.wait_for_timeout(800)
        shot(pg, 3.5)
        pg.get_by_test_id("open-selected-event").click()
        pg.get_by_test_id("coincidence-panel").wait_for()
        pg.wait_for_timeout(400)
        shot(pg, 2.5)
        pg.get_by_test_id("provenance").locator("summary").click()
        pg.get_by_test_id("measured-by-exasol").scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        shot(pg, 3.0)
        pg.goto(month_url)
        pg.get_by_test_id("generate-report").click()
        pg.get_by_test_id("report-links").wait_for(timeout=120_000)
        shot(pg, 3.0)
        pg.goto(base + "/upload")
        pg.get_by_test_id("upload-privacy").wait_for()
        shot(pg, 3.0)
        browser.close()
    return shots


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        os.environ["VOLTPROOF_REPORT_DIR"] = str(folder / "reports")  # the server inherits it: no file in reports/
        with app_server("VOLTPROOF") as base:
            shots = _frames(base, folder)
        lst = folder / "frames.txt"
        lines = []
        for p, seconds in shots:
            lines += [f"file '{p.as_posix()}'", f"duration {seconds}"]
        lines.append(f"file '{shots[-1][0].as_posix()}'")  # the concat demuxer needs the last file twice
        lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
        gif = folder / "tour.gif"
        subprocess.run([ff(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf",
                        f"fps=10,scale={WIDTH}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
                        "[b][p]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", str(gif)], check=True)
        size = gif.stat().st_size
        if size > MAX_BYTES:
            print(f"tour.gif is {size:,} bytes, over 5 MB; not written")
            return 1
        shutil.copy(gif, OUT)
    total = sum(s for _, s in shots)
    print(f"wrote {OUT.relative_to(REPO_ROOT)}: {len(shots)} screens, {total:.1f} s, {size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
