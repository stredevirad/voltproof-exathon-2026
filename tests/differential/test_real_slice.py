"""Differential tests on REAL data: the Exasol SQL pipeline vs the independent oracle.

Precondition: the production schema VOLTPROOF has been built from data/raw with the default
config/method.yaml (scripts\\load.ps1). The oracle reads, by itself, the raw CSV lines of the chosen
locations from EVERY readings file recorded in VOLTPROOF.SOURCE_FILE, so the comparison covers exactly the
same data as the SQL whatever subset (first / up / all) was loaded. The coincidence comparison covers June-August
2018 only (D-034), so its oracle fits in memory on a 16 GB laptop.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from pipeline.db import DEFAULT_SCHEMA, connect
from tests.oracle.reference import RawRow, run
from tests.support.compare import (
    diff,
    diff_coincidence,
    fetch_coincidence,
    fetch_sql,
    oracle_as_comparable,
    oracle_coincidence,
    params_from_yaml,
)

pytestmark = pytest.mark.exasol

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
SCHEMA = DEFAULT_SCHEMA
SLICE_SIZE = 4


def _readings_files(conn) -> list[tuple[Path, dict | None]]:
    from pipeline.load_raw import declared_periods

    declared = declared_periods()
    rows = conn.execute(
        f"SELECT FILE_ID, FILE_NAME FROM {SCHEMA}.SOURCE_FILE WHERE FILE_KIND = 'readings' ORDER BY FILE_ID"
    ).fetchall()
    files = [(RAW_DIR / name, declared.get(int(fid))) for fid, name in rows]
    missing = [f.name for f, _ in files if not f.exists()]
    if missing:
        pytest.skip(f"raw files loaded in {SCHEMA} are not present in data/raw: {missing}")
    return files


def _raw_rows(files: list[tuple[Path, dict | None]], names: set[str]) -> list[RawRow]:
    from tests.support.rawfiles import name_matcher, read_rows

    with connect() as conn:
        all_names = {r[0] for r in conn.execute(f"SELECT SOURCE_NAME FROM {SCHEMA}.LOCATION").fetchall()}
    matcher = name_matcher(all_names)
    out = []
    for path, declared in files:
        out.extend(read_rows(path, names, declared, matcher=matcher))
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


# The coincidence comparison runs on the 2018 June-August file, the scope it was designed on (D-034): the
# oracle holds every minute of two districts in memory, and over all of 2016-2019 that needed about 8.7 GB.
# The oracle also reads one calendar day either side of the window from the neighbouring files (gap bridging
# is off), so outages that cross 1 June or 1 September start at the same minute as in the SQL, which sees
# the files as one continuous record.
WINDOW = (dt.datetime(2018, 6, 1), dt.datetime(2018, 9, 1))
CONTEXT_DAYS = (dt.date(2018, 5, 31), dt.date(2018, 9, 1))


def _raw_rows_window(files: list[tuple[Path, dict | None]], names: set[str]) -> list[RawRow]:
    from tests.support.rawfiles import name_matcher, read_rows_window

    first, last = CONTEXT_DAYS
    with connect() as conn:
        all_names = {r[0] for r in conn.execute(f"SELECT SOURCE_NAME FROM {SCHEMA}.LOCATION").fetchall()}
    matcher = name_matcher(all_names)
    out = []
    for path, declared in files:
        if declared and declared.get("period_from") and declared.get("period_to") and (
                str(declared["period_to"]) < str(first) or str(declared["period_from"]) > str(last)):
            continue  # the file's declared period lies outside the window and its context days
        out.extend(read_rows_window(path, names, first, last, declared, matcher=matcher))
    return out


def _in_window(c: dict) -> dict:
    """Pairs with both starts, groups whose first member starts, and baseline months, inside WINDOW."""
    w0, w1 = WINDOW
    months = {f"2018-{m:02d}" for m in range(w0.month, w1.month)}
    return {"pairs": {p for p in c["pairs"] if w0 <= p[1] < w1 and w0 <= p[3] < w1},
            "groups": {k: v for k, v in c["groups"].items() if w0 <= k[1] < w1},
            "baseline": {k: v for k, v in c["baseline"].items() if k[1] in months}}


def test_coincidence_sql_matches_oracle_on_two_real_districts():
    """R-19..R-21 on real data, June-August 2018: every location of the two districts with the most coincident
    pairs in that window."""
    co = yaml.safe_load((REPO_ROOT / "config" / "method.yaml").read_text(encoding="utf-8"))["coincidence"]
    w0, w1 = WINDOW
    with connect() as conn:
        if not _schema_ready(conn):
            pytest.skip(f"{SCHEMA} not built (run scripts\\load.ps1)")
        files = _readings_files(conn)
        districts = [r[0] for r in conn.execute(
            f"""SELECT DISTRICT FROM {SCHEMA}.COINCIDENT_PAIR
                WHERE START_A >= {{w0}} AND START_A < {{w1}} AND START_B >= {{w0}} AND START_B < {{w1}}
                GROUP BY DISTRICT ORDER BY COUNT(*) DESC, 1 LIMIT 2""",
            {"w0": f"{w0:%Y-%m-%d %H:%M:%S}", "w1": f"{w1:%Y-%m-%d %H:%M:%S}"}).fetchall()]
        if not districts:
            pytest.skip(f"{SCHEMA} has no coincident pairs in June-August 2018 (that data is not loaded)")
        locs = dict(conn.execute(
            f"""SELECT l.SOURCE_NAME, l.DISTRICT FROM {SCHEMA}.LOCATION l
                JOIN {SCHEMA}.MONITOR_WINDOW w ON w.LOCATION_ID = l.LOCATION_ID
                WHERE l.DISTRICT IN ({{d}})""", {"d": districts}).fetchall())
        sql = _in_window(fetch_coincidence(conn, SCHEMA, districts))
        # every name, so the location order (LOCATION_ID = rank of the source name) matches the SQL
        all_names = dict(conn.execute(f"SELECT SOURCE_NAME, DISTRICT FROM {SCHEMA}.LOCATION").fetchall())
    ref_all = oracle_as_comparable(run(_raw_rows_window(files, set(locs)), params_from_yaml(), "%d-%m-%Y"))
    comparable = {k for k, v in ref_all["monthly"].items() if v["comparable"]}
    ref = _in_window(oracle_coincidence(ref_all["events"], all_names, co["max_start_offset_minutes"],
                                        co["min_overlap_minutes"], co["baseline_shifts"], comparable=comparable,
                                        comparable_only=bool(co["baseline_comparable_only"])))
    problems = diff_coincidence(sql, ref)
    print(f"districts={districts} locations={len(locs)} pairs SQL={len(sql['pairs'])} oracle={len(ref['pairs'])} "
          f"groups={len(sql['groups'])} baseline rows={len(sql['baseline'])}")
    assert len(ref["pairs"]) > 0
    assert not problems, "\n".join(problems[:40])


def test_coincidence_diff_detects_a_missing_pair():
    a = {"pairs": {("x", 1, "y", 2)}, "groups": {}, "baseline": {}}
    b = {"pairs": set(), "groups": {}, "baseline": {}}
    assert any("[R-19]" in p for p in diff_coincidence(a, b))
