"""Report table sizes for a schema from Exasol's own catalogue (read-only).

    .venv\\Scripts\\python.exe -m pipeline.storage_facts VOLTPROOF
"""

from __future__ import annotations

import sys

from pipeline.db import DEFAULT_SCHEMA, connect


def main(schema: str) -> int:
    with connect() as c:
        rows = c.execute(
            "SELECT OBJECT_NAME, RAW_OBJECT_SIZE, MEM_OBJECT_SIZE "
            "FROM EXA_ALL_OBJECT_SIZES WHERE ROOT_NAME = {s} AND OBJECT_TYPE = 'TABLE' ORDER BY 2 DESC",
            {"s": schema.upper()},
        ).fetchall()
        counts = {}
        for name, *_ in rows:
            counts[name] = int(c.execute(f'SELECT COUNT(*) FROM "{schema.upper()}"."{name}"').fetchval())
    tot_raw = tot_mem = 0
    print(f"{'table':<20} {'rows':>14} {'raw MiB':>10} {'stored MiB':>11} {'bytes/row':>10}")
    for name, raw, mem in rows:
        raw, mem = int(raw or 0), int(mem or 0)
        tot_raw += raw
        tot_mem += mem
        n = counts[name]
        print(f"{name:<20} {n:>14,} {raw / 2**20:>10.1f} {mem / 2**20:>11.1f} {mem / n if n else 0:>10.2f}")
    print(f"{'TOTAL':<20} {'':>14} {tot_raw / 2**20:>10.1f} {tot_mem / 2**20:>11.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCHEMA))
