# Ask VoltProof: questions to the results through Exasol's MCP server, read-only

An AI client (Claude Desktop, Claude Code or any MCP client) can ask questions about VoltProof's results through
Exasol's open-source MCP server ([github.com/exasol/mcp-server](https://github.com/exasol/mcp-server), PyPI package
`exasol-mcp-server`, version 2.3.0, checked 29 Oct 2026). It connects as **`VP_READER`**, a database user that can
read seven documented views and nothing else. VoltProof itself never calls a language model; the app and the
reports contain no generated text.

Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), https://doi.org/10.7910/DVN/CLLZZM,
CC0 1.0.

## What VP_READER can see

`python -m pipeline.ask setup` creates the schema `VOLTPROOF_ASK` with the views of
[sql/ask/reader_views.sql](../sql/ask/reader_views.sql) over the Prayas build `VOLTPROOF`, and the user `VP_READER`
with exactly two privileges: `CREATE SESSION` and `SELECT` on `VOLTPROOF_ASK`. Exasol runs a view with its owner's
rights, so the reader never touches a table.

| View | One row per | What it holds |
|---|---|---|
| `ABOUT_THIS_DATA` | rule | Source and attribution, and the rules for reading the other views (read it first) |
| `LOCATION_MONTH` | monitor and month | Outage minutes as lower and upper bounds, interruptions, coverage, comparable or not |
| `OUTAGE_EVENT` | outage event | Measured start and end, duration bounds, certainty of each edge |
| `POTENTIAL_SHARED_SUPPLY_EVENT` | group | Monitors of one district whose interruptions started within 2 minutes |
| `DAILY_OUTAGE` | monitor and day | Outage minutes as lower and upper bounds, interruptions |
| `DATA_QUALITY` | monitor | Coverage, gaps, duplicates, conflicts, quarantined values |
| `PROVENANCE` | SQL statement | The statements behind the current results, with time and memory measured by Exasol |

Every view and every column has a comment, which the MCP server shows to the client. Exasol accepts comments on
views and view columns only inside `CREATE VIEW` (`COMMENT ON` is for tables), so they are written there.

What it cannot do, tested in [tests/integration/test_ask_reader.py](../tests/integration/test_ask_reader.py): read
any table (raw data, results, the audit log), read an upload or any other schema, see any table in the catalogue,
create, change or drop anything, or grant anything. The same test checks that the real `VP_READER` holds only the
two privileges above. The MCP server adds its own limits: read queries only (`enable_write_query` off), no
preprocessor tools, only `VOLTPROOF_ASK` listed, 200 rows by default when the client sets no row limit, and telemetry
off (`EXASOL_TELEMETRY_DISABLE`).

## Set it up

```powershell
.venv\Scripts\python.exe -m pipeline.ask setup            # views + VP_READER; password in data\.reader.json (gitignored)
uv venv .tools\mcp-venv --python 3.12                      # a separate environment for the MCP server
uv pip install --python .tools\mcp-venv\Scripts\python.exe "exasol-mcp-server==2.3.0"
.tools\mcp-venv\Scripts\python.exe -m pipeline.ask_mcp tools      # the server starts as VP_READER and lists its tools
.tools\mcp-venv\Scripts\python.exe -m pipeline.ask_mcp examples   # the six questions below
```

`pipeline/ask_mcp.py serve` starts the server over stdio. It reads the password from `data\.reader.json` and passes
it to the server process in its environment only, so the password never goes into an AI client's settings file.

### Connect an AI client (instructions only; the team's own client settings were not changed)

**Claude Desktop:** add this entry to `mcpServers` in `claude_desktop_config.json`, then restart Claude Desktop.
Adjust the paths if the repository is not at `D:\Projects\VoltProof`.

```json
"voltproof-ask": {
  "command": "D:\\Projects\\VoltProof\\.tools\\mcp-venv\\Scripts\\python.exe",
  "args": ["-m", "pipeline.ask_mcp", "serve"],
  "env": {"PYTHONPATH": "D:\\Projects\\VoltProof"}
}
```

**Claude Code:**

```powershell
claude mcp add voltproof-ask -e PYTHONPATH=D:\Projects\VoltProof -- D:\Projects\VoltProof\.tools\mcp-venv\Scripts\python.exe -m pipeline.ask_mcp serve
```

