"""Every tracked text file is published (public repository): it must not contain a forbidden claims phrase or an
internal-only reference (tests/support/claims.py). Only the files that define the vocabulary, and .gitignore
(which must name the private folder to exclude it), are exempt."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.support.claims import forbidden_hits

REPO_ROOT = Path(__file__).resolve().parents[2]
EXEMPT = {".gitignore", "tests/support/claims.py", "tests/unit/test_claims.py"}
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".webm", ".mp4", ".zip"}


def _published_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return sorted({f for f in out.splitlines() if f and Path(f).suffix.lower() not in BINARY and f not in EXEMPT})


def scan() -> list[str]:
    hits = []
    for f in _published_files():
        path = REPO_ROOT / f
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for no, line in enumerate(text.splitlines(), 1):
            for h in forbidden_hits(line):
                hits.append(f"{f}:{no}: {h}")
    return hits


def test_published_text_has_no_forbidden_or_internal_terms():
    hits = scan()
    assert not hits, f"{len(hits)} hit(s):\n" + "\n".join(hits)
