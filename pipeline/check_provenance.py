"""Check that RUN_LOG (session id, statement id) pairs resolve to the same SQL text in Exasol's audit log.

For each RUN_LOG row, find EXA_DBA_AUDIT_SQL by (SESSION_ID, STMT_ID) and compare the SHA-256 of the
whitespace-normalised SQL text with RUN_LOG.STMT_SHA256 (computed by the runner on the exact text it sent).

    .venv\\Scripts\\python.exe -m pipeline.check_provenance VOLTPROOF
"""

from __future__ import annotations

import hashlib
import sys

from pipeline.db import DEFAULT_SCHEMA, connect


def verify(schema: str) -> dict:
    """The same check without printing: {'matches': n, 'different': n, 'missing': n}. Runs as the deployment's
    database user, which can read the audit log."""
    with connect() as c:
        c.execute("FLUSH STATISTICS")
        rows = c.execute(
            f"SELECT r.STMT_SHA256, a.SQL_TEXT FROM {schema}.RUN_LOG r LEFT JOIN EXA_DBA_AUDIT_SQL a "
            f"ON a.SESSION_ID = r.EXA_SESSION_ID AND a.STMT_ID = r.EXA_STMT_ID").fetchall()
    out = {"matches": 0, "different": 0, "missing": 0}
    for sha, text in rows:
        if text is None:
            out["missing"] += 1
        elif hashlib.sha256(text.encode("utf-8")).hexdigest() == sha:
            out["matches"] += 1
        else:
            out["different"] += 1
    return out


def main(schema: str) -> int:
    ok = bad = missing = 0
    with connect() as c:
        c.execute("FLUSH STATISTICS")
        rows = c.execute(
            f"SELECT r.STEP, r.STMT_INDEX, r.STMT_SHA256, r.EXA_SESSION_ID, r.EXA_STMT_ID, a.SQL_TEXT, a.COMMAND_NAME "
            f"FROM {schema}.RUN_LOG r LEFT JOIN EXA_DBA_AUDIT_SQL a "
            f"ON a.SESSION_ID = r.EXA_SESSION_ID AND a.STMT_ID = r.EXA_STMT_ID ORDER BY r.STARTED_AT"
        ).fetchall()
        for step, idx, sha, sess, stmt, text, cmd in rows:
            if text is None:
                missing += 1
                status = "NOT IN AUDIT"
            elif hashlib.sha256(text.encode("utf-8")).hexdigest() == sha:
                ok += 1
                status = "match (exact text)"
            else:
                bad += 1
                status = f"DIFFERENT text ({cmd})"
            print(f"  {step} #{int(idx)} session={sess} stmt={stmt}: {status}")
    print(f"exact matches={ok} different={bad} missing={missing}")
    return 0 if bad == 0 and missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCHEMA))
