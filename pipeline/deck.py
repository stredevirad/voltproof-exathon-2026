"""Render the pitch deck (docs/deliverables/deck/deck.html) to docs/deliverables/VoltProof_deck.pdf with Playwright,
and check its text before writing the PDF:
- no blocked claims phrase or internal reference (tests/support/claims.py);
- every number on the slides also appears in a project doc (README or docs/*.md), so the deck states no
  number that the docs do not;
- no leftover TODO marker.

Usage: .venv\\Scripts\\python.exe -m pipeline.deck
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from tests.support.claims import forbidden_hits

REPO_ROOT = Path(__file__).resolve().parents[1]
DECK = REPO_ROOT / "docs" / "deliverables" / "deck" / "deck.html"
PDF = REPO_ROOT / "docs" / "deliverables" / "VoltProof_deck.pdf"
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _corpus() -> str:
    files = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md")),
             *sorted((REPO_ROOT / "docs" / "data").glob("*.md"))]
    return "\n".join(f.read_text(encoding="utf-8") for f in files if f.exists())


def check(text: str) -> list[str]:
    problems = [f"blocked phrase: {h}" for h in forbidden_hits(text)]
    if "TODO" in text:
        problems.append("TODO marker left in the deck")
    corpus = _corpus()
    corpus_nums = set(NUM.findall(corpus)) | {n.replace(",", "") for n in NUM.findall(corpus)}
    for n in sorted(set(NUM.findall(text))):
        bare = n.replace(",", "")
        if len(bare.replace(".", "")) <= 2 and "." not in n:
            continue  # small integers (slide numbers, "2 minutes", "20 shifts") are not checked
        if n not in corpus_nums and bare not in corpus_nums:
            problems.append(f"number {n} does not appear in README.md or docs/*.md")
    return problems


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(DECK.as_uri())
        page.wait_for_load_state("networkidle")
        text = page.inner_text("body")
        problems = check(text)
        if problems:
            browser.close()
            print("Deck NOT written:\n  " + "\n  ".join(problems))
            return 1
        page.pdf(path=str(PDF), width="1280px", height="720px", print_background=True,
                 margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        n = page.locator("section.slide").count()
        if "--images" in sys.argv:  # 1920 x 1080 review images (not committed)
            review = REPO_ROOT / "reports" / "deck-review"
            review.mkdir(parents=True, exist_ok=True)
            hi = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5)
            hi.goto(DECK.as_uri())
            hi.wait_for_load_state("networkidle")
            for i in range(n):
                hi.locator("section.slide").nth(i).screenshot(path=str(review / f"slide_{i + 1:02d}.png"))
            print(f"review images: {review.relative_to(REPO_ROOT)} ({n} x 1920x1080)")
        browser.close()
    print(f"wrote {PDF.relative_to(REPO_ROOT)} ({n} slides, {PDF.stat().st_size:,} bytes); text checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
