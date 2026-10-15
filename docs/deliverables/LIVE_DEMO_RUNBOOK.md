# Live demo runbook (Stage 2: 15 minutes + 5 minutes Q&A)

All timings below were measured on the build laptop (docs/BENCHMARKS.md, "Interactive queries"). The demo
path is the guided demo: Huzurpur-Bahraich, July 2018, the evening of 25 July.

## 1. Pre-demo checklist (start 30 minutes before)

| # | Step | Command / check | Expected |
|---|---|---|---|
| 1 | Unrelated Oracle services stay stopped (Manual until after 4 Nov) | `Get-Service Oracle* \| Select Name, Status, StartType` | all Stopped, Manual or Disabled |
| 2 | Close Docker Desktop, other browsers' extra windows, chat and sync apps | Task Manager | only one browser window, with the VoltProof tab |
| 3 | Terminal set-up | `cd D:\Projects\VoltProof`; `Set-ExecutionPolicy -Scope Process Bypass` | – |
| 4 | Start the database | `scripts\exa.ps1 start`, then `scripts\exa.ps1 status` | `database_ready` (if it briefly says `database_connection_failed`, check again after 10 s) |
| 5 | Warm up and pre-render the demo report | `scripts\warmup.ps1` | about 4 s; the last line says the guided demo path is ready, and the report id is printed |
| 6 | Start the app | `scripts\start.ps1` (leave this terminal open) | "VoltProof is starting at http://127.0.0.1:8000/" |
| 7 | Health check | open http://127.0.0.1:8000/api/health | `"database":"ok"`, `"events":408223` |
| 8 | Free memory | `[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)` | at least 1.5 (GB) |
| 9 | Browser | window about 1366 × 860 or full screen, zoom 100% | – |
| 10 | Open the backups in other tabs or windows, ready to share | the committed video `docs\deliverables\VoltProof_demo.mp4`; the pre-rendered PDF `reports\evidence\<report id>.pdf` (id from step 5, also in `reports\warmup.json`); `docs\deliverables\VoltProof_deck.pdf` | – |

Do **not** run `scripts\load.ps1` or any SQL step after step 5. A rebuild takes about 4 minutes. The app
would then render a fresh report (about 4 s) instead of the pre-rendered one, because the data changed.
After any rebuild, run step 5 again.

## 2. Click path (about 6 minutes)

| Time | Click | Wait | Show and say |
|---|---|---|---|
| 0:00 | Start page | – | One sentence on the problem. The data is Prayas's ESMI; we show historical Uttar Pradesh data. |
| 0:30 | **Start guided demo** | about 0.1 s | The banner explains the selection rule (one example, not hand-picked). KPI tiles: 320 interruptions and at least 366.2 hours of outage in July 2018. The headline is the lower bound. Hatched days had too few readings, and missing readings never count as outage. |
| 1:30 | The demo day (25 July) | 0.13 s after warm-up | The voltage trace minute by minute. Orange blocks are outages, hatching means no reading. At 18:27 the supply drops to 0 V. |
| 2:30 | **Open evidence** for the 18:27 outage | about 0.2 s | Exact start and end, with the certainty of each edge. Open "How was this computed?" to show the two source-file lines and the Exasol statement ids. Then the panel: 16 other Bahraich monitors lost supply within 2 minutes, against 1,827.5 coincident pairs expected by chance for the month (3,945 observed). Coincidence is not cause. |
| 4:00 | Back to the month, **Generate evidence report** | about 0.4 s (pre-rendered; the page shows "Generated …, rendered earlier; same data and code since") | Open the PDF: calendar, every event with bounds, data quality, the grievance route, and the appendix with file checksums and statement ids. Not legal advice. |
| 5:00 | **Data & sources** | – | Scroll to the 2019 files: one excluded (Hour column lost), one marked as lower bounds (0 V hours omitted). Defects are shown, not hidden. |
| 5:45 | (optional) **Methodology** | – | Thresholds are Prayas's own, and every rule has an id. |

**If something is slower than above:**
- **Another day or month** may take a few seconds the first time; only the demo path is warmed. Say: "The
  database is reading this monitor's minute readings from disk for the first time; next time it is
  instant."
- **A fresh report** takes about 4 s. Say: "It re-reads every number from the database and renders the PDF;
  the PDF, the page and the JSON come from one data file."

## 3. Fallbacks

| Problem | Do this |
|---|---|
| `database_connection_failed` for more than 30 s | `scripts\exa.ps1 stop`, then `scripts\exa.ps1 start` (about 30 s), then `scripts\warmup.ps1`; meanwhile present deck slides 5–7 |
| The app does not start or a page shows an error | Play the committed video `docs\deliverables\VoltProof_demo.mp4` (under 3 minutes) and narrate over it, or pause on each screen |
| The report button fails | Open the pre-rendered PDF from step 10 |
| The laptop itself fails | The deck PDF and the screenshots in `docs\deliverables\screenshots\` are in the public repository |

## 4. 15-minute presentation outline (reuses the deck)

| Time | Deck / demo | Content |
|---|---|---|
| 0:00–1:30 | Slide 1, slide 2 | The one-sentence problem. Prayas's monitors, and what consumers lack today. The shopkeeper is illustrative. |
| 1:30–2:15 | Slide 3 | Who it helps: consumers, researchers, grievance forums. It is evidence, not a verdict. |
| 2:15–8:15 | **Live demo** (section 2) | Guided demo, from calendar to minute trace to evidence to report to sources |
| 8:15–9:45 | Slides 5–6 | How it works, all in SQL in Exasol: full build 210.4 s warm, IMPORT 30.3 s, run detection 35.6 s; the three scale fixes from the audit log |
| 9:45–11:00 | Slide 7 | Correctness: 18 fixtures, an independent oracle, Hypothesis, provenance checked against the audit log |
| 11:00–12:30 | Slides 8–9 | Validation against Prayas, in honest wording. The data defects found. |
| 12:30–13:45 | Slide 10 | Limits and legal framing: monitor not meter, historical data, coincidence is not cause, grievance route |
| 13:45–15:00 | Slides 11–12 | Future scope; team |
| 15:00–20:00 | Q&A | Have docs/JUDGE_QA.md open. Likely questions: #8 (is coincidence just chance?), #12 (tuning to Prayas?), #25 (why higher than Prayas's Figure 2?), #5 (what Prayas already publishes), #15 (why Exasol?), #24 (can a judge reproduce this?), #23 (is the demo data real?) |

Decide in advance who presents which block, and who drives the laptop during the demo.
