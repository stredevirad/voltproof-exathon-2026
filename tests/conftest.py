"""Settings for every test run.

Evidence reports rendered by tests go to reports/tests/evidence, never next to the real reports in
reports/evidence: one test deliberately renders a tampered report, and tests on scratch schemas render reports
with real-looking ids. The app servers and subprocesses that tests start inherit this setting.

The run fails if any test adds or changes a file in reports/evidence, or in the committed screenshots
(docs/deliverables/screenshots) unless VOLTPROOF_UPDATE_SCREENSHOTS=1 asks the e2e test to refresh them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "reports" / "evidence"
TEST_EVIDENCE = REPO_ROOT / "reports" / "tests" / "evidence"
DOC_SHOTS = REPO_ROOT / "docs" / "deliverables" / "screenshots"

os.environ["VOLTPROOF_REPORT_DIR"] = str(TEST_EVIDENCE)  # read by app/api/report.py at import


def _listing(folder: Path) -> dict[str, tuple[int, int]]:
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.iterdir()} if folder.is_dir() else {}


@pytest.fixture(scope="session", autouse=True)
def protected_folders_untouched():
    folders = [EVIDENCE] if os.environ.get("VOLTPROOF_UPDATE_SCREENSHOTS") == "1" else [EVIDENCE, DOC_SHOTS]
    before = {f: _listing(f) for f in folders}
    yield
    touched = sorted(f"{f.relative_to(REPO_ROOT).as_posix()}/{name}"
                     for f in folders for name, stat in _listing(f).items() if before[f].get(name) != stat)
    assert not touched, f"tests wrote to protected folders (reports/evidence, committed screenshots): {touched}"
