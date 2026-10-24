# Progress log

## Gate status

| Gate | Status | Evidence / blocker |
|---|---|---|
| G0 Environment & repo | ✅ passed 2026-10-11 | Environment report below; scaffold committed (`20ef134`). Tag `gate-0-env` |
| G1 Data access & licence | ✅ passed 2026-10-11 | Terms + exact citation in `docs/data/SOURCE_TERMS.md`; 3 sample files MD5-verified (original CSV); 542,518 rows confirmed; outage = 0 V, missing = absent hours; corrections D-013 to D-016. Tag `gate-1-data` |
| G2 Exasol | ✅ passed 2026-10-11 | Native IMPORT 542,518 rows in 1.23 s; in-DB unpivot to 32,551,080 minutes in 4.8 s; first LAG+SUM islands query on real data identical to an independent raw-CSV check (Dhule 16-06-2018: 37-min outage 17:00–17:36). Tag `gate-2-exasol` |
| G3 Correctness core | ✅ passed 2026-10-11 | Full UP subset loads (102,845,781 minutes, 176 locations) in 194 s; fixtures F01–F18 + Hypothesis + real-data slices identical to the oracle; quality report renders. Tag `gate-3-correctness` |
| G4 Coincidence | ✅ passed 2026-10-11 | `sql/100_coincidence.sql`; F13/F14 hand expectations pass; SQL = oracle on all fixtures and on 2 real districts (20,127 pairs); sanity check of Bahraich 2018-07 documented in `docs/VALIDATION.md` §2. Tag `gate-4-coincidence` |
| G5 Product | ✅ passed 2026-10-11 | Guided demo works end to end on real data via `scripts\start.ps1`; Playwright e2e 3/3; report numbers = independent SQL (test_report.py) + rendered values; forbidden-phrase scan on every page and report. Tag `gate-5-product` |
| G6 Validation & hardening | ✅ passed 2026-10-12 | Prayas comparison (VALIDATION §3); 2019 defect handled (D-031); benchmarks 3 cold + 3 warm full-UP builds and query timings (BENCHMARKS.md); WHY_EXASOL; README; clean start from GitHub passed every README step (VALIDATION §4); TEST_REPORT 94/94 on 3889f1a. Tag `gate-6-validation` |
| G7 Submission | ✅ ready to submit 2026-10-24 (tag `gate-9-submission`) | Problem statement, deck, the team's narrated demo video (2:14), clean warm benchmarks, warm-up + live-demo runbook, README deliverables. No-download quick start with the SYNTHETIC demo set (D-033). GitHub Actions CI (ruff + unit) green. Candidate 3 (`5f1a4d3`) and the rework (`gate-8-rework`) stay tagged. Left: the team submits on the submit page by Sun 25 Oct 11:59 pm IST |
| Rework (Oct 15–17) | ✅ merged 2026-10-17 (merge `2ba9f0a`, tag `gate-8-rework`) | Uploads of your own data (D-037), the new look with measured contrast (D-038), the beginner's guide and tour (D-039), the simpler deck (D-040), docs. Merged after every condition held: the full test suite (docs/TEST_REPORT.md), the slow gate GO, the original-baseline comparison (approved changes only), the compliance check (all pass except the video, still to be recorded), a full-history secret scan, CI green, an independent review. Candidate 3 stays tagged |

## Remaining risks (top 5, updated 2026-10-24)

1. **RAM.** 15.6 GB total; the database's virtual machine grows during long test runs. Heavy test parts run under a
   free-memory guard and the database is restarted between steps when needed; other memory-heavy applications
   (browsers, chat apps) should be closed during builds and tests.
2. **C: disk.** 28 GB free (17 Oct); C: holds Podman's machine and image, the database volume is in the deployment
   folder on the repository's drive. Keep at least 10 GB free on both; uploads check both before building.
