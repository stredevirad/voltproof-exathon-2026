"""Differential test on REAL data: the Exasol SQL pipeline vs the independent oracle, for a slice of
Uttar Pradesh locations from the 2018 June-Aug file.

Precondition: the production schema VOLTPROOF has been built from data/raw with the default
config/method.yaml (scripts\\load.ps1). The test reads the same raw CSV rows itself (plain Python) and
recomputes everything with tests/oracle/reference.py.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.db import connect
from tests.oracle.reference import RawRow, run
from tests.support.compare import diff, fetch_sql, oracle_as_comparable, params_from_yaml

pytestmark = pytest.mark.exasol

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw" / "ESMI minute-wise voltage data 2018 June-Aug.csv"
SCHEMA = "VOLTPROOF"
SLICE_SIZE = 4


def _pick_locations(conn) -> list[str]:
    # deterministic: Lucknow's Alambagh monitor plus the UP locations with the most events
    rows = conn.execute(
        f"""SELECT l.SOURCE_NAME, COUNT(*) FROM {SCHEMA}.EVENT e
            JOIN {SCHEMA}.LOCATION l ON l.LOCATION_ID = e.LOCATION_ID
            GROUP BY l.SOURCE_NAME ORDER BY 2 DESC, 1 LIMIT {SLICE_SIZE - 1}""").fetchall()
    names = [r[0] for r in rows]
    if "Alambagh- Lucknow" not in names:
        names.append("Alambagh- Lucknow")
    return names


def _raw_rows(names: set[str]) -> list[RawRow]:
    out = []
    with RAW.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for line_no, row in enumerate(rd, start=2):
            if row[0] in names:
                out.append(RawRow(row[0], row[1], row[2], row[3:], line_no))
    return out


@pytest.mark.skipif(not RAW.exists(), reason="real data file not downloaded (data/raw)")
def test_coincidence_sql_matches_oracle_on_two_real_districts():
    """R-19..R-21 on real data: every location of the two districts with the most coincident pairs."""
    import yaml

    from tests.support.compare import diff_coincidence, fetch_coincidence, oracle_coincidence

    co = yaml.safe_load((REPO_ROOT / "config" / "method.yaml").read_text(encoding="utf-8"))["coincidence"]
    with connect() as conn:
        districts = [r[0] for r in conn.execute(
            f"SELECT DISTRICT FROM {SCHEMA}.COINCIDENT_PAIR GROUP BY DISTRICT ORDER BY COUNT(*) DESC, 1 LIMIT 2"
        ).fetchall()]
        locs = dict(conn.execute(
            f"""SELECT l.SOURCE_NAME, l.DISTRICT FROM {SCHEMA}.LOCATION l
                JOIN {SCHEMA}.MONITOR_WINDOW w ON w.LOCATION_ID = l.LOCATION_ID
                WHERE l.DISTRICT IN ({{d}})""", {"d": districts}).fetchall())
        sql = fetch_coincidence(conn, SCHEMA, districts)
        # district_of must cover every name so the location order (LOCATION_ID = rank of name) matches
        all_names = dict(conn.execute(f"SELECT SOURCE_NAME, DISTRICT FROM {SCHEMA}.LOCATION").fetchall())
    ref_events = oracle_as_comparable(run(_raw_rows(set(locs)), params_from_yaml(), "%d-%m-%Y"))["events"]
    ref = oracle_coincidence(ref_events, all_names, co["max_start_offset_minutes"], co["min_overlap_minutes"],
                             co["baseline_shifts"])
    problems = diff_coincidence(sql, ref)
    print(f"districts={districts} locations={len(locs)} pairs SQL={len(sql['pairs'])} oracle={len(ref['pairs'])} "
          f"groups={len(sql['groups'])} baseline rows={len(sql['baseline'])}")
    assert len(ref["pairs"]) > 0
    assert not problems, "\n".join(problems[:40])


def test_coincidence_diff_detects_a_missing_pair():
    from tests.support.compare import diff_coincidence

    a = {"pairs": {("x", 1, "y", 2)}, "groups": {}, "baseline": {}}
    b = {"pairs": set(), "groups": {}, "baseline": {}}
    assert any("[R-19]" in p for p in diff_coincidence(a, b))


@pytest.mark.skipif(not RAW.exists(), reason="real data file not downloaded (data/raw)")
def test_sql_matches_oracle_on_real_up_slice():
    with connect() as conn:
        names = _pick_locations(conn)
        sql = fetch_sql(conn, SCHEMA, names)
    ref = oracle_as_comparable(run(_raw_rows(set(names)), params_from_yaml(), "%d-%m-%Y"))
    problems = diff(sql, ref)
    summary = (f"locations={names} events SQL={len(sql['events'])} oracle={len(ref['events'])} "
               f"days={len(ref['daily'])} months={len(ref['monthly'])}")
    print(summary)
    assert len(ref["events"]) > 0, "slice must contain events to be meaningful"
    assert not problems, summary + "\n" + "\n".join(problems[:40])
