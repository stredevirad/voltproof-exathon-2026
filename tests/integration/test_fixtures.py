"""Hand-written fixtures through the real pipeline in Exasol (load_raw -> SQL 020..090).

For every fixture: (1) each hand-derived expectation in its YAML must hold, and (2) the complete SQL
output for its locations must equal the independent oracle. Fixtures are grouped by parameter
overrides; each group is built in its own schema VP_TEST_<n>.
Coincidence expectations (R-19..R-21, fixtures F13/F14) are asserted by the G4 tests.
"""

from __future__ import annotations

import csv
import datetime as dt
import json

import pytest

from pipeline.db import connect
from pipeline.load_raw import load_paths
from pipeline.run_sql import resolve_steps, run_steps
from tests.fixtures.render import all_specs, render
from tests.oracle.reference import RawRow, run
from tests.support.compare import (diff, diff_coincidence, fetch_coincidence, fetch_sql, oracle_as_comparable,
                                   oracle_coincidence, params_from_yaml)

pytestmark = pytest.mark.exasol

SPECS = all_specs()
COINC = __import__("yaml").safe_load(
    (__import__("pathlib").Path(__file__).resolve().parents[2] / "config" / "method.yaml").read_text(encoding="utf-8")
)["coincidence"]
BASE_OVERRIDES = {"subset.states": "", "subset.locations": ""}


def _groups():
    groups: dict[str, list[dict]] = {}
    for s in SPECS:
        groups.setdefault(json.dumps(s.get("params") or {}, sort_keys=True), []).append(s)
    return list(groups.items())


def _oracle_rows(readings_path, known_locations: set[str]) -> list[RawRow]:
    rows = []
    with readings_path.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for line_no, r in enumerate(rd, start=2):
            if r[0] in known_locations:  # unknown locations are quarantined by R-2
                rows.append(RawRow(r[0], r[1], r[2], r[3:], line_no))
    return rows


@pytest.fixture(scope="session")
def built():
    """Build every parameter group once; return per-fixture SQL results, oracle results and quality."""
    out = {}
    with connect(autocommit=False) as conn:
        for gi, (pkey, specs) in enumerate(_groups(), start=1):
            schema = f"VP_TEST_{gi}"
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            conn.commit()
            files, rendered = [], {}
            for si, s in enumerate(specs):
                lp, rp = render(s)
                rendered[s["id"]] = (lp, rp)
                base = 9_000_000 + (gi * 100 + si) * 10
                files += [(base + 1, lp, "locations"), (base + 2, rp, "readings")]
            load_paths(conn, schema, files)
            overrides = dict(BASE_OVERRIDES, **json.loads(pkey))
            run_steps(conn, schema, resolve_steps(["020", "030", "040", "050", "060", "070", "080", "090", "100"]),
                      params_override=overrides, quiet=True)
            all_districts = {loc["name"]: loc["district"] for s2 in specs for loc in s2["locations"]}
            for si, s in enumerate(specs):
                names = [loc["name"] for loc in s["locations"]]
                base = 9_000_000 + (gi * 100 + si) * 10
                sql = fetch_sql(conn, schema, names)
                oracle = oracle_as_comparable(
                    run(_oracle_rows(rendered[s["id"]][1], set(names)), params_from_yaml(json.loads(pkey)),
                        "%d-%m-%Y"))
                districts = sorted({loc["district"] for loc in s["locations"]})
                co_sql = fetch_coincidence(conn, schema, districts)
                fparams = json.loads(pkey)
                comparable = {k for k, v in oracle["monthly"].items() if v["comparable"]}
                co_ref = oracle_coincidence(
                    oracle["events"], all_districts, COINC["max_start_offset_minutes"], COINC["min_overlap_minutes"],
                    COINC["baseline_shifts"], comparable=comparable,
                    comparable_only=bool(fparams.get("coincidence.baseline_comparable_only",
                                                     COINC["baseline_comparable_only"])))
                q = {
                    "duplicate_minutes": dict(conn.execute(
                        f"SELECT l.SOURCE_NAME, SUM(c.DUPLICATE_COUNT) FROM {schema}.READING_CLEAN c "
                        f"JOIN {schema}.LOCATION l ON l.LOCATION_ID = c.LOCATION_ID "
                        f"WHERE l.SOURCE_NAME IN ({{n}}) GROUP BY 1", {"n": names}).fetchall()),
                    "conflict_minutes": dict(conn.execute(
                        f"SELECT l.SOURCE_NAME, COUNT(*) FROM {schema}.READING_CONFLICT c "
                        f"JOIN {schema}.LOCATION l ON l.LOCATION_ID = c.LOCATION_ID "
                        f"WHERE l.SOURCE_NAME IN ({{n}}) GROUP BY 1", {"n": names}).fetchall()),
                    "value_quarantine": dict(conn.execute(
                        f"SELECT REASON, COUNT(*) FROM {schema}.VALUE_QUARANTINE "
                        f"WHERE FILE_ID = {base + 2} GROUP BY 1").fetchall()),
                    "row_quarantine": dict(conn.execute(
                        f"SELECT REASON, COUNT(*) FROM {schema}.ROW_QUARANTINE "
                        f"WHERE FILE_ID = {base + 2} GROUP BY 1").fetchall()),
                }
                out[s["id"]] = {"spec": s, "sql": sql, "oracle": oracle, "quality": q,
                                "co_sql": co_sql, "co_ref": co_ref}
    return out