3. **Virtual demo day (Fri 6 Nov 2026, 10:00 am IST).** The video-call app needs memory next to the database and
   the app, and the call needs the network: LIVE_DEMO_RUNBOOK §4 (share only the browser window, check free memory
   with everything running, a phone hotspot ready). A deck without a working live demo is not scored.
4. **Data download gate.** A Guestbook response is required per download. Mitigated: the README quick start uses the
   SYNTHETIC demo set (no download), and the scripted download (`get-data.ps1 -Download`, the user's own `.env`
   details) was tested end to end.
5. **New platform path.** Windows local deployment is new in launcher 2.3.0 (released 2026-09-21); after a machine
   restart Podman's machine may need `podman machine stop` / `start` before `scripts\exa.ps1 start`. On 24 Oct a
   start hung for 9 minutes and left the status at "Operation 'start' is currently in progress";
   `scripts\exa.ps1 stop`, a Podman restart and `scripts\exa.ps1 start` fixed it (16 s).

---

## 2026-10-11 — Day 1

### Done
- Re-verified the competition page: no changes vs the brief (VERIFICATION_LOG C1–C9).
- Environment inventory (G0), recorded below.
- Exasol Personal docs v2.3 read in full for: requirements, local deployment, managed deployments, connect, limitations, UDFs, troubleshooting, release notes.
- ESMI dataset located on Harvard Dataverse via the native API: `doi:10.7910/DVN/CLLZZM`, **CC0 1.0**, 14 files, 2,185,993,808 bytes, Nov 2014 – Dec 2019. Row counts measured from DDI metadata (no download needed).
- Prayas thresholds and UP-article methodology captured verbatim (VERIFICATION_LOG P1–P11).
- Scaffold: `.gitignore`, `.gitattributes`, `CLAUDE.md`, `docs/{PROGRESS,DECISIONS,VERIFICATION_LOG}.md`, `.claude/settings.json` (project permissions; destroy/remove deny-listed, bypass mode disabled), verbatim brief in a gitignored private folder.
- uv-managed CPython 3.12.14 installed into `D:\Projects\VoltProof\.cache\uv-python`.
  - Side effects (uv defaults, not yet disabled at that point): a 47 KB launcher shim `C:\Users\LENOVO\.local\bin\python3.12.exe` and a PEP 514 registry entry under HKCU. Future installs use `--no-bin --no-registry`.

### G0 environment report (measured 2026-10-11)

| Item | Value |
|---|---|
| OS | Windows 11 Home Single Language, build 26200 (10.0.26200) |
| Machine | Lenovo 83DA · **Intel Core Ultra 5 125H** (14 cores / 18 threads) · **15.6 GB RAM** (3.5 GB free at check time) |
| Hypervisor | present (`HypervisorPresent=True`) |
| Disk | C: 32.2 GB free / D: 408.9 GB free |
| PowerShell | 5.1.26100.9444 (Windows PowerShell; `&&` not available) |
| Git | 2.51.0.windows.1 · branch `main`, no commits yet, origin = `https://github.com/stredevirad/voltproof-exathon-2026.git` |
| gh | 2.102.0, logged in as `stredevirad` (keyring) |
| Python | system 3.13.0 (`py -0p`); project uses uv-managed 3.12.14 |
| uv | 0.12.15 |
| pip | 26.2.1 (system Python 3.13) |
| Node / npm | v24.7.0 / 11.5.1 |
| winget | v1.29.380 |
| WSL | 2.7.13.0, kernel 6.18.33.2-2; distros Debian12 (default) + docker-desktop, both stopped; `.wslconfig`: memory=11GB, processors=18, swap=4GB |
| Docker Desktop | 28.3.3 installed; `docker_data.vhdx` = 22.69 GB on C: |
| Claude Code | 2.1.296 |
| **Missing** | **Podman**, **Exasol launcher**, **gitleaks** |

