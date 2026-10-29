"""Keep Exasol's own measurements of every recorded build statement next to the results: table RUN_STATS.

For each RUN_LOG row, EXA_DBA_AUDIT_SQL (matched by session id and statement id, as in check_provenance.py) holds
the statement's DURATION in seconds and, where the column exists, TEMP_DB_RAM_PEAK in MiB, both measured by the
database. RUN_STATS copies them in one SQL statement, so the app and reports can show "measured by Exasol" timings.
It is additive: RUN_LOG and every result table stay unchanged. A statement missing from the audit log keeps NULLs.
Runs as the deployment's database user (it can read the audit log), also for upload schemas.

    .venv\\Scripts\\python.exe -m pipeline.run_stats VOLTPROOF
"""

from __future__ import annotations

import sys

from pipeline.db import DEFAULT_SCHEMA, connect

TABLE = "RUN_STATS"


def record(schema: str) -> int:
    """(Re)create <schema>.RUN_STATS from RUN_LOG and the audit log; returns its row count."""
    schema = schema.upper()
    with connect() as c:
        c.execute("FLUSH STATISTICS")  # the audit log is written in the background; flush it before reading
        cols = set(c.execute("SELECT * FROM EXA_DBA_AUDIT_SQL LIMIT 0").columns())
        ram = "a.TEMP_DB_RAM_PEAK" if "TEMP_DB_RAM_PEAK" in cols else "CAST(NULL AS DECIMAL(10,1))"
        c.execute(f"""CREATE OR REPLACE TABLE {schema}.{TABLE} AS
            SELECT r.RUN_ID, r.STEP, r.STMT_INDEX, r.EXA_SESSION_ID, r.EXA_STMT_ID,
                   a.DURATION AS EXA_DURATION_S, {ram} AS EXA_TEMP_DB_RAM_PEAK_MIB
            FROM {schema}.RUN_LOG r
            LEFT JOIN EXA_DBA_AUDIT_SQL a ON a.SESSION_ID = r.EXA_SESSION_ID AND a.STMT_ID = r.EXA_STMT_ID""")
        return int(c.execute(f"SELECT COUNT(*) FROM {schema}.{TABLE}").fetchval())


def main(schema: str) -> int:
    n = record(schema)
    print(f"{schema.upper()}.{TABLE}: {n} statements with Exasol's measured duration and temporary-memory peak")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCHEMA))