def _ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")


def check_expectations(b: dict) -> list[str]:
    """Compare one fixture's hand-written expectations with the SQL results; return the problems."""
    exp = b["spec"].get("expected", {})
    sql = b["sql"]
    problems = []
    for loc, n in (exp.get("events_count") or {}).items():
        got = sum(1 for e in sql["events"] if e["location"] == loc)
        if got != n:
            problems.append(f"[R-7] {loc}: {got} events, expected {n}")
    by_key = {(e["location"], e["start"]): e for e in sql["events"]}
    for e in exp.get("events", []):
        got = by_key.get((e["loc"], _ts(e["start"])))
        if got is None:
            problems.append(f"[R-7] missing event {e['loc']} {e['start']} ({e.get('why')})")
            continue
        if got["end"] != _ts(e["end"]):
            problems.append(f"[R-7] {e['loc']} {e['start']} end {got['end']} != {e['end']}")
        for f in ("min_duration", "max_duration", "bridged_minutes", "start_certainty", "end_certainty",
                  "is_interruption", "zero_minutes"):
            if f in e and got[f] != e[f]:
                problems.append(f"{e['loc']} {e['start']} {f}: SQL={got[f]!r} expected={e[f]!r} ({e.get('why')})")
    for d in exp.get("daily", []):
        row = sql["daily"].get((d["loc"], d["day"] if isinstance(d["day"], dt.date) else dt.date.fromisoformat(d["day"])))
        if row is None:
            problems.append(f"[R-12] missing daily row {d['loc']} {d['day']}")
            continue
        for f, v in d.items():
            if f in ("loc", "day", "why"):
                continue
            if row[f] != v:
                problems.append(f"daily {d['loc']} {d['day']} {f}: SQL={row[f]} expected={v} ({d.get('why')})")
    for m in exp.get("monthly", []):
        row = sql["monthly"].get((m["loc"], m["month"]))
        if row is None:
            problems.append(f"[R-12] missing monthly row {m['loc']} {m['month']}")
            continue
        for f, v in m.items():
            if f in ("loc", "month", "why"):
                continue
            if row[f] != v:
                problems.append(f"monthly {m['loc']} {m['month']} {f}: SQL={row[f]} expected={v} ({m.get('why')})")
    q = exp.get("quality") or {}
    for key in ("duplicate_minutes", "conflict_minutes", "value_quarantine", "row_quarantine"):
        for k, v in (q.get(key) or {}).items():
            got = int(b["quality"][key].get(k, 0))
            if got != v:
                problems.append(f"[R-2/R-3] {key}[{k}] SQL={got} expected={v}")
    return problems


