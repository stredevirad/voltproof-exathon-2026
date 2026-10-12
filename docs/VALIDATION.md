# Validation

This file collects evidence that VoltProof's numbers are right: comparisons with independent
implementations, hand-checked examples, and (G6) a comparison with Prayas's published Uttar Pradesh
figures. Every number here comes from a recorded run. Commands are given so each can be reproduced.

## 1. Independent oracle vs Exasol SQL (G3/G4)

| Check | Scope | Result | Command |
|---|---|---|---|
| Hand-written fixtures (R-1 to R-21) | 18 synthetic fixtures (F01–F18), every hand-derived expected value | all pass | `scripts\test.ps1 -Suite integration` |
| Fixtures, SQL = oracle | all events, daily and monthly rows, pairs, groups, baselines | identical | same |
| Harness sensitivity | a single perturbed expected value or oracle field must be reported | detected | same |
| Random inputs (Hypothesis) | 40 random multi-location batches, randomised parameters | identical (1,874 raw rows, 2,162 events, 228 bridged, 1,063 bounded edges) | `scripts\test.ps1 -Suite differential -Examples 40` |
| Real data, events and aggregates | 4 UP locations, 2018 Jun–Aug | identical (4,930 events, 365 days, 12 months) | same |
| Real data, coincidence | Bahraich + Barabanki, all 49 locations, 2018 Jun–Aug | identical (20,127 pairs, 6,683 groups, 6 district-month baselines) | same |

## 2. Coincidence sanity check on the full UP data (G4, re-run in G6)

**Data:** full Uttar Pradesh build (2016-01 to 2019-06); Δ = 2 min, θ = 1 min, N = 20 shifts; the baseline
uses comparable location-months only (D-023), so "Locations" counts monitors with a comparable month.
Command: `.venv\Scripts\python.exe -m pipeline.g4_sanity Bahraich 2018-07` (run 2026-10-11 on the full
build; the earlier 2018 Jun–Aug sample-era table is superseded).

**Observed vs chance (selected district-months):**

| District | Month | Locations | Interruptions | Observed pairs | Expected by chance | Ratio | Empirical p |
|---|---|---:|---:|---:|---:|---:|---:|
| Bahraich | 2018-07 | 19 | 5,557 | 3,945 | 1,827.5 | 2.2 | < 0.05 |
| Bahraich | 2018-08 | 14 | 4,238 | 3,270 | 1,063.0 | 3.1 | < 0.05 |
| Barabanki | 2018-07 | 18 | 4,689 | 1,983 | 1,291.8 | 1.5 | < 0.05 |
| Barabanki | 2018-08 | 13 | 3,003 | 757 | 536.8 | 1.4 | < 0.05 |
| Sitapur | 2018-07 | 8 | 2,221 | 410 | 276.5 | 1.5 | < 0.05 |
| Lucknow | 2018-06 | 4 | 406 | 54 | 8.5 | 6.4 | < 0.05 |
| Lucknow | 2018-08 | 4 | 183 | 2 | 1.8 | 1.1 | 0.50 |

"< 0.05" means none of the 20 shifted versions reached the observed count. With N = 20 the smallest
resolvable p is 1/20.

**All district-months:** 420 district-months have interruptions in comparable months; 322 of them have at
least two monitors. Of those 322, 174 are above every one of the 20 shifted versions, 132 have p > 0.05 and
44 have fewer coincident pairs than expected. Summed over the 322, there are 97,852 observed pairs against
43,192.4 expected (2.3 times). Over the 141 district-months with at least 10 expected pairs, the median
ratio is 1.9.

**Reading:** in the large rural districts, coincident interruptions are about 1.4–3.1 times more frequent
than the time-shifted baseline. The baseline keeps each monitor's own daily rhythm, including scheduled
evening cuts, so this excess is not explained by time-of-day routine alone. Many district-months sit at
chance (e.g. Lucknow 2018-08), which is the expected contrast.