The database must be running (`scripts\exa.ps1 status`).

## Six example questions

Run on 29 Oct 2026 by `pipeline/ask_mcp.py examples`: a small MCP client that starts the server as `VP_READER` and
sends each query through the server's `execute_exasol_query` tool. The rows below are the server's answers,
unchanged (timestamps are India Standard Time).

### 1. How much outage did Huzurpur-Bahraich have in July 2018?

```sql
SELECT MONITOR, DISTRICT, MONTH_KEY, IS_COMPARABLE, ROUND(OUTAGE_MIN_LOWER / 60, 1) AS OUTAGE_H_AT_LEAST, ROUND(OUTAGE_MIN_UPPER / 60, 1) AS OUTAGE_H_AT_MOST, INTERRUPTIONS FROM VOLTPROOF_ASK.LOCATION_MONTH WHERE MONITOR = 'Huzurpur-Bahraich' AND MONTH_KEY = '2018-07'
```

| MONITOR | DISTRICT | MONTH_KEY | IS_COMPARABLE | OUTAGE_H_AT_LEAST | OUTAGE_H_AT_MOST | INTERRUPTIONS |
|---|---|---|---|---|---|---|
| Huzurpur-Bahraich | Bahraich | 2018-07 | True | 366.2 | 367.2 | 320 |

### 2. Which other monitors lost supply with it on the evening of 25 July 2018?

```sql
SELECT GROUP_KEY, START_TS, N_LOCATIONS, MONITORS FROM VOLTPROOF_ASK.POTENTIAL_SHARED_SUPPLY_EVENT WHERE DISTRICT = 'Bahraich' AND START_TS >= '2018-07-25 18:00:00' AND START_TS < '2018-07-25 19:00:00' ORDER BY START_TS
```

| GROUP_KEY | START_TS | N_LOCATIONS | MONITORS |
|---|---|---|---|
| Bahraich \| 2018-07-25 18:19 | 2018-07-25 18:19:00.000000 | 3 | Bahadurpur-Bahraich, Raja Bazar Nanpara, Takia Jarwal Kasba |
| Bahraich \| 2018-07-25 18:27 | 2018-07-25 18:27:00.000000 | 17 | Agarwal Mohalla Jarwal Kasba, Bahadurpur-Bahraich, Bardaha-Bahraich, Bashirganj Bahraich, Bhavaniyapur Baharaich, Huzurpur-Bahraich, Jagatapur-Bahraich, Kanjaya-Bahraich, Kanoongopura Bahraich, Mahasi-Bahraich, Mihinpurwa-Bahraich, Nai Basti Bahraich, Nazirpura-Bahraich, Raja Bazar Nanpara, Rishibhumi Risia, Saraswati Nagar Risiya, Takia Jarwal Kasba |

The 18:27 group is the one in the guided demo: Huzurpur-Bahraich and 16 other monitors ([VALIDATION](VALIDATION.md) §2).

### 3. Which district-months of 2018 had the most potential shared supply events?

```sql
SELECT DISTRICT, TO_CHAR(START_TS, 'YYYY-MM') AS MONTH_KEY, COUNT(*) AS POTENTIAL_SHARED_SUPPLY_EVENTS FROM VOLTPROOF_ASK.POTENTIAL_SHARED_SUPPLY_EVENT WHERE START_TS >= '2018-01-01 00:00:00' AND START_TS < '2019-01-01 00:00:00' GROUP BY DISTRICT, TO_CHAR(START_TS, 'YYYY-MM') ORDER BY 3 DESC, 1, 2 LIMIT 5
```

| DISTRICT | MONTH_KEY | POTENTIAL_SHARED_SUPPLY_EVENTS |
|---|---|---|
| Bahraich | 2018-06 | 1341 |
| Bahraich | 2018-07 | 1220 |
| Barabanki | 2018-07 | 1166 |
| Bahraich | 2018-05 | 1079 |
| Barabanki | 2018-06 | 1040 |

These counts depend on how many monitors a district had; the chance baseline per district-month is in the app and
in [VALIDATION](VALIDATION.md).

### 4. How many outage events have an exact start and end, and how many are bounded by a gap in the data?

