"""G2 pass-criterion evidence: first gaps-and-islands query on real ESMI data inside Exasol, cross-checked
against the raw CSV with plain Python.

    .venv\\Scripts\\python.exe -m pipeline.g2_first_query "80 feet road- Dhule" 2018-06-16
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

from pipeline.db import DEFAULT_SCHEMA, connect

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw" / "ESMI minute-wise voltage data 2018 June-Aug.csv"

ISLANDS_SQL = """
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'classification.outage_max_v' THEN NUM_VALUE END) AS OUT_MAX,
           MAX(CASE WHEN NAME = 'classification.normal_min_v' THEN NUM_VALUE END) AS NORM_MIN,
           MAX(CASE WHEN NAME = 'classification.normal_max_v' THEN NUM_VALUE END) AS NORM_MAX
    FROM PARAMS
), S AS (
    SELECT r.TS,
           CASE WHEN r.VOLTAGE <= p.OUT_MAX THEN 'OUTAGE'
                WHEN r.VOLTAGE <  p.NORM_MIN THEN 'LOW'
                WHEN r.VOLTAGE <= p.NORM_MAX THEN 'NORMAL'
                ELSE 'HIGH' END AS ST
    FROM MINUTE_READING r
    JOIN LOCATION l ON l.LOCATION_ID = r.LOCATION_ID
    CROSS JOIN P p
    WHERE l.SOURCE_NAME = {loc} AND r.TS >= CAST({start} AS TIMESTAMP) AND r.TS < CAST({end} AS TIMESTAMP)
), C AS (
    SELECT TS, ST,
           CASE WHEN ST = LAG(ST) OVER (ORDER BY TS)
                 AND MINUTES_BETWEEN(TS, LAG(TS) OVER (ORDER BY TS)) = 1
                THEN 0 ELSE 1 END AS IS_NEW
    FROM S
), I AS (
    SELECT TS, ST, SUM(IS_NEW) OVER (ORDER BY TS ROWS UNBOUNDED PRECEDING) AS ISLAND
    FROM C
)
SELECT ISLAND, ST, MIN(TS) AS START_TS, MAX(TS) AS END_TS, COUNT(*) AS MINUTES
FROM I
GROUP BY ISLAND, ST
ORDER BY ISLAND
"""


def python_islands(location: str, day: dt.date):
    """Independent check from the raw CSV (no shared code with the SQL)."""
    minutes = {}
    with RAW.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[0] != location:
                continue
            d = dt.datetime.strptime(row[1], "%d-%m-%Y").date()
            if d != day:
                continue
            for i, v in enumerate(row[3:]):
                minutes[dt.datetime.combine(d, dt.time(int(row[2]), i))] = int(v)

    def st(v):
        return "OUTAGE" if v <= 130 else "LOW" if v < 205 else "NORMAL" if v <= 270 else "HIGH"

    islands = []
    prev = None
    for ts in sorted(minutes):
        s = st(minutes[ts])
        if islands and prev is not None and s == islands[-1][0] and (ts - prev) == dt.timedelta(minutes=1):
            islands[-1][2] = ts
            islands[-1][3] += 1
        else:
            islands.append([s, ts, ts, 1])
        prev = ts
    return islands


def main(location: str, day_str: str) -> int:
    day = dt.date.fromisoformat(day_str)
    start = dt.datetime.combine(day, dt.time())
    end = start + dt.timedelta(days=1)
    with connect(schema=DEFAULT_SCHEMA) as c:
        rows = c.execute(ISLANDS_SQL, {"loc": location, "start": f"{start:%Y-%m-%d %H:%M:%S}",
                                       "end": f"{end:%Y-%m-%d %H:%M:%S}"}).fetchall()
        session = c.session_id()
    print(f"Exasol islands for {location} on {day} (session {session}):")
    for isl, s, a, b, n in rows:
        print(f"  #{int(isl):<3} {s:<7} {a} -> {b}  {int(n):>4} min")
    ref = python_islands(location, day)
    sql_cmp = [(s, str(a)[:19], str(b)[:19], int(n)) for _, s, a, b, n in rows]
    py_cmp = [(s, a.strftime("%Y-%m-%d %H:%M:%S"), b.strftime("%Y-%m-%d %H:%M:%S"), n) for s, a, b, n in ref]
    same = sql_cmp == py_cmp
    print(f"independent raw-CSV check: {len(py_cmp)} islands, identical to Exasol result: {same}")
    if not same:
        for x, y in zip(sql_cmp, py_cmp):
            if x != y:
                print("  first difference:", x, "vs", y)
                break
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
