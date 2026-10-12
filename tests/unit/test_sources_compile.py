"""Every tracked Python file compiles without a SyntaxWarning (e.g. an invalid escape such as a Windows path in a
normal string), which would otherwise only show up as noise at import time."""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_python_sources_compile_without_warnings():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"], cwd=REPO_ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    problems = []
    for f in files:
        source = (REPO_ROOT / f).read_text(encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            try:
                compile(source, f, "exec")
            except SyntaxWarning as w:
                problems.append(f"{f}: {w}")
    assert not problems, "\n".join(problems)