```sql
SELECT START_CERTAINTY, END_CERTAINTY, COUNT(*) AS EVENTS FROM VOLTPROOF_ASK.OUTAGE_EVENT GROUP BY START_CERTAINTY, END_CERTAINTY ORDER BY 3 DESC
```

| START_CERTAINTY | END_CERTAINTY | EVENTS |
|---|---|---|
| exact | exact | 383134 |
| exact | bounded | 13212 |
| bounded | exact | 11575 |
| bounded | bounded | 231 |
| exact | censored | 34 |
| censored | exact | 29 |
| bounded | censored | 4 |
| censored | bounded | 4 |

### 5. Which monitors have the lowest data coverage?

```sql
SELECT MONITOR, DISTRICT, ROUND(100 * COVERAGE_WINDOW, 1) AS COVERAGE_PCT, GAP_COUNT, LONGEST_GAP_MINUTES, COMPARABLE_MONTHS FROM VOLTPROOF_ASK.DATA_QUALITY ORDER BY COVERAGE_WINDOW, MONITOR LIMIT 5
```

| MONITOR | DISTRICT | COVERAGE_PCT | GAP_COUNT | LONGEST_GAP_MINUTES | COMPARABLE_MONTHS |
|---|---|---|---|---|---|
| Haqikatnagar Saharanpur | Saharanpur | 14.8 | 6 | 580740 | 1 |
| Kevai-Fatehpur | Fatehpur | 25.3 | 10 | 333900 | 1 |
| Mathura Bazar 1-Balrampur | Balrampur | 29.2 | 4 | 210720 | 1 |
| Loha Mandi Jhansi | Jhansi | 38.8 | 3 | 98100 | 1 |
| Mau Rural-Jhansi | Jhansi | 42.4 | 9 | 62640 | 2 |

### 6. Which SQL statements took Exasol the longest in the current build, and how much memory did they use?

```sql
SELECT STEP, STMT_INDEX, EXA_DURATION_S, EXA_TEMP_DB_RAM_PEAK_MIB, EXA_SESSION_ID, EXA_STMT_ID FROM VOLTPROOF_ASK.PROVENANCE ORDER BY EXA_DURATION_S DESC LIMIT 3
```

| STEP | STMT_INDEX | EXA_DURATION_S | EXA_TEMP_DB_RAM_PEAK_MIB | EXA_SESSION_ID | EXA_STMT_ID |
|---|---|---|---|---|---|
| 050_segments.sql | 3 | 35.568 | 6214.2 | 1878820585412100096 | 54 |
| 030_unpivot.sql | 6 | 10.982 | 37 | 1878820585412100096 | 22 |
| 040_clean.sql | 3 | 6.707 | 27.1 | 1878820585412100096 | 41 |

### Two requests that are refused

| Request through the server | Answer |
|---|---|
| `DELETE FROM VOLTPROOF_ASK.ABOUT_THIS_DATA` | Refused by the MCP server: "The query is invalid or not a SELECT statement." |
| `SELECT * FROM VOLTPROOF.EVENT LIMIT 1` | Refused by the database: "insufficient privileges: SELECT on table EVENT" |

## The wording rule

- **The agent's sentences are its own.** VoltProof claims only what the views show. An answer an AI client writes
  is not a VoltProof result, report or finding, and it never appears in the app or the reports.
- The views carry the rules an answer should keep (`ABOUT_THIS_DATA`): missing readings are never an outage;
  durations next to a gap are bounds, and the lower bound is the headline; compare only comparable months;
  January–June 2019 figures are lower bounds; a potential shared supply event is a coincidence in time within a
  district, not a cause, and names no fault.
- VoltProof does not determine a cause, a breach of any standard or any remedy. A record may warrant review
  through the consumer grievance process, as the evidence report explains.
- Quote figures with the view and the query that produced them, as above, so anyone can run the same query.

## Revoke it

```powershell
.venv\Scripts\python.exe -m pipeline.ask revoke   # drops VP_READER and VOLTPROOF_ASK, deletes data\.reader.json
```

Then remove the `voltproof-ask` entry from the AI client (`claude mcp remove voltproof-ask` in Claude Code, or
delete it from `claude_desktop_config.json`). Running `setup` again creates a new password. Nothing else in
VoltProof depends on the reader: the app, the reports and the builds work the same without it.
