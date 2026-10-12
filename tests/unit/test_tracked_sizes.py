"""Size check for every tracked file: at most 5 MB, except the final narrated demo video, which the competition
requires in the repository (at most 40 MB; the target is under 25 MB)."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAX = 5 * 2**20
EXCEPTIONS = {"docs/deliverables/VoltProof_demo.mp4": 40 * 2**20}


def test_tracked_files_are_within_size_limits():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO_ROOT,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    big = []
    for f in files:
        p = REPO_ROOT / f
        if p.is_file() and p.stat().st_size > EXCEPTIONS.get(f, DEFAULT_MAX):
            big.append(f"{f}: {p.stat().st_size / 2**20:.1f} MB")
    assert not big, "\n".join(big)
