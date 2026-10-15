"""The grievance route is cited only from the UPERC 2003 regulations and the 2010 PIB release (VERIFICATION_LOG
L1, L2). The Act's text was never read (L3), so no published text names the Electricity Act or its sections, and
the Electricity (Rights of Consumers) Rules, 2020 are not cited either. docs/VERIFICATION_LOG.md is the record of
what was checked, not a claim to users, and is not scanned."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.api.report import REDRESS_TEXT

REPO_ROOT = Path(__file__).resolve().parents[2]
NOT_CITED = re.compile(r"Electricity Act|Section 42|\bs\. ?42\b|42\(\d\)|Rights of Consumers|Rules,? 2020|2020 Rules",
                       re.IGNORECASE)
TEXT_SUFFIXES = {".md", ".html", ".py", ".ts", ".tsx", ".json", ".txt", ".yaml", ".yml", ".ps1", ".sql", ".css"}
RECORD_ONLY = {"docs/VERIFICATION_LOG.md"}


def test_report_redress_text_cites_only_the_uperc_regulations_and_pib():
    assert "UPERC (Consumer Grievance Redressal Forum & Electricity Ombudsman) Regulations, 2003" in REDRESS_TEXT
    assert "Press Information Bureau, Ministry of Power, 30 December 2010" in REDRESS_TEXT
    assert not NOT_CITED.search(REDRESS_TEXT)
    assert "compensation" not in REDRESS_TEXT.lower()


def test_no_published_text_names_the_electricity_act_or_the_2020_rules():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO_ROOT,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    hits = []
    for f in files:
        p = REPO_ROOT / f
        if f in RECORD_ONLY or f.startswith("tests/") or p.suffix not in TEXT_SUFFIXES or not p.is_file():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if NOT_CITED.search(line):
                hits.append(f"{f}:{n}: {line.strip()[:100]}")
    assert not hits, "\n".join(hits)
