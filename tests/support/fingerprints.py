"""Table fingerprints computed inside Exasol, to show that two schemas hold the same results.

Each row becomes HASH_SHA256 over its columns (length-prefixed text under fixed session formats); a table's
fingerprint is its row count plus three exact sums of 48-bit slices of the row hashes, so it does not depend on row
order. Used by the upload tests: an upload built through the upload path must equal the command-line build of the
same files in every table, apart from the columns that name the source file (file id, file name), which differ by
design (uploads use file ids 800000001+).
"""

from __future__ import annotations

NULL_MARK = "~"
FILE_COLUMNS = {"FILE_ID", "SOURCE_FILE_ID", "FILE_NAME"}
# Columns that pack the file id into a number (step 040: FILE_ID * 10^12 + LINE_NO): only the line part is compared.
PACKED_FILE_COLUMNS = {"FIRST_SOURCE"}
# Tables that describe the run or the delivered files rather than results: the run log (session ids, times) and
# Exasol's measured timings for it (RUN_STATS), the parameters (an upload adds its own dataset.* and upload.* rows)
# and the per-file load record (load time).
NOT_RESULTS = {"RUN_LOG", "RUN_STATS", "PARAMS", "SOURCE_FILE", "SOURCE_FILE_DECLARED"}


def _session_formats(conn) -> None:
    for stmt in ("ALTER SESSION SET NLS_TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS.FF6'",
                 "ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD'",
                 "ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'"):
        conn.execute(stmt)


def _col_text(name: str, ctype: str) -> str:
    q = f'"{name}"'
    if name in PACKED_FILE_COLUMNS:
        q = f"MOD({q}, 1000000000000)"
    expr = q if ctype.startswith(("VARCHAR", "CHAR")) else f"CAST({q} AS VARCHAR(2000))"
    return f"COALESCE(LENGTH({expr}) || ':' || {expr}, '{NULL_MARK}')"


def tables(conn, schema: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT TABLE_NAME FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA = {s} ORDER BY TABLE_NAME", {"s": schema}).fetchall()]


def fingerprint(conn, schema: str, table: str, skip_columns: set[str] = FILE_COLUMNS, where: str = "") -> tuple:
    """`where` (optional) restricts the rows, e.g. to the locations two builds have in common; it is written by the
    test itself, never taken from data."""
    cols = [(n, t) for n, t in conn.execute(
        "SELECT COLUMN_NAME, COLUMN_TYPE FROM EXA_ALL_COLUMNS WHERE COLUMN_SCHEMA = {s} AND COLUMN_TABLE = {t} "
        "ORDER BY COLUMN_ORDINAL_POSITION", {"s": schema, "t": table}).fetchall() if n not in skip_columns]
    h = "HASH_SHA256(" + " || '|' || ".join(_col_text(n, t) for n, t in cols) + ")"
    sums = ", ".join(f"SUM(TO_NUMBER(SUBSTR(H, {1 + 12 * i}, 12), 'XXXXXXXXXXXX'))" for i in range(3))
    row = conn.execute(f'SELECT COUNT(*), {sums} FROM (SELECT {h} AS H FROM "{schema}"."{table}" {where})').fetchone()
    return (tuple(n for n, _ in cols),) + tuple(int(x or 0) for x in row)


def compare_schemas(conn, a: str, b: str, skip_tables: set[str] = NOT_RESULTS,
                    only_tables: set[str] | None = None, skip_columns: dict[str, set[str]] | None = None) -> dict:
    """{'compared': [tables], 'different': [tables], 'only_in_a': [...], 'only_in_b': [...]} for every result table
    the two schemas share (or only `only_tables`). `skip_columns` names further columns to leave out per table."""
    _session_formats(conn)
    ta, tb = set(tables(conn, a)), set(tables(conn, b))
    common = sorted((ta & tb) - skip_tables - {t for t in ta | tb if t.startswith("UPLOAD_")})
    if only_tables is not None:
        common = [t for t in common if t in only_tables]

    def fp(schema, t):
        return fingerprint(conn, schema, t, FILE_COLUMNS | (skip_columns or {}).get(t, set()))
    different = [t for t in common if fp(a, t) != fp(b, t)]
    return {"compared": common, "different": different,
            "only_in_a": sorted(ta - tb - skip_tables), "only_in_b": sorted(tb - ta - skip_tables)}
