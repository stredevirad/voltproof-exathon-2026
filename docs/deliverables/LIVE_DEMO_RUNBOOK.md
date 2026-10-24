# Live demo runbook (Stage 2: 15 minutes + 5 minutes Q&A)

**Demo day: Fri 6 Nov 2026, 10:00 am IST, virtual** (over a video call; the Top 5 are announced Wed 4 Nov,
6:00 pm IST). The jury scores the live demo: a deck alone is not scored.

All timings below were measured on the build laptop (docs/BENCHMARKS.md, "Interactive queries"). The demo
path is the guided demo: Huzurpur-Bahraich, July 2018, the evening of 25 July.

## 1. Pre-demo checklist (start 30 minutes before)

| # | Step | Command / check | Expected |
|---|---|---|---|
| 1 | Unrelated Oracle services stay stopped (Manual until after 6 Nov) | `Get-Service Oracle* \| Select Name, Status, StartType` | all Stopped, Manual or Disabled |
| 2 | Close Docker Desktop, other browsers' extra windows, chat and sync apps | Task Manager | only one browser window, with the VoltProof tab |
| 3 | Terminal set-up | `cd D:\Projects\VoltProof`; `Set-ExecutionPolicy -Scope Process Bypass` | – |
| 4 | Start the database | `podman machine start` (red "already running" is fine), `scripts\exa.ps1 start`, then `scripts\exa.ps1 status` | `database_ready` (if it briefly says `database_connection_failed`, check again after 10 s) |
| 5 | Warm up and pre-render the demo report | `scripts\warmup.ps1` | about 4 s; the last line says the guided demo path is ready, and the report id is printed |
| 6 | Start the app | `scripts\start.ps1` (leave this terminal open) | "VoltProof is starting at http://127.0.0.1:8000/" |
| 7 | Health check | open http://127.0.0.1:8000/api/health | `"database":"ok"`, `"events":408223` |
| 8 | Free memory | `[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)` | at least 1.5 (GB) |
| 9 | Browser | window about 1366 × 860 or full screen, zoom 100%; open the start page once and press **Skip the tour** (the browser remembers it; to rehearse the tour later, open http://127.0.0.1:8000/?tour=1) | the start page shows no tour card |
| 10 | Open the backups in other tabs or windows, ready to share | the committed video `docs\deliverables\VoltProof_demo.mp4`; the pre-rendered PDF `reports\evidence\<report id>.pdf` (id from step 5, also in `reports\warmup.json`); `docs\deliverables\VoltProof_deck.pdf` | – |
| 11 | Pre-build one upload (so the demo never waits for a build) | in the app: **Upload your data**, download the two ESMI-layout sample files linked on the page (readings and location file), choose them, **Upload and preview**, **Check the file**, **Analyse this file**; wait for the **Open this dataset** button | the **Data** menu lists "Your upload: …"; switch back to the Prayas data before the demo starts (the start page's "historical records" line shows only on the Prayas data) |

Do **not** run `scripts\load.ps1` or any SQL step after step 5. A rebuild takes about 4 minutes. The app
would then render a fresh report (about 4 s) instead of the pre-rendered one, because the data changed.
After any rebuild, run step 5 again.

## 2. Click path (about 6 minutes)

| Time | Click | Wait | Show and say |
|---|---|---|---|
| 0:00 | Start page | – | One sentence on the problem. The line under the headline says it: historical records from monitors in Uttar Pradesh, 2016–2019, not anyone's supply today. (The first-visit tour never shows in the demo browser once it has been seen; if it does, press **Skip the tour**.) |
| 0:30 | **Start guided demo** | about 0.1 s | The note explains the selection rule (one example, not hand-picked). The first tile, OUTAGE TIME (AT LEAST): at least 366.2 h in July 2018, "up to 367.2 h" if every minute with no reading next to an outage was also one; 320 interruptions next to it. The headline is the minimum: missing readings never count as outage, and hatched days had too few readings. |
| 1:30 | The demo day (25 July) | 0.13 s after warm-up | The voltage trace minute by minute. Orange blocks are outages, hatching means no reading. At 18:27 the supply drops to 0 V. |
| 2:30 | In the table "Outages on this day", the selected 18:27 outage: **open evidence →** | about 0.2 s | Exact start and end, with the certainty of each edge. Open "How was this computed?" to show the two source-file lines and the Exasol statement ids. Then the panel: 16 other Bahraich monitors lost supply within 2 minutes, against 1,827.5 coincident pairs expected by chance for the month (3,945 observed). Coincidence is not cause. |
| 4:00 | Back to the month, **Generate evidence report** | about 0.4 s (pre-rendered; the page shows "Generated …, rendered earlier; same data and code since") | Open the PDF: calendar, every event with bounds, data quality, the grievance route, and the appendix with file checksums and statement ids. Not legal advice. |
| 5:00 | **Data & sources** | – | Scroll to the 2019 files: one excluded (Hour column lost), one marked as lower bounds (0 V hours omitted). Defects are shown, not hidden. |
| 5:30 | **Upload your data**, then the **Data** menu: the pre-built upload (step 11) | about 0.1 s | Your own monitor's readings: the file stays on this computer, the same SQL analyses it in its own schema, and every page says "Uploaded data — not verified by VoltProof". Then switch the **Data** menu back to the Prayas data. |
| 6:00 | (optional) **How to use**, **Methodology** | – | The plain-language guide; thresholds are Prayas's own, and every rule has an id. |

**If something is slower than above:**
- **Another day or month** may take a few seconds the first time; only the demo path is warmed. Say: "The
  database is reading this monitor's minute readings from disk for the first time; next time it is
  instant."
- **A fresh report** takes about 4 s. Say: "It re-reads every number from the database and renders the PDF;
  the PDF, the page and the JSON come from one data file."

## 3. Fallbacks

| Problem | Do this |
|---|---|
| `database_connection_failed` for more than 30 s | `scripts\exa.ps1 stop`, then `scripts\exa.ps1 start` (about 30 s), then `scripts\warmup.ps1`; meanwhile present deck slides 6–8 |
| `scripts\exa.ps1 start` prints nothing new for 3 minutes, or `status` keeps saying "Operation 'start' is currently in progress" | Press Ctrl+C; `scripts\exa.ps1 stop` (this clears the stuck start), `podman machine stop`, `podman machine start`, `scripts\exa.ps1 start` (16 s on 24 Oct), then `scripts\warmup.ps1` |
| A live upload is slow or refused | Switch to the pre-built upload (step 11) in the **Data** menu |
| The app does not start or a page shows an error | Play the committed video `docs\deliverables\VoltProof_demo.mp4` (under 3 minutes) and narrate over it, or pause on each screen |
| The report button fails | Open the pre-rendered PDF from step 10 |
| The laptop itself fails | The deck PDF and the screenshots in `docs\deliverables\screenshots\` are in the public repository |

**Cut list and triggers (decide before, not during):**

| When | Do |
|---|---|
| The live demo is still running at 8:30 | Skip **How to use** and **Methodology** |
| Past 12:00 overall | Skip the upload page; say slides 9–10 in one sentence each |
| The database is not `database_ready` 10 minutes before the start | Present from the committed video, or the deck; do not rebuild |

**Spoken wording (the text checks read files, not speech; in rehearsal one teammate counts slips):**
- Say "at least" with every outage figure, and give its unit: "at least 366.2 hours in July 2018, at one monitor,
  out of 744".
- Say "potential shared supply event", "may warrant review", "Illustrative" (the shopkeeper) and "monitor" (not the
  utility's meter).
- Never claim more certainty than the screen shows, never state an amount owed or a remedy, never name a cause or a
  piece of equipment, and never give a scale beyond what was measured (176 monitors; 102,927,720 minute rows; 210.4 s).
- When the pre-rendered report opens, say so first: "rendered earlier, same data and code".
- At **Data & sources**, show the 2019 file that left out most 0 V hours: missing readings are never counted as
  outages, so those months are lower bounds.

## 4. Virtual demo day (video call)

- **Share only the browser window** in the video-call app (not the whole screen), so terminals, notifications and
  other windows stay private. Switch the shared window to the deck PDF or the video if a fallback is needed.
- **The call app uses memory too.** With the database, the app and the call all running, check free memory again
  (checklist step 8): at least 1.5 GB. If it is lower, close everything else; never restart the database during
  the call.
- **Teammates join from their own devices** (their own laptops or phones), not from the demo laptop. One person
  drives the demo laptop; the others present their blocks and answer questions.
- **Have a phone hotspot ready** if the Wi-Fi drops. The app and the database run on the laptop itself, so only
  the call needs the internet.
- Join the call 15 minutes early from the demo laptop, test screen sharing on the browser window once, and keep
  notifications off (Do not disturb).

## 5. 15-minute presentation outline (reuses the deck)

| Time | Deck / demo | Content |
|---|---|---|
| 0:00–1:30 | Slides 1–3 | The one-sentence problem; the shopkeeper (illustrative); Prayas's monitors already recorded every minute. |
| 1:30–2:00 | Slide 4 | What VoltProof gives him: every cut, dated, with its certainty; the headline is a minimum. |
| 2:00–8:30 | **Live demo** (section 2; slide 5 is its still version) | Guided demo, from calendar to minute trace to evidence to report to sources, then the upload |
| 8:30–10:00 | Slides 6–7 | How it works in four steps, and how Exasol Personal does steps 2 and 3: full build 210.4 s warm, unpivot 11.0 s, every cut found in 35.6 s (665 s before our fix); the audit-log match |
| 10:00–11:00 | Slide 8 | Why the numbers can be checked: number, SQL step, Exasol statement, source line; the independent test check |
| 11:00–12:30 | Slides 9–10 | The data defects found; where we differ from Prayas, in honest wording |
| 12:30–13:30 | Slide 11 | Limits and legal framing: monitor not meter, historical data, coincidence is not cause, grievance route |
| 13:30–15:00 | Slides 12–13 | What changes if adopted; team. Appendix A1–A5 stays ready for questions. |
| 15:00–20:00 | Q&A | Have docs/JUDGE_QA.md open. Likely questions: #8 (is coincidence just chance?), #12 (tuning to Prayas?), #25 (why higher than Prayas's Figure 2?), #5 (what Prayas already publishes), #15 (why Exasol?), #24 (can a judge reproduce this?), #23 (is the demo data real?), #27–#29 (uploads and unverified data) |

Decide in advance who presents which block, and who drives the laptop during the demo.
