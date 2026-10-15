"""Settings for every test run.

Evidence reports rendered by tests go to reports/tests/evidence, never next to the real reports in
reports/evidence: one test deliberately renders a tampered report, and tests on scratch schemas render reports
with real-looking ids. The app servers and subprocesses that tests start inherit this setting. The run fails if
any test adds or changes a file in reports/evidence.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "reports" / "evidence"
TEST_EVIDENCE = REPO_ROOT / "reports" / "tests" / "evidence"

os.environ["VOLTPROOF_REPORT_DIR"] = str(TEST_EVIDENCE)  # read by app/api/report.py at import


def _listing() -> dict[str, tuple[int, int]]:
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in EVIDENCE.iterdir()} if EVIDENCE.is_dir() else {}


@pytest.fixture(scope="session", autouse=True)
def real_evidence_folder_untouched():
    before = _listing()
    yield
    after = _listing()
    touched = sorted(name for name, stat in after.items() if before.get(name) != stat)
    assert not touched, f"tests wrote to reports/evidence (use reports/tests/evidence): {touched}"
