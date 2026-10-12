Households and small shops on unreliable electricity can't show when, and for how long, their power failed, because when they complain, their own memory is usually all they have to set against the utility's records. If this worked, they could take a dated, minute-by-minute record of every outage and voltage problem, with its uncertainty stated, to their utility or grievance forum.

# VoltProof

**Traceable evidence of power cuts and poor supply, from minute-by-minute voltage records, analysed inside Exasol.**

ExaThon India 2026, Track 3. Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI).
Team: Joshua Herbert Japheth, Rohith Mohandas, Dane John Padinjarekara — Rajagiri School of Engineering &
Technology, Kochi.

## Submission deliverables

| Deliverable | Where |
|---|---|
| Problem statement | [docs/deliverables/PROBLEM_STATEMENT.md](docs/deliverables/PROBLEM_STATEMENT.md) (the one-sentence statement is also the first line of this README) |
| Pitch deck (PDF) | [docs/deliverables/VoltProof_deck.pdf](docs/deliverables/VoltProof_deck.pdf). The source is `docs/deliverables/deck/deck.html`, rendered and checked by `python -m pipeline.deck` |
| Demo video (narrated, under 3:00) | `docs/deliverables/VoltProof_demo.mp4`, **pending the team's voice-over**. Script: [VOICEOVER_SCRIPT.md](docs/deliverables/VOICEOVER_SCRIPT.md); how it is made: [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| Run guide | [Quick start](#quick-start-windows-1011-amd64) below and [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) |
| Licence | MIT, [LICENSE](LICENSE); third-party notices in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |
| Live demo runbook | [docs/deliverables/LIVE_DEMO_RUNBOOK.md](docs/deliverables/LIVE_DEMO_RUNBOOK.md) |
| Evidence behind the claims | [VALIDATION](docs/VALIDATION.md), [BENCHMARKS](docs/BENCHMARKS.md), [TEST_REPORT](docs/TEST_REPORT.md), [JUDGE_QA](docs/JUDGE_QA.md), [METHODOLOGY](docs/METHODOLOGY.md), [DECISIONS](docs/DECISIONS.md) |

![Location-month view: calendar of daily outage minutes, KPIs and the chance comparison](docs/deliverables/screenshots/02_month_calendar.png)

## The problem

In much of India, households and small shops still live with daily power cuts and voltage that is too low
or too high to use. When they complain, their memory is the only record they have, set against the
utility's own reports. Prayas (Energy Group) ran independent plug-in voltage monitors (ESMI) at hundreds of
homes and shops and published the minute-by-minute readings. Those readings are raw: 63-column hourly
rows, gaps, duplicates and file defects. On their own they don't add up to evidence a consumer can show anyone.

## What VoltProof does

VoltProof turns the raw ESMI files into evidence you can check, one location-month at a time. The whole
analysis is versioned SQL that runs **inside Exasol**.

- **Every outage.** Each interruption gets exact timestamps, a certainty for each edge (exact, bounded or
  censored) and a lower and upper duration. The headline is always the lower bound.
