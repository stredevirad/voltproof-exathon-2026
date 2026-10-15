"""The setup scripts and CI install exactly the locked dependencies: every `uv sync` uses --frozen (uv.lock is
never re-resolved on a judge's machine), and the web app installs with `npm ci` (package-lock.json)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FILES = sorted((REPO_ROOT / "scripts").glob("*.ps1")) + sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
UV_SYNC = re.compile(r"^\s*(run:\s*)?uv sync\b")  # lines that run it, not messages or comments
NPM = re.compile(r"\bnpm(\.cmd)? (ci|install|i)\b")


def _runs(pattern: re.Pattern) -> list[tuple[str, str]]:
    return [(f.name, ln.strip()) for f in FILES for ln in f.read_text(encoding="utf-8").splitlines()
            if pattern.search(ln) and not re.search(r"throw|Write-|^\s*#", ln)]


def test_every_uv_sync_uses_the_lock_file():
    calls = _runs(UV_SYNC)
    assert {name for name, _ in calls} >= {"bootstrap.ps1", "ci.yml"}
    assert [c for c in calls if "--frozen" not in c[1]] == []


def test_web_dependencies_install_from_the_lock_file():
    calls = _runs(NPM)
    assert {name for name, _ in calls} >= {"bootstrap.ps1", "start.ps1"}
    assert [c for c in calls if not re.search(r"\bnpm(\.cmd)? ci\b", c[1])] == []