@pytest.mark.parametrize("fid", [s["id"] for s in SPECS])
def test_fixture_expectations(built, fid):
    problems = check_expectations(built[fid])
    assert not problems, "\n".join(problems)


def test_harness_detects_a_wrong_expectation(built):
    """Sensitivity check: perturbing one expected value must produce exactly that reported problem."""
    import copy
    b = copy.deepcopy(built["F05_gaps_bounds"])
    b["spec"]["expected"]["daily"][0]["outage_upper"] += 1
    problems = check_expectations(b)
    assert len(problems) == 1 and "outage_upper" in problems[0], problems
    b = copy.deepcopy(built["F07_bridging"])
    b["spec"]["expected"]["events"][0]["bridged_minutes"] = 0
    assert any("bridged_minutes" in p for p in check_expectations(b))


@pytest.mark.parametrize("fid", [s["id"] for s in SPECS if {"coincidence", "baseline", "baseline_absent"}
                                 & set(s.get("expected", {}))])
def test_coincidence_expectations(built, fid):
    b = built[fid]
    exp = b["spec"]["expected"]
    co = b["co_sql"]
    problems = []
    c = exp.get("coincidence")
    if c:
        want_pairs = {(p["a"], _ts(p["a_start"]), p["b"], _ts(p["b_start"])) for p in c["pairs"]}
        if co["pairs"] != want_pairs:
            problems.append(f"[R-19] pairs SQL={sorted(co['pairs'])} expected={sorted(want_pairs)}")
        for p in c.get("not_pairs", []):
            k1 = (p["a"], _ts(p["a_start"]), p["b"], _ts(p["b_start"]))
            k2 = (p["b"], _ts(p["b_start"]), p["a"], _ts(p["a_start"]))
            if k1 in co["pairs"] or k2 in co["pairs"]:
                problems.append(f"[R-19] unexpected pair {k1} ({p['why']})")
        want_groups = {(g["district"], _ts(g["start"])): frozenset((m["loc"], _ts(m["start"])) for m in g["members"])
                       for g in c["groups"]}
        if co["groups"] != want_groups:
            problems.append(f"[R-20] groups SQL={co['groups']} expected={want_groups}")
    for bl in exp.get("baseline_absent", []):
        if (bl["district"], bl["month"]) in co["baseline"]:
            problems.append(f"[R-21] baseline row present for {bl['district']} {bl['month']} ({bl['why']})")
    for bl in exp.get("baseline", []):
        got = co["baseline"].get((bl["district"], bl["month"]))
        want = (bl["observed_pairs"], round(bl["expected_pairs"], 6), round(bl["p_value"], 6))
        if got is None or (got[2], got[3], got[4]) != want:
            problems.append(f"[R-21] baseline {bl['district']} {bl['month']}: SQL={got} expected "
                            f"(observed, expected, p)={want}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("fid", [s["id"] for s in SPECS])
def test_coincidence_sql_equals_oracle(built, fid):
    problems = diff_coincidence(built[fid]["co_sql"], built[fid]["co_ref"])
    assert not problems, "\n".join(problems[:40])


def test_oracle_diff_detects_a_changed_event(built):
    import copy
    b = copy.deepcopy(built["F02_single_interruptions"])
    b["oracle"]["events"][0]["max_duration"] += 1
    assert any("[R-10]" in p for p in diff(b["sql"], b["oracle"]))


@pytest.mark.parametrize("fid", [s["id"] for s in SPECS])
def test_fixture_sql_equals_oracle(built, fid):
    b = built[fid]
    problems = diff(b["sql"], b["oracle"])
    assert not problems, "\n".join(problems[:40])