- **Missing data stays missing.** A minute without a reading is never counted as an outage.
- **Daily and monthly figures.** These are computed on a full calendar, with coverage. A month counts as
  comparable only if more than 90% of its minutes were read (Prayas's rule).
- **Potential shared supply events.** These are interruptions at different monitors in a district that
  start within 2 minutes of each other. Each district-month is compared with a time-shifted chance baseline.
- **An evidence report (PDF).** It traces every number to the source file and line, the SQL statement's
  hash and its Exasol statement id, and it points to the statutory grievance route.
- **A web app.** A guided demo walks through one real case, from calendar to minute trace to event evidence
  to report.

| | Status |
|---|---|
| Minute classification (Prayas thresholds), events with certainty and bounds, daily/monthly aggregates, coverage, quarantine | **Implemented and tested** (hand-written fixtures, independent oracle, Hypothesis, real data) |
| Coincidence across monitors with a chance baseline | **Implemented and tested** |
| Evidence report with provenance; web app; guided demo | **Implemented and tested** (report consistency tests, Playwright end-to-end) |
| Comparison with Prayas's published figures | **Done**, with an honest result: see [Validation](#validation-against-prayas) |
| Live monitors or smart-meter feeds; state-specific standards of performance; other states | **Future scope**, not claimed |

**What VoltProof does not claim:**
- It does not state what a consumer is owed, or that any rule was breached.
- It does not identify a cause or a piece of equipment. A potential shared supply event is a coincidence
  in time, not proof of a common cause.
- It does not describe today's supply. ESMI data is historical (2014–2019).
- A plug-in monitor is not the utility's meter.

The report says this in plain words and is not legal advice.

## Quick start (Windows 10/11, AMD64)

You need Git, [uv](https://docs.astral.sh/uv/), Node.js 20 or newer, WSL 2 and about 16 GB RAM. Keep
Docker Desktop closed while the database runs. Full details and troubleshooting are in
[docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md).

```powershell
git clone https://github.com/stredevirad/voltproof-exathon-2026.git D:\Projects\VoltProof
cd D:\Projects\VoltProof
Set-ExecutionPolicy -Scope Process Bypass        # this terminal only; repeat it in every new terminal
scripts\bootstrap.ps1                            # about 3 minutes: Python 3.12, dependencies, Exasol launcher, Chromium, web build (all inside the repo)
```

**1. Exasol Personal.** Check whether a database is already running:

```powershell
scripts\exa.ps1 status
```

- If it prints `database_ready`, go to step 2.
- After a Windows restart, run `scripts\exa.ps1 start`.
- First time on this machine:

  ```powershell
  winget install -e --id RedHat.Podman             # then open a new terminal and repeat Set-ExecutionPolicy above
  scripts\exa.ps1 install local --auto-approve     # about 2 minutes; accepts the Exasol Personal EULA
  ```

**2. Data (minimum set, about 141 MB).** The ESMI files are on Harvard Dataverse. Each download asks for a
short Guestbook form, so you download them yourself.
1. Open https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/CLLZZM.
2. Download these three files into `data\raw\` (create the folder) without renaming them:
   - `ESMI location information`
   - `About the initiative.pdf`
   - `ESMI minute-wise voltage data 2018 June-Aug`

   For tabular files, choose "Original File Format (Comma Separated Values)". This set is enough for the
   guided demo and the tests.

**3. Build the analysis inside Exasol.** This verifies checksums against Dataverse, loads with native
`IMPORT`, runs every SQL step and checks provenance. It took 27 seconds in the clean-start test.

```powershell
scripts\load.ps1 -Set first
```

**4. Open the app** at http://127.0.0.1:8000/ and press **Start guided demo**:

```powershell
scripts\start.ps1                # stop it with Ctrl+C; stop it before rebuilding with load.ps1
```

**5. Run the tests** (unit, integration, differential, end-to-end; about 3 minutes on the minimum set):

```powershell
scripts\test.ps1
```

To build next to an existing build without touching it, set a schema name before steps 3–5, for example
`$env:VOLTPROOF_SCHEMA = 'VOLTPROOF_CLEAN'`. To use another port, run `scripts\start.ps1 -Port 8090`.

**Optional: all of Uttar Pradesh (about 1.9 GB; gives the headline figures below).**
1. Also download 2016 Jan-June, 2016 July-Dec, 2017 Jan-April, 2017 May-Aug, 2017 Sept-Dec, 2018 Jan-May,
   2018 Sep-Dec, 2019 Jan-June and 2019 July-Dec.
2. Then run:

   ```powershell
   scripts\load.ps1 -Set up                                  # about 4 minutes on the build laptop
   .venv\Scripts\python.exe -m pipeline.run_sql 110          # validation tables (VALIDATION.md section 3)
   .venv\Scripts\python.exe -m pipeline.headline_figures     # regenerates docs\HEADLINE_FIGURES.md
   ```

   Keep other heavy applications closed: on a 16 GB machine the database uses most of the memory during
   this build.

## How it works

```
Dataverse CSV ──verify MD5──▶ Exasol IMPORT (raw rows + file id + line no)
   ▶ sql/030  unpivot 63 columns → minutes; parse dates per file; quarantine bad rows
   ▶ sql/040  duplicates and conflicts → clean readings; monitoring window
   ▶ sql/050  voltage classes; runs via one window function (gaps-and-islands); NO_DATA gaps
   ▶ sql/060–090  events with certainty and bounds → daily (full calendar) → monthly (coverage)
   ▶ sql/095  data quality per file and location
   ▶ sql/100  coincident interruptions across monitors; chance baseline (20 whole-day shifts)
   ▶ FastAPI + React app, PDF evidence report (every number traced to file line and Exasol statement id)
```

The rules are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md), and every choice is recorded in
[docs/DECISIONS.md](docs/DECISIONS.md). Exasol's specific role is in [docs/WHY_EXASOL.md](docs/WHY_EXASOL.md).

## Headline figures (Uttar Pradesh)

From [docs/HEADLINE_FIGURES.md](docs/HEADLINE_FIGURES.md), which a script generates.

- **Scale (full load):** 102,845,781 clean minute readings from 176 monitors (January 2016 to June 2019)
  gave 408,223 outage events, 83,929 location-days and 2,870 location-months.
- **Outage, 2016–2018, comparable months.** Measured minutes only, so these are lower bounds.

  | Category | Monitors | Outage, minutes/day | Interruptions/day | Evening outage (17–23 h), minutes |
  |---|---:|---:|---:|---:|
  | Megacity (Lucknow, Kanpur) | 16 | 56.3 | 1.76 | 11.5 |
  | Other municipal | 68 | 189.5 | 4.03 | 52.1 |
  | Rural | 82 | 566.3 | 7.44 | 152.0 |

- **Potential shared supply events, 2016–2018:**
  - Across the 276 district-months with at least two monitors, interruptions started within 2 minutes of
    each other 91,532 times. The time-shifted baseline expects 40,704.6.
  - 150 of those district-months are above all 20 shifted variants.
  - Coincidence is not cause.

## Validation against Prayas

VoltProof agrees with Prayas's published single-monitor profiles (2017–18, within 0.2 h/day) and its
time-of-day and evening charts. Our daily-outage averages are higher than Prayas's Figure 2. Prayas's
Figure 2 and Figures 8–9 imply different averages, and the article does not state the averaging used for
Figure 2 ([docs/VALIDATION.md](docs/VALIDATION.md) §3).

Correctness is checked independently of that comparison ([docs/VALIDATION.md](docs/VALIDATION.md) §1):
- 18 hand-written fixtures, with expected values derived by hand from the rules;
- an independent plain-Python oracle that must equal the SQL exactly, on the fixtures, on 40 random
  Hypothesis batches and on real Uttar Pradesh slices;
- report-consistency tests;
- every executed statement matched to Exasol's audit log.

Test results are in [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

## Known data defects (found, documented, handled)

- **2019 July–Dec file: the Hour column was lost** (690,915 of 695,974 rows say hour 0). It is loaded and
  verified, then excluded from the analysis (D-026).
- **2019 Jan–June file: most all-0 V hours are omitted.** Prayas's own charts count those hours as no
  supply. VoltProof keeps them as missing data, so outage figures for January–June 2019 are **lower
  bounds**. The app and reports say so, and headline figures use 2016–2018 (D-031, VALIDATION §3.4).
- **2019 files:** dates are M/D/YYYY, where earlier files use DD-MM-YYYY (detected per file, D-025).
  Location names carry an added " [Offline]" (matched only when unambiguous, D-029).

## Performance

Measured on an Intel Core Ultra 5 125H laptop with 15.6 GB RAM ([docs/BENCHMARKS.md](docs/BENCHMARKS.md);
medians of 3 runs). The full Uttar Pradesh build, from IMPORT through every SQL step, takes:
- 210.4 s warm and 238.6 s cold (first run after a database restart);
- of which 30.3 s is the native IMPORT of 7,367,581 raw rows;
- 11.0 s the in-database unpivot to 102,927,720 minute rows;
- 35.6 s run detection over 102.8 million readings with one window function.

These runs had other memory-heavy applications closed. With them open, free host RAM fell below our 0.4 GiB
guard and the run was stopped (both cases are recorded in BENCHMARKS.md).

In the app, warm:
- a location-month opens in about 0.1 s and a day view in about 0.2 s;
- a fresh evidence report (HTML and PDF) takes about 3.7 s, and an unchanged one is served again in 0.4 s.

Right after a database restart, the first day view took 2.1 s; after `scripts\warmup.ps1`, it took 0.13 s.

Every statement in every build matched Exasol's audit log. Why this is Exasol's work and not Python's:
[docs/WHY_EXASOL.md](docs/WHY_EXASOL.md).

## Repository map

| Path | What |
|---|---|
| `sql/` | Numbered SQL steps: the single source of analytical truth |
| `pipeline/` | Download checks, native IMPORT, step runner with provenance, benchmarks, validation scripts |
| `app/api`, `app/web` | FastAPI service and evidence report; React + ECharts web app |
| `tests/` | Fixtures, independent oracle, Hypothesis differential, report and end-to-end tests |
| `config/` | Thresholds and parameters (each with its source), declared file periods |
| `docs/` | Methodology, decisions, validation, benchmarks, verification log, judge Q&A, setup |

## Data, citation and licence

- **Data.** Prayas, Energy Group, 2019, "Minute-wise voltage data collected in Electricity Supply
  Monitoring Initiative", https://doi.org/10.7910/DVN/CLLZZM, Harvard Dataverse, V2,
  UNF:6:CQzM5yPH9GilZHSqyRRyEQ== [fileUNF].
  - The dataset is licensed **CC0 1.0** on Dataverse. Prayas also asks for non-commercial, academic and
    research use with acknowledgement, and we follow that.
  - Raw data is **not** redistributed in this repository ([docs/data/SOURCE_TERMS.md](docs/data/SOURCE_TERMS.md)).
- **Code.** MIT licence ([LICENSE](LICENSE)). Third-party notices are in
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- **Exasol Personal** is used under its End User License Agreement and is not included in this repository.

## Acknowledgements

We are grateful to **Prayas (Energy Group)** and the volunteers of the **Electricity Supply Monitoring
Initiative (ESMI)**, who collected and published these readings. VoltProof exists only because they made
the data public. Any errors in the analysis are ours.
