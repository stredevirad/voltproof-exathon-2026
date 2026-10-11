"""Property-based differential test (spec 9.2): random raw ESMI-like inputs, SQL pipeline in Exasol vs the
independent oracle, exact equality of events, daily and monthly results for every location.

Each Hypothesis example is a batch of several locations (loaded once, pipeline run once) to keep the
number of database round trips manageable. Inputs deliberately include boundary voltages, blank and
malformed cells, missing hours, midnight/month crossings, and duplicate or conflicting hours split
across two files.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipeline.db import connect
from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER, load_paths
from pipeline.run_sql import resolve_steps, run_steps
from tests.oracle.reference import RawRow, run
from tests.support.compare import diff, fetch_sql, oracle_as_comparable, params_from_yaml

pytestmark = pytest.mark.exasol
SCHEMA = "VP_HYPO"
BOUNDARY = ["0", "1", "99", "101", "129", "130", "131", "150", "204", "205", "230", "245", "270", "271",
            "300", "350", "364"]


@st.composite
def cell_runs(draw):
    """60 cells built from a few runs of one value (realistic) plus rare blank/malformed cells."""
    cells: list[str] = []
    while len(cells) < 60:
        v = draw(st.sampled_from(BOUNDARY))
        n = draw(st.integers(1, 25))
        cells.extend([v] * n)
    cells = cells[:60]
    for _ in range(draw(st.integers(0, 3))):
        i = draw(st.integers(0, 59))
        cells[i] = draw(st.sampled_from(["", "", "", "abc", "-1"]))
    return cells


@st.composite
def batch(draw):
    n_loc = draw(st.integers(2, 5))
    rows, locs = [], []
    for li in range(n_loc):
        name = f"HYP L{li}"
        locs.append((name, f"HYP D{draw(st.integers(0, 1))}"))
        start = dt.datetime(2018, 6, 30, 0) + dt.timedelta(hours=draw(st.integers(-30, 30)))
        n_hours = draw(st.integers(1, 30))
        for h in range(n_hours):
            if draw(st.integers(0, 9)) < 2:      # ~20% of hours missing
                continue
            ts = start + dt.timedelta(hours=h)
            cells = draw(cell_runs())
            rows.append([name, ts.strftime("%d-%m-%Y"), str(ts.hour)] + cells)
            r = draw(st.integers(0, 9))
            if r == 0:                            # identical duplicate hour
                rows.append(list(rows[-1]))
            elif r == 1:                          # conflicting duplicate hour
                alt = list(rows[-1])
                j = 3 + draw(st.integers(0, 59))
                alt[j] = "231" if alt[j] != "231" else "232"
                rows.append(alt)
    params = {
        "events.gap_bridge_max_minutes": draw(st.sampled_from([0, 0, 2, 5])),
        "events.max_uncertain_extension_minutes": draw(st.sampled_from([60, 30, 7])),
        "events.interruption_min_minutes": draw(st.sampled_from([1, 2])),
    }
    split = draw(st.integers(0, max(len(rows), 1)))
    return locs, rows, params, split


def _write(path: Path, header: list[str], rows: list[list[str]]):
    path.write_bytes(("\r\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\r\n").encode())


MAX_EXAMPLES = int(__import__("os").environ.get("VOLTPROOF_HYPOTHESIS_EXAMPLES", "12"))
STATS = Path(__file__).resolve().parents[2] / "reports" / "hypothesis_stats.jsonl"


@settings(max_examples=MAX_EXAMPLES, deadline=None,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
@given(batch())
def test_sql_equals_oracle_on_random_batches(b):
    locs, rows, params, split = b
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        lp, r1, r2 = td / "loc.csv", td / "r1.csv", td / "r2.csv"
        _write(lp, LOCATIONS_HEADER,
               [[n, "01-01-2018", "31-12-2018", d, "Hypothesis State", "Gram Panchayat", "Domestic"] for n, d in locs])
        _write(r1, READINGS_HEADER, rows[:split])
        _write(r2, READINGS_HEADER, rows[split:])
        with connect(autocommit=False) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            conn.commit()
            load_paths(conn, SCHEMA, [(8_000_001, lp, "locations"), (8_000_002, r1, "readings"),
                                      (8_000_003, r2, "readings")])
            run_steps(conn, SCHEMA, resolve_steps(["020", "030", "040", "050", "060", "070", "080", "090"]),
                      params_override=dict({"subset.states": "", "subset.locations": ""}, **params), quiet=True)
            sql = fetch_sql(conn, SCHEMA)
        raw = [RawRow(r[0], r[1], r[2], r[3:], i) for i, r in enumerate(rows)]
        ref = oracle_as_comparable(run(raw, params_from_yaml(params), "%d-%m-%Y"))
    problems = diff(sql, ref)
    STATS.parent.mkdir(parents=True, exist_ok=True)
    with STATS.open("a", encoding="utf-8") as fh:  # evidence that examples are not trivial
        fh.write(json.dumps({"rows": len(rows), "locations": len(locs), "events": len(ref["events"]),
                             "bridged_events": sum(1 for e in ref["events"] if e["bridged_minutes"]),
                             "bounded_edges": sum((e["start_certainty"] == "bounded") + (e["end_certainty"] == "bounded")
                                                  for e in ref["events"]),
                             "days": len(ref["daily"]), "months": len(ref["monthly"]), "params": params,
                             "match": not problems}) + "\n")
    assert not problems, json.dumps(params) + "\n" + "\n".join(problems[:30])