**Example group, Bahraich, 25 July 2018 (evening):** group key `Bahraich | 2018-07-25 18:27`, 17 member
interruptions at 17 different monitors, 136 coincident pairs, starts between 18:27 and 18:29 (this is the
guided demo's group). 21 Bahraich monitors had interruptions that month. Each member was checked against the raw CSV
(independently of the SQL): the minute before the start shows supply (137–243 V) and the start minute
reads **0 V**. All 17 pass.

**What this does and does not show:** it shows that independent monitors in one district recorded
loss of supply within two minutes of each other far more often than chance. It does **not** show a
common fault or identify one. A shared upstream cause is plausible, but independent local causes and
scheduled supply arrangements remain possible, and VoltProof reports these only as
"potential shared supply events".

## 3. Comparison with Prayas's published UP figures (G6)

**Source:** Prayas (Energy Group), "ESMI in Uttar Pradesh", 7 Aug 2019, text and Figures 2, 5, 6, 8, 9,
10, 11, 12 and 14 (VERIFICATION_LOG P4–P16). Prayas's stated method: UP, calendar years 2016–19, "Data
from a location was considered for months only where more than 90% of data was available".

**Summary.** VoltProof agrees with Prayas's single-monitor supply profiles for 2017–2018 to within
0.2 h/day for every voltage class (34 monitor-months), and with Prayas's time-of-day and evening outage
figures (Figures 8 and 9). **VoltProof does not reproduce the daily outage averages in Prayas's Figure 2
and its text** (ours are 2.0–2.6 times higher). We could not reconcile Figure 2 with Figures 8 and 9; the
article does not state how Figure 2 was averaged. The comparison also found a defect in the 2019
Jan–Jun source file (§3.4).

### 3.1 Definitions used

- **Primary definition (stated before comparing, not tuned):** Prayas's voltage classes (outage ≤ 130 V);
  measured minutes only; interruption = an outage of at least 1 minute; location-months with more than
  90% of calendar minutes read ("comparable", Prayas's rule); 2016-01 to 2019-06 (our 2019 July–Dec file
  is excluded, D-026); averages pooled (total outage minutes ÷ total observed days) per category;
  evening = 17:00–22:59.
- **Categories (D-030):** our location file gives State Capital, District Headquarters, Other Municipal
  Area and Gram Panchayat. Megacity = State Capital (Lucknow) plus the Kanpur District Headquarters
  monitors; other municipal = other District Headquarters and Other Municipal Area; rural = Gram
  Panchayat. Counts: megacity 10 domestic + 7 non-domestic (Prayas 9 + 7), other municipal 66 + 6
  (Prayas 57 + 11), rural 86 + 1 (Prayas 79 + 0). Monitors with at least one comparable month in the
  study period: 16 / 68 / 82.
- **Data used:** 1,876 comparable location-months (megacity 292, other municipal 818, rural 766),
  56,490 observed location-days.

### 3.2 Results, one row per published figure

| Published (where) | Prayas | VoltProof | Reading |
|---|---|---|---|
| Daily outage, min/day (Figure 2 and text) | 21 / 87 / 260 | 55.6 / 174.4 / 555.2 | **Not reproduced** (×2.6 / ×2.0 / ×2.1) |
| Outage by time of day, summed over the four 6-h slots (Figure 8, read from its colour scale, ±0.1 h per slot) | ≈ 56 / ≈ 155 / ≈ 523 | 54 / 174 / 598 (equal weight per month, as Figure 8's columns) · 56 / 174 / 555 (pooled) | Agrees (within 0–14%) |
| Evening outage, min per evening (Figure 9: 6 h minus 5 h 48 / 5 h 07 / 3 h 36 of supply) | 12 / 53 / 144 | 11.3 / 47.8 / 147.3 | Agrees |
| Evening outage (text) | "Lucknow … 12 minutes"; other municipal "about 53"; rural "close to 1 hour and 30 minutes" | Lucknow 6.0; 47.8; 147.3 | The text differs from Figure 9 for rural (90 vs 144) and names Lucknow where Figure 9's bulb says "Megacity"; both readings are shown |
| Interruptions per day (text; Figure 6 monthly bars) | "a couple" / "nearly five" / "up to 10"; monthly bars about 1–3.6 / 2–7 / 5–10 | 1.81 / 4.01 / 7.50 (≥ 2 min: 1.70 / 3.90 / 7.19); monthly 0.7–3.6 / 2.2–6.4 / 4.8–11.5 | Approximately agrees |
| Duration mix, "across all ESMI locations" (Figure 5): ≤ 15 min / 15–60 min / 1–3 h / > 3 h | 11 / 19 / 33 / 37% | by count 55.0 / 19.9 / 17.2 / 8.0%; by time 5.5 / 10.2 / 31.1 / 53.2% | **Not reproduced** under either weighting (Figure 5 may cover all ESMI states, which we cannot test) |
| Single-monitor supply profiles, 2017–2018 (Figures 10, 11, 12, 14: Sikanderabad, Biswan, Baraulia, Huzurpur road Kaisarganj) | hours/day per class, per month | largest difference over 34 monitor-months: normal 0.1, low 0.1, high 0.2, no supply 0.1, no data 0.1 h/day | Agrees |
| Same monitors, 2019 Jan–Jun | 11 monitor-months | normal / low / high within 0.2 h/day; no supply up to 11.6 h/day lower, with no data correspondingly higher | Source-file defect, §3.4 |
| Sikanderabad: "around 12 hours of high voltage (>270 volts) supply each day in the initial month" | ≈ 12 h; Figure 10 starts at Dec 2017 and shows 11.8 h | Dec 2017, its first month with > 90% data: 11.7 h (the partial months before: Oct 3.4 h, Nov 8.5 h) | Agrees |
| Baraulia: "high voltage supply exceeding 300 volts on multiple occasions" | — | 34,554 minutes above 300 V on 150 days | Agrees |
| Months Prayas leaves out of a monitor's profile (Biswan Sep 2018) | omitted | our coverage 79.7%, below the 90% rule | Consistent |

Megacity, other municipal and rural are given in that order. Prayas's single-monitor figures are read by
counting the pixels of each legend colour down each stacked bar, whose full height is 24 h.

### 3.3 Investigating the daily-outage gap

Every row below changes one definition and keeps the rest of the primary definition. None is tuned.
The result does not explain the gap.

| Variant | Megacity | Other municipal | Rural |
|---|---:|---:|---:|
| Primary (pooled) | 55.6 | 174.4 | 555.2 |
| Mean of location-months | 55.6 | 173.9 | 554.3 |
| Mean of locations | 60.3 | 224.0 | 573.1 |
| Median of locations | 59.7 | 119.8 | 581.1 |
| Equal weight per calendar month | 54 | 174 | 598 |
| Domestic connections only | 57.3 | 184.2 | 564.7 |
| 0 V minutes only (not 1–130 V) | 55.0 | 170.0 | 539.6 |
| 2016–2018 only (without 2019) | 56.3 | 189.5 | 566.3 |
| Upper bound (with inferred minutes) | 55.7 | 177.5 | 558.0 |
| Lucknow only, for megacity | 34.6 | – | – |
| **Prayas, Figure 2** | **21** | **87** | **260** |

By year (pooled): megacity 68.3 / 48.1 / 49.6 / 50.3 (2016–2019), other municipal 237.4 / 116.1 / 226.8 /
84.9, rural 771.4 / 495.5 / 561.0 / 437.5. No single year comes close to Figure 2.

**Causes tested and rejected:**
- Multi-day zero stretches account for only 5–9% of outage minutes.
- The gap is not driven by a few extreme monitors: the top 10% of monitors contribute 27.5% / 17.4% / 10.6%
  of each category's outage minutes.
- Averaging method, connection type, 0 V vs low readings, the year mix, the 2019 data, and inferred
  minutes are all ruled out by the table above.

**Evidence that the pipeline does not inflate outage minutes:**
- Prayas's own single-monitor profiles agree to within 0.1 h/day of no supply for 2017–2018.
- Prayas's Figures 8 and 9 agree with our time-of-day and evening outage.
- The gaps run in opposite directions for Lucknow: its daily outage is 1.6 times Figure 2's megacity value,
  while its evening outage is half the text's 12 minutes. A uniform inflation would push both up.
- The SQL matches an independent oracle (§1).

**What we cannot test from the publication:**
- **Prayas's exact location-months.** Figure 6 shows months we have but Prayas does not: megacity 2019
  Jan–Jun, rural Feb 2016, Jun–Aug 2016 and Mar–Jun 2019. Prayas also had 2019 Jul–Nov, which our files
  lack.
- **How Figure 2 averages.** Its megacity range bar tops out at about 1.3 h/day. Three of our megacity
  monitors average more than that: Aishbagh-Lucknow 151 min/day over 5 months, Masvanpur-Kanpur 98 over 38,
  Civil Line-Kanpur 88 over 11.
- **Any verification or exclusion step** applied to the published averages.
- **Whether Figure 5 covers UP only.**

### 3.4 Finding: the 2019 Jan–Jun file omits most all-zero hours

The single-monitor comparison exposed a defect in `ESMI voltage data 2019 Jan-June.csv`.

**Evidence:**
- **All-zero hours:** in 2016–2018, 11–17% of read location-hours have 0 V in all 60 minutes. In 2019 it
  is 4.3%.
- **Gaps:** 2019 has 12,555 gaps with no reading, against 209–1,027 a year before. 82% of the 2019 gaps
  (75% of their minutes) have a 0 V reading immediately before and after.
- **Example:** Biswan-Sitapur on 10 Jan 2019. The CSV has rows for hours 0–9, 17–18 and 20–23. Hour 9 ends
  at 0 V and hour 17 starts at 0 V, and the same happens around hour 19. Prayas's Figure 11 shows about
  12 h/day of no supply at Biswan in Jan 2019, where we read 1.8 h of outage and 10.3 h without readings.

**Effect:**
- Under R-2 ("missing data is never counted as an outage"), these hours are NO_DATA.
- 2019 outage figures are therefore lower bounds, well below what Prayas's own system shows.
- Many 2019 location-months fall below the 90% rule and are flagged as not comparable: 222 of 492 UP
  location-months are comparable.
- Even comparable 2019 months may lack up to 10% of minutes.
- The aggregate comparison barely changes without 2019 (table above).
- Handling is recorded as D-031.

### 3.5 Reproduce

```powershell
.venv\Scripts\python.exe -m pipeline.run_sql 110          # validation tables (about 1 s; needs the UP build)
.venv\Scripts\python.exe -m pipeline.prayas_figures       # needs network: downloads Prayas's figures to .cache\prayas
```

Step 110 is not part of `scripts\load.ps1`, because it is a UP-specific validation, not a product
feature. `pipeline.prayas_figures` is not part of the clean start, because it needs the network. The
figures stay in `.cache` and are never committed; they are Prayas's work.

## 4. Clean-start test (G6): a fresh clone, following only the README

**Setup.**
- **Clone:** `D:\Temp\voltproof-clean`, cloned on 2026-10-12 from the local repository at commit `83fd1ce`.
  The final repeat clones from GitHub after the G6 push (§4.3).
- **Database:** the existing Exasol Personal deployment, already running. The README branch "`status`
  prints `database_ready`, go to step 2" was taken; `exa.ps1 install` was not run.
- **Schema:** the build went into a separate schema, `$env:VOLTPROOF_SCHEMA = 'VOLTPROOF_CLEAN'`, as the
  README describes, so the main build was untouched.
- **Data:** the README minimum set. The three files were hardlinked from the repository's `data\raw`, in
  place of the browser downloads the README asks for (same names and bytes; the Dataverse Guestbook is a
  manual step).

### 4.1 Iteration 1 (commit `83fd1ce`)

| README step | Result | Time |
|---|---|---|
| `Set-ExecutionPolicy -Scope Process Bypass`; `scripts\bootstrap.ps1` | ✅ launcher and gitleaks SHA-256 verified; Python env, Chromium and web build done | 188 s |
| 1. `scripts\exa.ps1 status` | ✅ `database_ready` (install skipped, as the README says) | – |
| 2. Data | ✅ three files in `data\raw\` | – |
| 3. `scripts\load.ps1 -Set first` | ✅ checksums verified against Dataverse; 98 monitors, 10,424,400 clean minutes, 52,810 events; provenance 45/45 | 26.6 s |
| 4. `scripts\start.ps1 -Port 8090` | ❌ the server stopped right after starting **when its output was redirected to a file** (how the test captured it). Windows PowerShell 5.1 turns uvicorn's stderr log lines into error records, and the script's `Stop` preference then ends it. Run directly, uvicorn served `/api/health` (schema `VOLTPROOF_CLEAN`), `/api/demo` (the same Bahraich, 25 July 2018 example) and the home page (HTTP 200) | – |
| 5. `scripts\test.ps1` | ❌ e2e `test_methodology_and_sources_pages` failed: it expected an "Excluded" file on the Sources page, which exists only when the full Uttar Pradesh set (with 2019 July–Dec) is loaded. Unit 22, integration 63 (1 skipped), differential 4 passed | 147 s |

**Fixes, each committed before the next iteration:**
- `3671dfb`: `start.ps1` keeps the server running when its output is redirected.
- `3f2dd80`: the e2e Sources-page checks follow the files actually loaded.

**README changes from this run:**
- repeat the execution-policy line in every new terminal;
- measured times for bootstrap, the minimum build and the tests;
- how to stop the app.

No step needed knowledge that the README did not give.

### 4.2 Iteration 2 (`git pull` to `3f2dd80`)

| README step | Result | Time |
|---|---|---|
| 4. `scripts\start.ps1 -Port 8090` (output redirected) | ✅ `/api/health`: database ok, schema `VOLTPROOF_CLEAN`, 98 locations, 52,810 events | – |
| 5. `scripts\test.ps1` (all suites, one command) | ✅ unit 22 passed; integration 63 passed, 1 skipped (the 2019-month report test: no 2019 data in the minimum set); differential 4 passed; e2e 3 passed, 1 skipped (the 2019 banner test, same reason) | 161 s |

### 4.3 Final repeat from GitHub (commit `225b3a0`)

`git clone https://github.com/stredevirad/voltproof-exathon-2026.git D:\Temp\voltproof-clean-2`, exactly as in
the README, on 2026-10-12. Same database and the same `VOLTPROOF_CLEAN` schema; minimum set hardlinked as before.

| README step | Result | Time |
|---|---|---|
| `Set-ExecutionPolicy -Scope Process Bypass`; `scripts\bootstrap.ps1` | ✅ both SHA-256 checks verified | 188 s |
| 1. `scripts\exa.ps1 status` | ✅ `database_ready` | – |
| 3. `scripts\load.ps1 -Set first` | ✅ three files verified against Dataverse; 98 monitors, 10,424,400 clean minutes, 52,810 events; provenance 0 different, 0 missing | 32.1 s |
| 4. `scripts\start.ps1 -Port 8090` | ✅ health ok (`VOLTPROOF_CLEAN`, commit `225b3a0b1845`), guided demo event `183-201807251827`, home page HTTP 200 | – |
| 5. `scripts\test.ps1` | ✅ unit 22; integration 63 (1 skipped: no 2019 data); differential 4; e2e 3 (1 skipped: no 2019 data); **all passed** | 183 s |

No step needed knowledge outside the README. Both clones and the schema `VOLTPROOF_CLEAN` were removed later.

### 4.4 No-download quick start from GitHub (commit `35bc78a`)

On 2026-10-12, `git clone https://github.com/stredevirad/voltproof-exathon-2026.git D:\Temp\voltproof-clean-3`
was followed by the new README quick start: bootstrap, `load -Set demo`, start. Nothing was downloaded
from Dataverse and nothing was copied from the main checkout.

Setup:
- **Machine and database:** the same machine and the same running database as above.
- **Schema:** the database is shared with the main build, so `VOLTPROOF` exists, and `start.ps1` and
  `test.ps1` would prefer it. To reproduce a machine that has only the demo set,
  `$env:VOLTPROOF_SCHEMA = 'VOLTPROOF_DEMO'` was set before steps 3 and 4.
- **"Working":** the app counted as working only when `/api/meta` reported `synthetic: true` and
  `/api/demo` returned the synthetic event. HTTP 200 alone was not enough.

| README step | Result | Time |
|---|---|---|
| `git clone` | ✅ commit `35bc78a9ff04` | 36.3 s |
| `Set-ExecutionPolicy -Scope Process Bypass`; `scripts\bootstrap.ps1` | ✅ launcher and gitleaks SHA-256 verified; Python 3.12 environment, Chromium and web build, all inside the clone | 234.8 s |
| 1. `scripts\exa.ps1 status` | ⚠️ printed `database_connection_failed` ("may still be starting up") although the database was running. Bootstrap had just finished building the web app. `load.ps1`'s readiness check, which retries, found it ready a moment later. The README now says to run `status` again in that case | 18.8 s |
| 2. `scripts\load.ps1 -Set demo` | ✅ generated the SYNTHETIC files; 20 locations, 885,480 clean minutes, 1,315 events, 20 comparable location-months. One transient IMPORT transport error was retried automatically (D-032) | 24.8 s |
| 3. `scripts\start.ps1 -Port 8090` | ✅ `/api/health`: schema `VOLTPROOF_DEMO`, 20 locations, 1,315 events. `/api/meta`: `synthetic: true`. `/api/demo`: event `1-203001171842`, "Synthpur (SYNTHETIC) \| 2030-01-17 18:42". Home page: HTTP 200 | 13.2 s to the guided demo |
| **Clone to working app** | **steps above, end to end** | **328 s (5 min 28 s)** |
| 4. `scripts\test.ps1` (after stopping the app) | ✅ unit 27. Integration 70, 1 skipped (no 2019 month). Differential 2; the 2 real-data slice tests skipped with "raw files loaded in VOLTPROOF_DEMO are not present in data/raw". E2e 5, 1 skipped (no 2019 month). **All passed**; the real-data tests skip cleanly on a demo-only machine | 139 s |

Installing Podman and Exasol Personal is not in the 328 s. It is a one-time step that this run skipped,
because the database already existed. The clone is left in `D:\Temp\voltproof-clean-3`.