### Session 2 (same day): user approvals received
- Launcher v2.3.0 and gitleaks v8.30.1 downloaded, SHA-256 verified, unpacked to `.tools\`.
- User installed Podman 5.8.3. `scripts\exa.ps1` wrapper (always `--deployment-dir`, refuses destroy/remove, runs from `.cache\tmp`).
- `scripts\exa.ps1 install local --auto-approve`: **success in ~2 min**; status `database_ready`; Exasol `2026.2.0-nano.3`.
  - First attempt failed on wrapper argument handling (scalar splat) and PS 5.1 stderr→error conversion; both fixed.
- **Disk:** C: −2.90 GB (Podman 2.49 GB, launcher cache 0.13 GB), D: −2.19 GB. **DB data is on D:** (`<deployment>\local\runtime\exa`, bind-mounted; confirmed in launcher source). WSL move not needed (D-010).
- Probes: window functions, interval joins, ST_DISTANCE, Lua scripts + Lua UDFs, statistics, `EXA_DBA_AUDIT_SQL` (has rows) all ✅; Python UDF ❌ (needs SLC, not installed by design, D-011).
- Python env: `.venv` (3.12.14) via `uv sync`; `scripts\bootstrap.ps1` written and run (idempotent).
- DDI metadata shows **no blank minute cells** (missing data = whole missing location-hours) and voltage range 0–350 V.
- Spec-first: `docs/METHODOLOGY.md` v0.1 (rules R-1 to R-21), `config/method.yaml` (sourced parameters), `tests/oracle/reference.py` (independent oracle; hand-computed smoke case passes).
- Stray `NUL` file (Podman ssh known_hosts line) removed from the repo root; `.gitignore` guards it.
- **Commit still blocked** by the auto-mode classifier (no permission rule matches; see the checkpoint). Nothing committed yet.

### Session 3 (same day): user work order (history scan, resources, G1→G3)
- User committed the scaffold (`20ef134`, tag `gate-0-env`); all three teammates registered. Local commits are now authorised for Claude (no push).
- User decision: **no courtesy email to Prayas** (dropped).
- **Step 1, history scan:** `gitleaks git --redact -v` → 1 commit scanned (~184 KB), **no leaks found**. Commit contents checked: no data, `.cache`, `.tools`, `.venv` or private files.
- **Step 2, resource facts (measured 14:59 IST):**

| Resource | Value | Source |
|---|---|---|
| Host | Intel Core Ultra 5 125H, 15.6 GB RAM | G0 |
| WSL2 VM (shared by Podman + Docker Desktop) | 10,951 MiB RAM, 4,096 MiB swap, 18 CPUs | `.wslconfig` exists: `memory=11GB, processors=18, swap=4GB`; `free -m` in VM |
| Exasol container | no own cap (limit = VM, 11.48 GB) | `podman stats` |
| Exasol DB RAM | **8.9 GiB** (`dbram=auto`), 9 vCPU, 1 node | `EXA_SYSTEM_EVENTS`, `exasol.conf` |
| Connections | licence limit 20; `maxConnections` 18 | `EXA_SYSTEM_EVENTS.PARAMETERS`, `EXA_METADATA` |
| Free disk | C: 28.57 GB · D: 406.20 GB | `Get-PSDrive` |
| DB data location | D: (`D:\ExasolDeployments\voltproof\local\runtime\exa`) | launcher source + measurement |

  **Limits that could bite on the full UP load (2014–2018 national ≈ 6.6 M location-hours ≈ 396 M minute values; UP is a subset):**
  1. **Host RAM headroom:** 8.9 GiB DB RAM inside an 11 GB VM leaves Windows ~4.6 GB of the 15.6 GB. A browser + Playwright + VS Code during a heavy load could push Windows into paging. *Recommendation:* keep `.wslconfig` unchanged (11 GB); keep Docker Desktop off; avoid other heavy apps during full loads. Only if Windows becomes sluggish, consider `memory=10GB` (needs your approval; lowers DB RAM proportionally).
  2. **Storage I/O over the Windows→WSL bind mount (X22, unverified upstream):** measured during the G2 load, see below.
  3. **Disk:** no concern. Data grows on D: (406 GB free); C: only grows with images/SLCs.
  4. **Connections:** 18 usable. The app uses a small pool (≤4), tests ≤2.

- **G1 passed** (commit `a988ce8`, tag `gate-1-data`): see VERIFICATION_LOG G1f–G1n and DECISIONS D-013 to D-016.
- **G2 passed**: VERIFICATION_LOG G2a–G2d, X22 update, X31 (new risk: 1 GB preallocated volume).
- Working-tree gitleaks scan (`gitleaks dir .`) flagged 14 items, **all in ignored third-party files** (`.venv`, `.cache/uv`, gitleaks' own README). None are trackable. Pre-push scans will cover history + tracked files only.

### G3 (in progress)
- X31 resolved: the volume grows automatically (1 → 5 GB). **The first growth is slow** (130 M rows in 434 s while growing vs 21 s once grown, ~10 MB/s growth over the bind mount), so the cold-start cost will be documented in BENCHMARKS.
- Provenance verified: RUN_LOG (session, statement) ids match `EXA_DBA_AUDIT_SQL` by exact SQL text (6/6) after D-017 (one transaction per step).
- SQL steps 040 clean → 050 segments → 060 events → 070 uncertainty claims → 080 daily (full calendar) → 090 monthly, all reading thresholds from PARAMS. Reserved words hit: STATE, DAY (renamed SUPPLY_STATE, CAL_DAY).
- Real UP sample (98 locations with data, 2018 Jun–Aug, scope = Uttar Pradesh): 10,424,400 minutes → 188,544 segments → 52,810 outage events → 7,794 location-days → 270 location-months.
- **First oracle-vs-SQL differential on real data: PASS.** 4 UP locations, 4,930 events, 365 days, 12 months identical in every field (`tests/differential/test_real_slice.py`).
- User asked (via the G2 checkpoint) to download the 9 remaining UP-period files.

- Fixtures F01–F14 + harness (`tests/integration/test_fixtures.py`); sensitivity checks; loader edge cases (14 unit tests).
- Hypothesis differential: 40 random batches identical (VALIDATION §1).
- `sql/095_quality.sql`; `scripts\load.ps1` (verify → IMPORT → SQL → quality guard → provenance 55/55); `scripts\test.ps1`.
- **G4:** `sql/100_coincidence.sql` (pairs, chains/groups, shift baseline). Baseline went from 348 s to 1.8 s via bucketed equality joins (D-021). Real data: 26,075 pairs → 9,347 potential shared supply events. Bahraich 2018-07: 4,322 observed vs 2,149.6 expected pairs; example group of 17 monitors at 18:27–18:29 on 25 July 2018 (raw-CSV checked).

### Session 3 (continued): full UP data, G3 and G5 passed
- The user downloaded the 9 UP files (all original CSV, MD5-verified). Profiling found three real defects:
  2019 `M/D/YYYY` dates (D-025), a lost Hour column in 2019 July–Dec (excluded, D-026), and name variants
  with an added "[Offline]" (D-029). Each was handled with evidence and fixtures F16–F18.
- Scale: the first full build stalled (> 60 min) in two statements. Hour-level duplicate detection and
  single-window gaps-and-islands brought the full build to **160 s SQL / 194 s wall** (D-028).
- Advisor review fixes: baseline on comparable months only (D-023), stable keys (D-024), real-data tests
  read every loaded file.
- **Full test run on the full data (19:59 IST): unit 16, integration 63, differential 4 (Hypothesis 12 +
  real slices; 12.5 min), e2e 3, all passed.** Screenshots in `docs/deliverables/screenshots/`.
- G5: FastAPI API, React/ECharts app (colours validated, D-027), PDF evidence report, `scripts\start.ps1`
  (tested on port 8077), SETUP_WINDOWS, JUDGE_QA (22 questions), DEMO_SCRIPT, THIRD_PARTY_NOTICES.

### G6 (passed 2026-10-12)
- **Validation against Prayas (VALIDATION §3, done):**
  - `sql/110_validation_prayas_up.sql` (D-030 categories) and `pipeline/prayas_figures.py`, which reads
    Prayas's published charts.
  - **Agrees:** single-monitor profiles for 2017–2018 (34 monitor-months, ≤ 0.2 h/day in every class),
    Figure 8 time of day, Figure 9 evening, Sikanderabad and Baraulia anchors.
  - **Not reproduced:** Figure 2 daily averages (ours 2.0–2.6×) and Figure 5 duration mix. Investigated,
    nothing tuned.
- **Data finding (D-031, OPEN):** the 2019 Jan–Jun file omits most all-0 V hours, so 2019 outage is a lower
  bound. Awaiting the user's decision on handling (stop rule c).
- VALIDATION §2 regenerated from the full build (Bahraich 2018-07: 3,945 vs 1,827.5). JUDGE_QA #4, #7, #9,
  #11 and #19 updated; fixture count corrected to 18.

- **Decisions:** D-031 decided by the project owner; D-032 (retry a dropped IMPORT transfer once).
- **Benchmarks** (BENCHMARKS.md, generated from docs/benchmarks/*.jsonl): full UP build 252.8 s warm / 238.6 s
  cold (medians of 3). Two failed runs are listed: one IMPORT transport drop (ETL-5105), and one stopped by
  the 0.4 GiB free-RAM guard. Free RAM was raised with the owner's approval by stopping the Oracle services
  (the undo is in the private RAM_CHANGES.md).
- **Clean start** (VALIDATION §4): the README minimum set, a separate schema `VOLTPROOF_CLEAN` and the existing
  database. Two bugs were found and fixed: `start.ps1` with redirected output, and an e2e test that assumed
  the full data. The repeat from GitHub (225b3a0) passed every step.
- **Tests:** TEST_REPORT.md, 94/94 passed on 3889f1a (full UP build). The differential suite was run in parts
  (`test.ps1 -Part`).
- **Guards:** published-text guard (blocked phrases, internal references, control characters).
- **Grievance citation:** now rests on the UPERC 2003 regulations and PIB 2010 (VERIFICATION_LOG L1–L7). The
  Act's text was unreachable (India Code 504).

### G7 (in progress, 2026-10-12)
- **Problem statement** in the required one-sentence format: PROBLEM_STATEMENT.md (234 words), README line
  1, deck slide 1.
- **Clean warm benchmarks:** 210.4 s median of 3, with Oracle stopped and Chrome closed. The earlier warm
  runs, made with Oracle running, are listed as superseded. Cold runs: 238.6 s.
- **Reports:** a month's report now fetches its shared-event groups in one batch (175 groups: 13 s → 0.08 s;
  identical data). A fresh report takes about 3.7 s. An unchanged report is reused (same data and commit,
  shown with its generation time) in 0.4 s.
- **Warm-up:** `scripts\warmup.ps1` (about 4 s) brings the first day view after a restart from 2.1 s to
  0.13 s.
- **Live demo:** LIVE_DEMO_RUNBOOK.md has the checklist, click path, fallbacks and the 15-minute outline.
- **Robustness:** a status check retry (`Get-DatabaseStatus`), and a compile check for Python sources.
- **Cleanup:** VOLTPROOF_CLEAN dropped; the D:\Temp clones deleted.

### G7 work order 2 (2026-10-12, while the team records the voice-over)
- **No-download quick start (D-033):** `pipeline/synthetic.py` writes 20 invented monitors in three invented
  districts (January 2030, about 4 MB, fixed seed) in the ESMI file format. `scripts\load.ps1 -Set demo`
  builds them into `VOLTPROOF_DEMO`. Guards keep synthetic and real data apart. Every page and report carries
  a SYNTHETIC DEMO DATA banner, and the guided demo lands on the designed shared interruption.
- **Clean start from GitHub (35bc78a):** clone to working app in 328 s with no download; all suites passed
  in 139 s with the real-data tests skipped (VALIDATION §4.4).
- **Scripted Guestbook download:** `get-data.ps1 -Set first -Download` with the team's `.env` was tested
  into a separate folder (56 s; three files, MD5 verified against Dataverse), and the copies were deleted.
- **CI:** `.github/workflows/ci.yml` (windows-latest, actions pinned by SHA): ruff + unit tests, green on
  a150710. The database suites stay local. CONTRIBUTING.md added. The owner set the repository
  description and topics (exasol, sql, open-data, electricity, india, hackathon) with `gh repo edit`.
- **JUDGE_QA:** "Most consumers don't have a monitor. Who can use this today?" and "Is the demo data real?"
- **Tests:** TEST_REPORT 108/108 on a150710 (clean tree; the differential suite run in parts).

## 2026-10-15 to 2026-10-17 — October rework (branch `rework-oct15`, merged 17 Oct, tag `gate-8-rework`)

- **Audit fixes, candidate 3 (15 Oct):** path traversal on the static routes closed and a Host allowlist added;
  standard MIT licence (GitHub detects it); grievance wording limited to the UPERC 2003 regulations and the 2010 PIB
  release; disclaimer and data source on every PDF page; tests write their reports outside `reports/evidence`.
  Merged to main `5f1a4d3`, tag `gate-7-submission-candidate-3`.
- **Your own data (D-037):** upload page and `python -m pipeline.upload`; the same SQL in a separate schema owned by
  a restricted database user; uploaded files give the same results as the command-line build; honest labels.
- **The new look (D-038):** one lead number per page, plain captions, the "Civic calm" colours behind one switch,
  WCAG AA text contrast measured on every screen in light and dark, no sideways scroll on a phone, chart text readable
  in dark mode, table rows with real links; the day view draws every minute in any viewer time zone (F-09).
- **Beginner's guide and tour (D-039)** and **a simpler deck (D-040)**, each reviewed by an LLM council; every
  wording change reviewed line by line against the frozen wording.
- **Benchmarks not re-measured:** every SQL step the benchmarks time (`sql/010`–`sql/110`) is unchanged; the new SQL
  is only in `sql/ingest/` (uploads). The command-line build gained a build lock and a progress callback around
  the same statements.

## 2026-10-24 — Final submission (tag `gate-9-submission`)

- **Demo video:** the team recorded it live (2:14, 7,800,241 bytes, H.264 + AAC, 1600 × 960, subtitles burned in) and it is
  committed as `docs/deliverables/VoltProof_demo.mp4`; its narration differs from the voice-over script.
  `python -m pipeline.video check` now judges the competition limits (3:00 at most, 40 MB at most, H.264 + AAC) and
  only reports the frame size, which was fixed to the size of our own drafts.
- **Dates:** the rules page changed on 21 Oct (VERIFICATION_LOG C10): Top 5 Wed 4 Nov 6:00 pm, demo day and
  winners Fri 6 Nov 10:00 am IST, virtual. We keep the submit page's 25 Oct deadline.
- **Live demo:** LIVE_DEMO_RUNBOOK gained a virtual demo day section and the fix for a stuck database start.
- **Tests:** the full suite on the final commit (docs/TEST_REPORT.md). The slow gate was not re-run: no analysis code
  has changed since `77193d2`, where it last passed.

### Next (the team)
1. Submit on the submit page by **Sun 25 Oct 2026, 11:59 pm IST**: the repository, the deck PDF, the video and the
   problem statement.
2. Top 5 announced **Wed 4 Nov, 6:00 pm IST**. Before demo day: one full rehearsal on the demo laptop with the
   video-call app running (LIVE_DEMO_RUNBOOK §1 and §4).
3. Demo day **Fri 6 Nov, 10:00 am IST** (virtual): 15 minutes presentation + 5 minutes jury questions.
