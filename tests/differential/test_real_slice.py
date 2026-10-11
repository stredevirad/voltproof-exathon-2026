"""Differential tests on REAL data: the Exasol SQL pipeline vs the independent oracle.

Precondition: the production schema VOLTPROOF has been built from data/raw with the default
config/method.yaml (scripts\\load.ps1). The oracle reads, by itself, the raw CSV lines of the chosen
locations from EVERY readings file recorded in VOLTPROOF.SOURCE_FILE, so the comparison covers exactly the
same data as the SQL whatever subset (first / up / all) was loaded.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from pipeline.db import connect
from tests.oracle.reference import RawRow, run
from tests.support.compare import (diff, diff_coincidence, fetch_coincidence, fetch_sql, oracle_as_comparable,
                                   oracle_coincidence, params_from_yaml)

pytestmark = pytest.mark.exasol

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
SCHEMA = "VOLTPROOF"
SLICE_SIZE = 4


def _readings_files(conn) -> list[Path]:
    names = [r[0] for r in conn.execute(
        f"SELECT FILE_NAME FROM {SCHEMA}.SOURCE_FILE WHERE FILE_KIND = 'readings' ORDER BY FILE_ID").fetchall()]
    files = [RAW_DIR / n for n in names]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        pytest.skip(f"raw files loaded in {SCHEMA} are not present in data/raw: {missing}")
    return files


def _raw_rows(files: list[Path], names: set[str]) -> list[RawRow]:
    out = []
    for path in files:
        with path.open(newline="", encoding="utf-8") as fh:
            rd = csv.reader(fh)
            next(rd)
            for line_no, row in enumerate(rd, start=2):
                if row and row[0] in names:
                    out.append(RawRow(row[0], row[1], row[2], row[3:], line_no))
    return out


def _schema_ready(conn) -> bool:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {SCHEMA}.EVENT").fetchval()) > 0
    except Exception:
        return False


def test_sql_matches_oracle_on_real_up_slice():
    with connect() as conn:
        if not _schema_ready(conn):
            pytest.skip(f"{SCHEMA} not built (run scripts\\load.ps1)")
        files = _readings_files(conn)
        # deterministic: Lucknow's Alambagh monitor plus the in-scope locations with the most events
        names = [r[0] for r in conn.execute(
            f"""SELECT l.SOURCE_NAME, COUNT(*) FROM {SCHEMA}.EVENT e
                JOIN {SCHEMA}.LOCATION l ON l.LOCATION_ID = e.LOCATION_ID
                GROUP BY l.SOURCE_NAME ORDER BY 2 DESC, 1 LIMIT {SLICE_SIZE - 1}""").fetchall()]
        if "Alambagh- Lucknow" not in names:
            names.append("Alambagh- Lucknow")
        sql = fetch_sql(conn, SCHEMA, names)
    ref = oracle_as_comparable(run(_raw_rows(files, set(names)), params_from_yaml(), "%d-%m-%Y"))
    problems = diff(sql, ref)
    print(f"files={len(files)} locations={names} events SQL={len(sql['events'])} oracle={len(ref['events'])} "
          f"days={len(ref['daily'])} months={len(ref['monthly'])}")
    assert len(ref["events"]) > 0, "slice must contain events to be meaningful"
    assert not problems, "\n".join(problems[:40])


def test_coincidence_sql_matches_oracle_on_two_real_districts():
    """R-19..R-21 on real data: every location of the two districts with the most coincident pairs."""
    co = yaml.safe_load((REPO_ROOT / "config" / "method.yaml").read_text(encoding="utf-8"))["coincidence"]
    with connect() as conn:
        if not _schema_ready(conn):
            pytest.skip(f"{SCHEMA} not built (run scripts\\load.ps1)")
        files = _readings_files(conn)
        districts = [r[0] for r in conn.execute(
            f"SELECT DISTRICT FROM {SCHEMA}.COINCIDENT_PAIR GROUP BY DISTRICT ORDER BY COUNT(*) DESC, 1 LIMIT 2"
        ).fetchall()]
        locs = dict(conn.execute(
            f"""SELECT l.SOURCE_NAME, l.DISTRICT FROM {SCHEMA}.LOCATION l
                JOIN {SCHEMA}.MONITOR_WINDOW w ON w.LOCATION_ID = l.LOCATION_ID
                WHERE l.DISTRICT IN ({{d}})""", {"d": districts}).fetchall())
        sql = fetch_coincidence(conn, SCHEMA, districts)
        # every name, so the location order (LOCATION_ID = rank of the source name) matches the SQL
        all_names = dict(conn.execute(f"SELECT SOURCE_NAME, DISTRICT FROM {SCHEMA}.LOCATION").fetchall())
    ref_all = oracle_as_comparable(run(_raw_rows(files, set(locs)), params_from_yaml(), "%d-%m-%Y"))
    comparable = {k for k, v in ref_all["monthly"].items() if v["comparable"]}
    ref = oracle_coincidence(ref_all["events"], all_names, co["max_start_offset_minutes"], co["min_overlap_minutes"],
                             co["baseline_shifts"], comparable=comparable,
                             comparable_only=bool(co["baseline_comparable_only"]))
    problems = diff_coincidence(sql, ref)
    print(f"districts={districts} locations={len(locs)} pairs SQL={len(sql['pairs'])} oracle={len(ref['pairs'])} "
          f"groups={len(sql['groups'])} baseline rows={len(sql['baseline'])}")
    assert len(ref["pairs"]) > 0
    assert not problems, "\n".join(problems[:40])


def test_coincidence_diff_detects_a_missing_pair():
    a = {"pairs": {("x", 1, "y", 2)}, "groups": {}, "baseline": {}}
    b = {"pairs": set(), "groups": {}, "baseline": {}}
    assert any("[R-19]" in p for p in diff_coincidence(a, b))
