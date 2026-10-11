"""G2 feature probes against the local Exasol Personal deployment.

Each probe runs a tiny, self-checking SQL statement and records supported / not supported / error with
the evidence (result or error text). Output: reports/exasol_probes.json and a printed table.

    .venv\\Scripts\\python.exe -m pipeline.probe_exasol
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from pipeline.db import conn_info, connect

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "reports" / "exasol_probes.json"
SCHEMA = "VP_PROBE"

PROBES: list[tuple[str, list[str], str, object]] = [
    # (name, setup statements, query, expected first row or callable check)
    (
        "window LAG/LEAD + running SUM",
        [
            f"CREATE OR REPLACE TABLE {SCHEMA}.T (LOC INT, M INT, S VARCHAR(10))",
            f"INSERT INTO {SCHEMA}.T VALUES (1,0,'N'),(1,1,'O'),(1,2,'O'),(1,3,'N'),(1,4,'O')",
        ],
        f"""SELECT COUNT(DISTINCT ISL) FROM (
              SELECT SUM(CHG) OVER (PARTITION BY LOC ORDER BY M ROWS UNBOUNDED PRECEDING) ISL FROM (
                SELECT LOC, M, CASE WHEN S = LAG(S) OVER (PARTITION BY LOC ORDER BY M) THEN 0 ELSE 1 END CHG
                FROM {SCHEMA}.T))""",
        (4,),  # islands: N | O O | N | O
    ),
    (
        "interval self-join",
        [
            f"CREATE OR REPLACE TABLE {SCHEMA}.E (ID INT, ST TIMESTAMP, EN TIMESTAMP)",
            f"""INSERT INTO {SCHEMA}.E VALUES
                (1, '2018-06-01 10:00:00', '2018-06-01 10:30:00'),
                (2, '2018-06-01 10:02:00', '2018-06-01 10:20:00'),
                (3, '2018-06-01 12:00:00', '2018-06-01 12:05:00')""",
        ],
        f"""SELECT COUNT(*) FROM {SCHEMA}.E A JOIN {SCHEMA}.E B
              ON A.ID < B.ID AND A.ST < B.EN AND B.ST < A.EN
                 AND ABS(MINUTES_BETWEEN(A.ST, B.ST)) <= 5""",
        (1,),
    ),
    (
        "GEOMETRY + ST_DISTANCE",
        [],
        "SELECT ROUND(ST_DISTANCE('POINT(0 0)', 'POINT(3 4)'), 6)",
        (5,),
    ),
    (
        "native Lua scripting (EXECUTE SCRIPT)",
        [
            f"""CREATE OR REPLACE LUA SCRIPT {SCHEMA}.HELLO() RETURNS ROWCOUNT AS
local r = query([[SELECT 41 + 1 AS X]])
exit({{rows_affected = r[1].X}})
""",
        ],
        f"EXECUTE SCRIPT {SCHEMA}.HELLO()",
        "rowcount",
    ),
    (
        "Lua scalar UDF (no SLC needed)",
        [
            f"""CREATE OR REPLACE LUA SCALAR SCRIPT {SCHEMA}.LUA_ADD(A DOUBLE) RETURNS DOUBLE AS
function run(ctx)
  return ctx.A + 1
end
""",
        ],
        f"SELECT CAST({SCHEMA}.LUA_ADD(41) AS DECIMAL(18,0))",
        (42,),
    ),
    (
        "Python3 UDF without installing an SLC",
        [
            f"""CREATE OR REPLACE PYTHON3 SCALAR SCRIPT {SCHEMA}.PY_ADD(A INT) RETURNS INT AS
def run(ctx):
    return ctx.A + 1
/
""",
        ],
        f"SELECT {SCHEMA}.PY_ADD(41)",
        (42,),
    ),
    (
        "FLUSH STATISTICS + EXA_SQL_LAST_DAY",
        ["FLUSH STATISTICS"],
        "SELECT COUNT(*) FROM EXA_SQL_LAST_DAY",
        "nonzero",
    ),
    (
        "EXA_DBA_AUDIT_SQL readable",
        [],
        "SELECT COUNT(*) FROM EXA_DBA_AUDIT_SQL",
        "any",
    ),
    (
        "auditing enabled (EXA_PARAMETERS / EXA_METADATA)",
        [],
        "SELECT PARAM_NAME, PARAM_VALUE FROM EXA_METADATA WHERE UPPER(PARAM_NAME) LIKE '%AUDIT%'",
        "show",
    ),
    (
        "script languages configured",
        [],
        "SELECT SYSTEM_VALUE FROM EXA_PARAMETERS WHERE PARAMETER_NAME = 'SCRIPT_LANGUAGES'",
        "show",
    ),
]


def run() -> int:
    info = conn_info()
    results = []
    with connect() as c:
        version = c.execute(
            "SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME = 'databaseProductVersion'"
        ).fetchval()
        c.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        for name, setup, query, expect in PROBES:
            rec = {"probe": name, "query": " ".join(query.split())}
            try:
                for s in setup:
                    c.execute(s)
                st = c.execute(query)
                if expect == "rowcount":
                    rec["result"] = st.rowcount()
                    rec["status"] = "supported" if rec["result"] == 42 else "unexpected"
                else:
                    rows = st.fetchall() if st.result_type == "resultSet" else []
                    rec["result"] = [list(map(str, r)) for r in rows[:10]]
                    if expect == "nonzero":
                        rec["status"] = "supported" if rows and int(rows[0][0]) > 0 else "unexpected"
                    elif expect in ("any", "show"):
                        rec["status"] = "supported" if expect == "any" else "observed"
                    else:
                        got = tuple(int(v) if str(v).replace(".", "", 1).isdigit() else v for v in rows[0])
                        rec["status"] = "supported" if got == expect else f"unexpected (expected {expect})"
            except Exception as e:  # record the database's own message as evidence
                rec["status"] = "error / not supported"
                msg = getattr(e, "message", None) or str(e) or repr(e)
                rec["error"] = " ".join(str(msg).split())[:400]
            results.append(rec)
        c.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        max_conn = None
        try:
            max_conn = c.execute(
                "SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME LIKE '%onnection%'"
            ).fetchall()
        except Exception as e:  # informational only
            max_conn = f"error: {e}"

    report = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dsn": info.dsn,
        "database_version": version,
        "connection_params_metadata": [list(map(str, r)) for r in max_conn] if isinstance(max_conn, list) else max_conn,
        "probes": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Exasol {version} at {info.dsn}")
    for r in results:
        detail = r.get("error") or r.get("result")
        print(f"  {r['status']:<24} {r['probe']}: {str(detail)[:140]}")
    print(f"written: {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
