"""Read raw ESMI-layout files into oracle rows (test side; independent of the SQL implementation).

Implements the per-file date-format rule of D-025 in plain Python: dash dates follow DD-MM-YYYY unless the
second part exceeds 12 while the first never does (then MM-DD-YYYY); slash dates are MM/DD/YYYY or
DD/MM/YYYY only when the data decides it, otherwise ambiguous ("" -> the oracle quarantines them).
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

from tests.oracle.reference import RawRow

DASH = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def detect_formats(dates: list[str]) -> tuple[str, str]:
    d1 = d2 = s1 = s2 = 0
    for d in dates:
        d = d.strip()
        if m := DASH.match(d):
            d1, d2 = max(d1, int(m.group(1))), max(d2, int(m.group(2)))
        elif m := SLASH.match(d):
            s1, s2 = max(s1, int(m.group(1))), max(s2, int(m.group(2)))
    dash = "%m-%d-%Y" if (d2 > 12 and d1 <= 12) else "%d-%m-%Y"
    if s2 > 12 and s1 <= 12:
        slash = "%m/%d/%Y"
    elif s1 > 12 and s2 <= 12:
        slash = "%d/%m/%Y"
    else:
        slash = ""  # ambiguous
    return dash, slash


def _as_date(v) -> dt.date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


def read_rows(path: Path, names: set[str] | None = None, declared: dict | None = None) -> list[RawRow]:
    """All data rows of `path` (optionally only `names`) with per-row date format and declared period.
    Rows of a file with an exclude_reason are not returned (excluded from the analysis, D-026)."""
    if declared and declared.get("exclude_reason"):
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        raw = [(line_no, row) for line_no, row in enumerate(rd, start=2) if row]
    dash, slash = detect_formats([row[1] for _, row in raw])
    period = None
    if declared and (declared.get("period_from") or declared.get("period_to")):
        period = (_as_date(declared.get("period_from")) or dt.date.min,
                  _as_date(declared.get("period_to")) or dt.date.max)
    out = []
    for line_no, row in raw:
        if names is not None and row[0] not in names:
            continue
        d = row[1].strip()
        fmt = slash if SLASH.match(d) else dash
        out.append(RawRow(row[0], row[1], row[2], row[3:], line_no, date_format=fmt, period=period))
    return out
