"""Ask VoltProof through Exasol's open-source MCP server, as the read-only user VP_READER (docs/ASK_VOLTPROOF.md).

Runs with the separate MCP environment (.tools/mcp-venv with `exasol-mcp-server` from PyPI), not the project venv:

    .tools\\mcp-venv\\Scripts\\python.exe -m pipeline.ask_mcp serve      # stdio MCP server as VP_READER, for an AI client
    .tools\\mcp-venv\\Scripts\\python.exe -m pipeline.ask_mcp tools      # the tools the server offers
    .tools\\mcp-venv\\Scripts\\python.exe -m pipeline.ask_mcp examples   # the six example questions, as markdown

The password comes from data/.reader.json (python -m pipeline.ask setup) and reaches the server only through its
environment. The server lists only VOLTPROOF_ASK, runs read queries only (write queries and preprocessor tools are
off) and sends no telemetry. VoltProof itself never calls a language model: an AI client decides what to ask.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from pipeline.db import conn_info

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER = Path(sys.executable).with_name("exasol-mcp-server.exe" if os.name == "nt" else "exasol-mcp-server")
CREDENTIALS = Path(os.environ.get("VOLTPROOF_READER_FILE") or REPO_ROOT / "data" / ".reader.json")
ASK_SCHEMA = "VOLTPROOF_ASK"
SETTINGS = {"enable_read_query": True, "enable_write_query": False, "enable_preprocessor_tools": False,
            "default_row_limit": 200, "schemas": {"like_pattern": ASK_SCHEMA}}

# The six example questions of docs/ASK_VOLTPROOF.md: the question, then the exact SQL sent through the server.
EXAMPLES = [
    ("How much outage did Huzurpur-Bahraich have in July 2018?",
     "SELECT MONITOR, DISTRICT, MONTH_KEY, IS_COMPARABLE, ROUND(OUTAGE_MIN_LOWER / 60, 1) AS OUTAGE_H_AT_LEAST, "
     "ROUND(OUTAGE_MIN_UPPER / 60, 1) AS OUTAGE_H_AT_MOST, INTERRUPTIONS FROM VOLTPROOF_ASK.LOCATION_MONTH "
     "WHERE MONITOR = 'Huzurpur-Bahraich' AND MONTH_KEY = '2018-07'"),
    ("Which other monitors lost supply with it on the evening of 25 July 2018?",
     "SELECT GROUP_KEY, START_TS, N_LOCATIONS, MONITORS FROM VOLTPROOF_ASK.POTENTIAL_SHARED_SUPPLY_EVENT "
     "WHERE DISTRICT = 'Bahraich' AND START_TS >= '2018-07-25 18:00:00' AND START_TS < '2018-07-25 19:00:00' "
     "ORDER BY START_TS"),
    ("Which district-months of 2018 had the most potential shared supply events?",
     "SELECT DISTRICT, TO_CHAR(START_TS, 'YYYY-MM') AS MONTH_KEY, COUNT(*) AS POTENTIAL_SHARED_SUPPLY_EVENTS "
     "FROM VOLTPROOF_ASK.POTENTIAL_SHARED_SUPPLY_EVENT WHERE START_TS >= '2018-01-01 00:00:00' "
     "AND START_TS < '2019-01-01 00:00:00' GROUP BY DISTRICT, TO_CHAR(START_TS, 'YYYY-MM') "
     "ORDER BY 3 DESC, 1, 2 LIMIT 5"),
    ("How many outage events have an exact start and end, and how many are bounded by a gap in the data?",
     "SELECT START_CERTAINTY, END_CERTAINTY, COUNT(*) AS EVENTS FROM VOLTPROOF_ASK.OUTAGE_EVENT "
     "GROUP BY START_CERTAINTY, END_CERTAINTY ORDER BY 3 DESC"),
    ("Which monitors have the lowest data coverage?",
     "SELECT MONITOR, DISTRICT, ROUND(100 * COVERAGE_WINDOW, 1) AS COVERAGE_PCT, GAP_COUNT, LONGEST_GAP_MINUTES, "
     "COMPARABLE_MONTHS FROM VOLTPROOF_ASK.DATA_QUALITY ORDER BY COVERAGE_WINDOW, MONITOR LIMIT 5"),
    ("Which SQL statements took Exasol the longest in the current build, and how much memory did they use?",
     "SELECT STEP, STMT_INDEX, EXA_DURATION_S, EXA_TEMP_DB_RAM_PEAK_MIB, EXA_SESSION_ID, EXA_STMT_ID "
     "FROM VOLTPROOF_ASK.PROVENANCE ORDER BY EXA_DURATION_S DESC LIMIT 3"),
]
# Two requests that must be refused: a write, and a table outside the views.
REFUSALS = ["DELETE FROM VOLTPROOF_ASK.ABOUT_THIS_DATA", "SELECT * FROM VOLTPROOF.EVENT LIMIT 1"]


def server_env() -> dict[str, str]:
    info = conn_info()
    password = json.loads(CREDENTIALS.read_text(encoding="utf-8"))["password"]
    env = dict(os.environ, EXA_DSN=info.dsn, EXA_USER="VP_READER", EXA_PASSWORD=password,
               EXA_MCP_SETTINGS=json.dumps(SETTINGS), EXASOL_TELEMETRY_DISABLE="1")
    if info.skip_cert_validation:  # the local deployment's self-signed certificate, loopback only (pipeline/db.py)
        env["EXA_SSL_CERT_VALIDATION"] = "no"
    return env


def serve() -> int:
    return subprocess.run([str(SERVER)], env=server_env(), check=False).returncode


def _client():
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    return Client(StdioTransport(command=str(SERVER), args=[], env=server_env()))


def _rows(result) -> tuple[list[str], list[list]]:
    data = result.structured_content or json.loads(result.content[0].text)
    data = data.get("result", data)
    return data["columns"], data["rows"]


def _table(cols: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if v is None else str(v).replace("|", "\\|") for v in r) + " |" for r in rows]
    return "\n".join(out)


async def _tools() -> None:
    async with _client() as c:
        for t in await c.list_tools():
            print(f"{t.name}: {json.dumps(t.inputSchema.get('properties', {}))[:200]}")


async def _examples() -> None:
    async with _client() as c:
        names = sorted(t.name for t in await c.list_tools())
        print(f"Server tools ({len(names)}): {', '.join(names)}\n")
        for i, (question, sql) in enumerate(EXAMPLES, start=1):
            res = await c.call_tool("execute_exasol_query", {"query": sql})
            cols, rows = _rows(res)
            print(f"### {i}. {question}\n\n```sql\n{sql}\n```\n\n{_table(cols, rows)}\n")
        for sql in REFUSALS:
            res = await c.call_tool("execute_exasol_query", {"query": sql}, raise_on_error=False)
            text = " ".join(getattr(x, "text", "") for x in res.content)[:300].replace("\n", " ")
            print(f"Refusal check: `{sql}` -> is_error={res.is_error}: {text}\n")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "serve":
        return serve()
    if cmd == "tools":
        asyncio.run(_tools())
        return 0
    if cmd == "examples":
        asyncio.run(_examples())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
