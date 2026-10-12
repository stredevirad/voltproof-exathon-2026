"""Collect the database's own resource facts (RAM, storage) as evidence. Read-only.

    .venv\\Scripts\\python.exe -m pipeline.resource_facts
"""

from __future__ import annotations

import json
import sys

from pipeline.db import connect

QUERIES = {
    "system_events_last": "SELECT * FROM EXA_SYSTEM_EVENTS ORDER BY MEASURE_TIME DESC LIMIT 3",
    "db_size_last_day": "SELECT MEASURE_TIME, RAW_OBJECT_SIZE, MEM_OBJECT_SIZE, AUXILIARY_SIZE, STATISTICS_SIZE, "
                        "RECOMMENDED_DB_RAM_SIZE, STORAGE_SIZE, USE, OBJECT_COUNT FROM EXA_DB_SIZE_LAST_DAY "
                        "ORDER BY MEASURE_TIME DESC LIMIT 1",
    "monitor_last_day": "SELECT MEASURE_TIME, LOAD, CPU, TEMP_DB_RAM, PERSISTENT_DB_RAM, HDD_READ, HDD_WRITE, SWAP "
                        "FROM EXA_MONITOR_LAST_DAY ORDER BY MEASURE_TIME DESC LIMIT 1",
    "metadata_resources": "SELECT PARAM_NAME, PARAM_VALUE FROM EXA_METADATA WHERE LOWER(PARAM_NAME) REGEXP_LIKE "
                          "'.*(ram|mem|node|cpu|core|connection|session).*' ORDER BY 1",
}


def main() -> int:
    out = {}
    with connect() as c:
        c.execute("FLUSH STATISTICS")
        for name, q in QUERIES.items():
            try:
                st = c.execute(q)
                cols = st.column_names()
                out[name] = [dict(zip(cols, map(str, r), strict=False)) for r in st.fetchall()]
            except Exception as e:
                out[name] = f"error: {' '.join(str(getattr(e, 'message', e)).split())[:300]}"
    print(json.dumps(out, indent=1)[:8000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
