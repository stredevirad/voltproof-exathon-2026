# Decisions

One entry per significant decision: context, options, choice, why. Newest at the bottom.

---

## D-001 · 2026-10-11 · Exasol launcher source and version

- **Context:** The documented `installer.sh` supports macOS/Linux only. Windows local deployment was added in launcher 2.3.0. An unversioned `latest/exasol.exe` also exists on S3.
- **Options:** (a) GitHub release asset `exasol-personal_Windows_x86_64.zip` v2.3.0 with published SHA256; (b) S3 `latest` exe (no checksum, moving target); (c) run the launcher inside WSL Debian.
- **Choice:** (a), pinned to **v2.3.0**, verified against `exasol-personal_2.3.0_checksums.txt`, extracted into `D:\Projects\VoltProof\.tools\exasol\` (gitignored, user-level, no admin).
- **Why:** checksummed, reproducible for judges, and it is the official native-Windows path. (c) would add a second Linux environment for no benefit.

## D-002 · 2026-10-11 · Deployment directory and launcher wrapper

- **Context:** `--deployment-dir` deployments are not listed by `exasol deployments list`. Forgetting the flag silently targets `~/.exasol/personal/deployments/default`.
- **Choice:** keep the deployment in `D:\ExasolDeployments\voltproof` (outside the repo). Every launcher call goes through one wrapper script that always passes `--deployment-dir` from `.env` (`EXASOL_DEPLOYMENT_DIR`).
- **Note:** this relocates only config/state/`secrets.json`. On Windows the **database data lives in Podman's default machine (a WSL disk image on C:)**. That is measured, not assumed (see PROGRESS).

## D-003 · 2026-10-11 · Destructive launcher commands are deny-listed

- **Context:** with no terminal attached (how Claude Code runs commands), `exasol destroy` / `exasol remove` proceed **without asking**, and `exasol slc install/update/remove` restart the DB without asking.
- **Choice:** project permissions deny `exasol destroy` and `exasol remove` outright (the human runs them if ever needed), and require a prompt for `exasol slc …`.

## D-004 · 2026-10-11 · Python toolchain

- **Context:** the system has Python 3.13.0 only; the plan says 3.12. uv 0.12.15 is installed.
- **Choice:** uv-managed **CPython 3.12** with `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` under `D:\Projects\VoltProof\.cache\`. No system-level install.
- **Why:** 3.12 has the broadest wheel support for pyexasol/Playwright/Hypothesis. uv makes the version reproducible for judges without touching their system Python.

## D-005 · 2026-10-11 · Node

- **Choice:** use the installed Node v24.7.0 (an LTS line) and npm 11.5.1. Pin the engine range `>=20` in `package.json`. No install.

## D-006 · 2026-10-11 · Data source, licence posture and redistribution

- **Context:** the Dataverse dataset `doi:10.7910/DVN/CLLZZM` is licensed CC0 1.0. Its description also carries Prayas "Terms of use" asking for non-commercial/academic/research use with clear acknowledgement, and for notification of use. Downloads require a Guestbook response.
- **Choice:** follow the stricter reading. Cite the dataset exactly as Dataverse specifies and credit Prayas (Energy Group) and ESMI everywhere. Never commit raw data (download script + checksums only; test fixtures are synthetic).
- **Why:** this satisfies both readings at no cost to the project. A competition entry with an open-source, non-commercial tool is research/demo use.
- **Update 2026-10-11 (user decision):** no courtesy email will be sent. The draft was removed from all to-do lists.

## D-007 · 2026-10-11 · Raw layout: load wide, unpivot inside Exasol

- **Context:** source files are wide (`Location name, Date, Hour, Min 0..Min 59`).
- **Choice:** load each file as-is into a 63-column `RAW_HOURLY` table, plus `source_file`/`source_row`. Unpivot to minute rows **in SQL inside Exasol**.
- **Why:** keeps "raw untouched" and "Exasol does the analysis" both true, and makes the unpivot step itself a measurable Exasol workload.

## D-008 · 2026-10-11 · Default thresholds = Prayas ESMI definitions

- **Choice:** the default method profile uses Prayas's published classes: OUTAGE ≤130 V, LOW 131–204 V, NORMAL 205–270 V, HIGH ≥271 V (integer volts; boundary handling to be confirmed against real value types). Source: https://energy.prayaspune.org/how-does-esmi-work (retrieved 2026-10-11). A second profile based on an official supply-voltage regulation is added only if we find and cite the primary text.
- **Comparable-coverage threshold:** >90% per location-month, matching Prayas's UP methodology ("more than 90% of data was available").

## D-010 · 2026-10-11 · Leave the Podman WSL disk on C: (for now)

- **Context:** the user asked whether Podman's WSL disk can move to D:. WSL 2.7.13 supports
  `wsl --manage podman-machine-default --move D:\WSL\podman-machine-default` (machine stopped first).
- **Finding:** the launcher bind-mounts the database data directory from the deployment directory, which
  is already on D:. The C: footprint is ~2.9 GB in total and does not grow with our data volume (only with
  images and SLCs).
- **Choice:** don't move it. If C: ever drops near the 10 GB floor, the move command is
  `podman machine stop` → `wsl --manage podman-machine-default --move D:\WSL\podman-machine-default` →
  `podman machine start` → `scripts\exa.ps1 start`. It needs user approval. Risk: Podman's machine JSON
  records the original path, so `podman machine inspect/rm` may report or act on a stale path. That is untested.

## D-011 · 2026-10-11 · No Python SLC; Lua where per-location logic is needed

- **Context:** Python UDFs need `exasol slc install python3`, which restarts the DB and adds image
  size on C:. Lua scripts and Lua scalar UDFs work out of the box (probed).
- **Choice:** the core pipeline is pure SQL (window functions). Any per-location procedural step, and
  the optional in-database orchestration (SHOULD), uses Lua. No Python SLC unless a later need is shown.

## D-012 · 2026-10-11 · TLS handling for the local DB

- **Choice:** pyexasol with `encryption=True` and certificate validation skipped **only** when the host is
  loopback (the launcher marks the local deployment `insecureSkipCertValidation: true` and serves a
  self-signed certificate). Any non-loopback host raises an error unless validated normally
  (`pipeline/db.py`).

## D-013 · 2026-10-11 · No upper plausibility cut on voltage (correction from G1)

- **Assumption corrected:** `max_valid_v: 350` (provisional, from Dataverse DDI stats for three columns).
- **Real data (2018 June–Aug, 32,551,080 readings):** maximum 364 V. 285 readings are exactly 350 V,
  284 of them at one monitor (Pachmori), which ramps 213→312→324→350 and then stays flat for whole
  hours. That is sensor saturation, so the true value is ≥350 V. One 364 V reading (Saraswati Nagar
  Risiya) is a transient at supply restoration within a 300–330 V stretch.
- **Choice:** no upper cut (`max_valid_v: null`). Both cases are real HIGH readings; quarantining them
  would hide over-voltage evidence. The data-quality output reports the observed maximum and the count
  of readings at exactly 350 V.

## D-014 · 2026-10-11 · Keep Prayas's ≤130 V "no supply" rule; report the 0 V share separately

- **Real data:** 4,337,926 readings are 0 V and 254,214 are 1–130 V (5.5% of outage minutes). 101 V
  occurs 116,494 times (≈25× its neighbours) at 102 monitors, and 99 V 15,694 times at 25 monitors.
  Both appear inside deep sags (e.g. …120, 117, 101, 106, 101, 101…), never as a whole hour. They look
  like device measurement floors.
- **Choice:** classification stays exactly as Prayas defines it (≤130 V = no supply), so no headline
  number or legal framing changes. For transparency, aggregates and reports also give the **0 V
  minutes** within outage minutes (R-16b), and the UI labels non-zero outage minutes "voltage too low
  to use (≤130 V, Prayas definition)".

## D-015 · 2026-10-11 · Timestamps treated as local Indian time

- **Evidence:** Prayas documents `Hour` as "Hour of the day (0 to 23)" (About the initiative.pdf) and
  analyses an "evening" window of 5–11 pm on the same data. No time zone is stated.
- **Choice:** treat timestamps as local Indian time (IST) without conversion, and say so in reports.

## D-016 · 2026-10-11 · Location identity and categories

- **Real data:** 528 location rows with unique names; 177 names carry the suffix " [Offline]". The data
  file uses exactly the same names (0 unmatched in 2018 June–Aug), suffix included. The `Category`
  vocabulary is **Gram Panchayat / District Headquarters / State Capital / Other Municipal Area**, not
  Prayas's "megacity / other municipal area / rural". UP has 179 locations (Prayas's article counts
  163 for 2016–19) across 17 districts (the article says 14).
- **Choice:** `LOCATION_ID` is a surrogate integer key. The full source name is kept for joins and
  provenance, and the display name drops " [Offline]" (kept as a separate `IS_OFFLINE` flag). The
  source category is stored verbatim. Mapping it to Prayas's three groups is a **validation-time
  decision (G6)**: Gram Panchayat→rural is direct; "megacity" needs city-level judgement. Both the
  mapping and any locations that can't be reproduced will be documented in VALIDATION.md.

## D-007 (refined) · 2026-10-11 · Raw table design after G1

- Raw wide rows are loaded **as text** (`RAW_HOURLY`: 63 VARCHAR columns + source file id + source line
  number), so the stored raw is byte-faithful. Every parse, check and quarantine rule (R-1 to R-3)
  then runs in SQL.
- The analytical layer is **long** (`MINUTE_READING`: location_id, ts, voltage), produced by an
  in-database unpivot. The long form is what window functions need for gaps-and-islands across hour
  boundaries. The wide form is kept only as the untouched raw layer, where it is 60× fewer rows to import.

## D-017 · 2026-10-11 · One transaction per SQL step; statement ids verified against the audit log

- **Finding:** in autocommit mode Exasol inserts `COMMIT /* AUTO */` after every statement, so a
  "current statement − 1" lookup pointed at COMMITs (caught by `pipeline/check_provenance.py`: 6 of 11
  RUN_LOG ids were wrong).
- **Choice:** `run_steps` requires `autocommit=False` and commits once per step. A step that fails then
  rolls back as a unit, and `CURRENT_STATEMENT + 1` taken before each statement is exact. Result: 6/6 RUN_LOG
  rows match `EXA_DBA_AUDIT_SQL` by exact SQL text hash. The pre-fix dev RUN_LOG rows were deleted.

## D-018 · 2026-10-11 · NO_DATA represented as runs, not per-minute rows

- **Context:** the initial design's `MINUTE_STATE` would synthesise one row per missing minute
  (hundreds of millions of rows for UP 2016–19).
- **Choice:** `SEGMENT` holds maximal runs per location: measured state runs (gaps-and-islands over
  readings, breaking on a state change **or** a non-consecutive minute) plus NO_DATA runs derived
  from the gaps between them (`LEAD`). The semantics are identical (R-6); storage is O(runs). Daily
  measures use interval-overlap arithmetic over a full **location × day calendar** covering each
  monitoring window, so days with no readings at all are kept (coverage 0).

## D-019 · 2026-10-11 · Analytical subset filter

- Raw files are always loaded whole. The unpivot (step 030) keeps only the subset in PARAMS:
  `subset.states` (comma-separated `STATE_NAME`s; empty = all) and `subset.locations` (optional source
  names, for small dev runs). Default: `Uttar Pradesh`. The fixture schema overrides it to all.

## D-020 · 2026-10-11 · Precise definitions for coincidence (R-19 to R-21)

- R-19 pair: two interruptions at different locations in the same district with
  `|start_A − start_B| ≤ Δ` and measured overlap `≥ θ` minutes.
- R-20 group: start-time chains per district (a chain breaks when consecutive starts are > Δ apart).
  A chain is a potential shared supply event if it contains ≥ 1 coincident pair. Its members are the
  chain's events that take part in at least one such pair. One window pass, no graph algorithm.
- R-21 baseline: per district and calendar month (D days), locations ordered by LOCATION_ID get
  index j = 0…L−1. For k = 1…N, every event of location j moves by `(j·k) mod D` days, wrapping within
  the month. Expected = mean coincident-pair count over the N shifts. Empirical p = share of shifts
  whose count ≥ observed. Details and caveats are in METHODOLOGY.

## D-021 · 2026-10-11 · Band joins via time buckets (coincidence)

- **Measured problem:** the R-21 baseline as one statement with a non-equality time band over 1.1 M
  shifted copies took **348 s** on the 2018 Jun–Aug UP sample, and a "cross join to two keys" variant
  was slower still (killed after 10 min).
- **Choice:** materialise the shifted copies, give every interruption a time bucket of width ≥ Δ, and
  run two plain equality joins (bucket + 0, bucket + 1) with the exact band filter applied afterwards.
  Each pair is found exactly once. Result: the whole coincidence step takes **1.8 s** (pairs 0.15 s, was 9.2 s).
  Unchanged results: 26,075 pairs; the k = 0 baseline count equals `COINCIDENT_PAIR` (26,075), and
  everything still equals the independent oracle.

## D-022 · 2026-10-11 · Baseline resolution and reporting

- With N = 20 shifts the smallest resolvable empirical p is 1/20. A p of 0 is reported as "< 0.05"
  ("none of 20 shifted versions reached the observed count"), never as a p-value of zero.

## D-023 · 2026-10-11 · Chance baseline on comparable location-months only

- **Problem (advisor review):** a shifted event can land on days its partner was not monitored, which
  lowers "expected" and overstates the observed/expected ratio. Large UP districts lose monitors
  mid-quarter (Bahraich 25 → 21 → 19 locations).
- **Choice:** `coincidence.baseline_comparable_only: true` (default). Observed and shifted counts use
  only interruptions of comparable location-months. Pairs and groups are still reported for every
  interruption. The mod-30 alignment effect (conservative) is disclosed in METHODOLOGY R-21.

## D-024 · 2026-10-11 · Stable keys

- `EVENT_KEY = LOCATION_ID || '-' || start minute`, and `GROUP_KEY = district | start minute`, are used in
  URLs, report ids and tests. `EVENT_ID` and `GROUP_ID` renumber on rebuild. `LOCATION_ID` stays stable
  as long as the location file is unchanged (it is the rank of the source name).

## D-025 · 2026-10-11 · Date format detected per file, in SQL (correction from the full download)

- **Real data:** the two 2019 files use `M/D/YYYY` (e.g. `1/1/2019`; the July–Dec file starts at
  `7/1/2019`; the 2nd part reaches 31). All 2014–2018 files use `DD-MM-YYYY`. 2019 Jan–June also
  holds 72 `#VALUE!` dates and 50 rows dated July–November.
- **Choice:** `FILE_DATE_FORMAT` (step 030) detects the format per file from the data. Dash dates
  follow the documented ESMI convention `DD-MM-YYYY` unless the data contradicts it. Slash dates
  must be decidable (one part > 12), otherwise they are quarantined as `ambiguous_date_format`, never
  guessed. Fixtures F16/F17 cover this.

## D-026 · 2026-10-11 · Declared file periods; 2019 July–Dec excluded from the analysis

- `config/source_files.yaml` records each file's declared period (from its Dataverse description).
  Rows dated outside it are quarantined (`outside_declared_period`).
- **2019 July–Dec has lost its Hour column:** 690,915 of 695,974 rows say hour 0, and every
  location-day appears as 24 rows all labelled 0 (e.g. Adgaon-Nashik 7/1/2019). Minute timestamps
  could only be guessed from row order. The file is loaded raw (verified, traceable) but excluded from
  the analysis with that documented reason, which `QUALITY_FILE` shows. Validation is unaffected:
  Prayas's UP article was published on 7 Aug 2019.

## D-027 · 2026-10-11 · Colour encoding (validated, not eyeballed)

- **Calendar:** a single-hue orange sequential ramp (OKLCH at the outage hue, lightness strictly
  decreasing 0.958 → 0.400) with 6 binned classes, **instead of the brief's "red-and-green"
  calendar**. Red/green fails the most common colour-vision deficiency. Days read for less than 90%
  of their minutes are hatched grey and labelled, never coloured as if complete.
- **States:** OUTAGE = orange, LOW = blue, HIGH = aqua, from the reference palette's first three slots.
  They pass `validate_palette.js --pairs all` in both modes: worst CVD ΔE 9.2 light / 9.4 dark; normal
  vision 24.0 / 20.9. Aqua is below 3:1 contrast on light, so it is always shown with a text label. The
  voltage line is neutral ink. NO_DATA is a hatched pattern with the words "no reading — not counted as
  outage". State is also encoded by position (horizontal class bands with text labels), so colour is
  never the only cue.
- Rejected after validation: status yellow (fails the lightness band as a mark colour); orange + red
  together (normal-vision ΔE 10.8 < 15); blue + violet in dark mode (protan ΔE 1.9).

## D-028 · 2026-10-11 · Formulations that scale to the full UP load (measured)

The first full Uttar Pradesh build (90.5 M minutes then; 102.8 M after D-029) was dominated by two
statements that were fine at sample scale (10.4 M minutes):

| Step | Before | After | Change (same semantics; fixtures + oracle) |
|---|---|---|---|
| 040 duplicates/conflicts | > 50 min, 7.1 GB temp RAM, spilled (killed) | **24 s** | Repeats are found on the ~1.7 M **hour-rows** (a repeated minute can only come from a repeated hour-row). Only those hours are grouped per minute; the rest pass through |
| 050 runs (gaps-and-islands) | **665 s**, ~6 GB temp RAM | **54 s** | One window function: `minute_number − ROW_NUMBER() OVER (PARTITION BY location, state ORDER BY ts)` is constant along a run, replacing LAG + running SUM (two full sorts) |
| `READING_STATE` | 90 M-row table | view | It is only a CASE over `READING_CLEAN`; materialising it rewrote ~1 GB for no gain |

Result: the full build takes **160 s of SQL** (194 s wall) on the build machine. All fixture, Hypothesis and
real-data oracle tests are re-run on the new formulations.

## D-029 · 2026-10-11 · Location-name matching (status marker and spacing)

- **Real data:** the 2019 Jan–June file names locations with an added `" [Offline]"` status marker and
  sometimes doubled spaces (e.g. `Jagatapur-Bahraich [Offline]`, `Kakatiya Nagar- Hyderabad  [Offline]`).
  Exact matching quarantined 559,269 of its 894,850 rows. Prayas documents `[Offline]` as a status
  ("monitoring … discontinued"), not part of the identity.
- **Choice:** exact name first. Otherwise a normalised key (lower case, `[offline]` removed, no spaces
  around hyphens, single spaces), but only when that key identifies **exactly one** location (no
  location-file key is ambiguous). The method per raw name is recorded in `NAME_MATCH`, and `QUALITY_FILE`
  counts the rows matched this way.
- **Not done:** fuzzy matching. 19 names still match nothing (e.g. `Bhubaneswar_5`, `KT_4355`,
  `Varanasi_7721`, three Sultanpur spellings) and stay quarantined as `unknown_location`. Guessing an
  identity would be worse than reporting it. Effect on UP: 67 monitors' 2019 data recovered (2019 Jan–June
  in-scope minutes 5.06 M → 17.44 M); remaining quarantine in that file is 27,964 rows. Fixture F18.

## D-009 · 2026-10-11 · No geospatial features

- **Context:** the location metadata has no coordinates.
- **Choice:** coincidence comparison groups are administrative (same district, then same state). No ST_DISTANCE, no map. The GEOMETRY probe in G2 is informational only. The map moves to future scope.

## D-030 · 2026-10-11 · Prayas UP categories for validation

- **Context:** Prayas groups UP monitors as megacity / other municipal area / rural (Table 1: 9 + 7,
  57 + 11 and 79 + 0 domestic + non-domestic). Our location file has State Capital, District
  Headquarters, Other Municipal Area and Gram Panchayat, with no "megacity" field.
- **Choice:** megacity = State Capital (Lucknow) plus the Kanpur District Headquarters monitors (Kanpur is
  the other UP city that would be called a megacity); other municipal = other District Headquarters and
  Other Municipal Area; rural = Gram Panchayat. This gives 10 + 7, 66 + 6 and 86 + 1, the closest match
  of the mappings tried. Prayas's list of monitors is not published, so the mapping cannot be checked
  monitor by monitor. Lucknow alone is also reported, because Prayas's evening text names Lucknow.
- **Where:** `sql/110_validation_prayas_up.sql` (`VALIDATION_CATEGORY`); used only for validation, not
  in the product.

## D-031 · 2026-10-11, decided 2026-10-12 · 2019 Jan–Jun file omits most all-zero hours

- **Finding:** see VALIDATION §3.4. The 2019 Jan–June CSV lacks most location-hours in which every
  minute read 0 V. Prayas's own charts count them as no supply. Normal, low and high minutes agree with
  Prayas's charts to within 0.2 h/day; only the no-supply hours are missing from the file.
- **Current handling (unchanged rules):** the absent hours are NO_DATA (R-2: missing data is never an
  outage). 2019 outage is therefore a lower bound; most affected months fail the 90% coverage rule and
  are flagged as not comparable. Nothing is inferred from the 0 V readings on either side of a gap,
  beyond the existing upper bound (R-15: at most 60 minutes of a gap next to each outage edge).
- **Decision (project owner, 2026-10-12):** keep the rules unchanged and add a plain, descriptive warning.
  - **Where the warning appears:** the Sources page, and every view and evidence report covering a day in
    2019 January–June. It is presentation only: `data_warning` in `config/source_files.yaml`, read by the
    app. No SQL, oracle or number changes.
  - **Headline and aggregate figures** in the README, deck, JUDGE_QA and the app's overview use 2016–2018,
    the validated years (`pipeline/headline_figures.py` → docs/HEADLINE_FIGURES.md). Scale figures (rows
    and minutes processed) still describe the full load.
  - **2019 months** stay visible, labelled as lower bounds.
- **Recorded as stated by the project owner:** the decision was made before looking at whether it changes
  any headline in our favour.
- **For the record:** the 2016–2018-only variant was already reported in VALIDATION §3.3 before this
  decision (outage min/day 56.3 / 189.5 / 566.3, against 55.6 / 174.4 / 555.2 for the primary definition).
  VALIDATION §3 keeps its pre-stated primary definition (2016-01 to 2019-06).

## D-032 · 2026-10-12 · Retry a dropped IMPORT transfer once

- **Observed:** during a benchmark build (2026-10-12, docs/BENCHMARKS.md), IMPORT of one file failed with
  `ETL-5105 … failed after 174960452 bytes … SSL_ERROR_SYSCALL … Failure when receiving data from the
  peer`. The HTTP transport between the Windows client and the database VM dropped mid-file. Free host
  RAM was low (about 0.5 GiB) during these builds.
- **Effect:** the file's transaction rolled back, including its DELETE, so the raw and analytical tables
  stayed intact. The build failed loudly.
- **Choice:** `load_file` retries a file **once** after rolling it back, and only for this transport error
  (`is_transient_import_error`). Data errors (for example ETL-3050) are never retried. The row-count
  check (loaded = data lines) still runs after the retry, and each file records `attempts`.
- **Tests:** `tests/unit/test_loader_edge_cases.py` checks that a transient error is retried once, that a
  second failure is raised, and that a data error is not retried.

## D-033 · 2026-10-12 · SYNTHETIC demo data set for a no-download quick start

- **Need:** judges should be able to try the app without the Dataverse Guestbook download.
- **Choice:** `pipeline/synthetic.py` writes invented monitors in the exact ESMI file format into
  `data/demo/` (gitignored):
  - 20 monitors in 3 invented districts of an invented state, January 2030;
  - a fixed seed and CRLF line endings, so the output is byte-identical every time, about 4 MB;
  - outages, low and high voltage, missing hours, one duplicate hour, and one evening interruption shared
    by all 9 monitors of the largest district, which the guided demo picks.

  `scripts\load.ps1 -Set demo` builds it into its own schema, **VOLTPROOF_DEMO**, with
  `config/method.demo.yaml`. That file changes only the scope, the guided-demo window and the dataset
  label; every analytical threshold is unchanged.
- **Kept apart from real data:**
  - **Names:** SYNTHETIC appears in every file, location, district and state name. File ids are
    900000001+, never Dataverse ids. Dates are outside every real file's period.
  - **Builds:** the build refuses to put the demo set into VOLTPROOF, and refuses to mix synthetic and
    real files in one schema.
  - **Real-data tools:** headline figures, benchmarks, the Prayas comparison and standalone SQL steps all
    refuse a synthetic schema.
  - **App and reports:** a persistent banner on every page, a SYNTHETIC footer, a SYNTHETIC citation and
    attribution, and dataset-aware page text. Reports get a `VP-DEMO-` id, a banner, a footer label and
    a SYNTHETIC limitation.
- **Tests:**
  - **Unit:** the files are byte-identical every time, and the format matches the real files.
  - **Integration:** the set builds, holds only synthetic data, the guided demo lands on the designed
    event, and reports are labelled. The independent oracle equals the SQL on the **whole** synthetic
    set (events, aggregates, coincidence).
  - **e2e:** every page shows the banner and passes the claims scan, and no distinctive real-data value
    or real place name appears.
- **Schema used by the scripts:** `start`, `test` and `warmup` use VOLTPROOF_SCHEMA if set, otherwise
  VOLTPROOF if it is built, otherwise VOLTPROOF_DEMO.

## D-034 · 2026-10-15 · Real-data coincidence test scoped to June–August 2018

- **Problem:** `test_coincidence_sql_matches_oracle_on_two_real_districts` gives the independent oracle every
  minute of two districts. It was written on the 2018 June–August file and grew with the data: on the full
  Uttar Pradesh build (2016–2019) the test process needed about 8.7 GB, and free RAM on the 15.6 GB development
  laptop fell to 0.31 GB.
- **Choice (team decision):** the test compares the SQL with the oracle on June–August 2018, the scope it was
  designed on, with the same assertions:
  - the two districts with the most coincident pairs in that window, and all their monitors;
  - pairs with both starts, groups whose first member starts, and baseline months inside the window.

  The oracle streams only the rows of those monitors dated 31 May to 1 September from the files that cover
  them. The extra day on each side makes outages that cross 1 June or 1 September start at the same minute as
  in the SQL, which reads the files as one continuous record (gap bridging is off, so one day is enough).
- **This is an exception, not compliance:** the test now checks less than before. The SQL-vs-oracle comparison of
  coincidences on real data no longer covers 2016, 2017 or 2019, so a coincidence defect that showed only in
  those years would not be caught by this test. The coincidence rules are still checked in full on the
  synthetic set and by the hand-written fixtures (D-033).
- **Proof:**
  - On a build of only the 2018 June–August file, the original and the scoped test chose the same districts
    (Bahraich, Barabanki), gave the oracle the same 88,608 rows and produced identical SQL and oracle results
    (20,127 pairs, 6,683 groups, 6 baseline rows). Both passed, and both failed when one pair was removed or
    one start was moved by a minute.
  - On the full build the scoped test passes in about 45 s, and free RAM stayed above 2.4 GB.
  - The 76 pairs that the one-file build has in addition all start at 1 June 00:00: outages that began in
    May, cut at the file edge.
- **Unchanged:** the oracle, the SQL, the event and aggregate test on the real slice (it still reads every
  file), the Hypothesis tests and the 18 fixtures. No test was skipped or weakened.

## D-035 · 2026-10-15 · The verification log stays as a history

- **Problem:** `docs/VERIFICATION_LOG.md` records every external fact we checked during the build, including legal
  sources that the app, the reports, the deck and the README no longer cite (the grievance route is now cited only
  from the UPERC 2003 regulations and the 2010 PIB release).
- **Choice (team decision):** keep the log unchanged as a record of what was checked and when, with one line at
  the top saying that items it does not verify are not cited anywhere in the app, the reports, the deck or the
  README. It is a working record, not a claim to users; `tests/unit/test_grievance_wording.py` already treats it
  as record-only.

## D-036 · 2026-10-16 · ECharts advisory: escape tooltip text, keep ECharts 5.6

- **Problem:** `npm audit` reports a moderate advisory for ECharts before 6.1.0: text placed in a tooltip is
  shown as HTML. Uploads bring text from users' files into the app.
- **Choice:** no user text is placed in chart tooltips or labels (only dates, numbers and fixed wording), and every
  tooltip value goes through `esc()` (`app/web/src/charts.tsx`). ECharts stays at 5.6: version 6 changes the
  default chart styling, which we would have to re-check on every screen a week before submission.
- **Also:** evidence reports carry a Content-Security-Policy that lets them load nothing (no scripts, images or
  network requests), and names are escaped by the report template.

## D-037 · 2026-10-16 · Upload your own voltage data: same SQL, its own database user, honest labels

- **What:** a person can upload 1-minute voltage readings (the ESMI layout, also as the Harvard Dataverse `.tab`
  file, or one reading per line) on the Upload page or with `python -m pipeline.upload`. The file stays on this
  computer (`data/uploads/<id>/`, gitignored) and can be deleted with one button.
- **Same analysis:** the upload is staged unchanged in its own schema `VP_USER_<id>`, checked by SQL
  (`sql/ingest/u20_validate.sql`), turned into the standard raw rows (`u30_canonical.sql`: dates written one way,
  confirmed 1-24 hours shifted, readings in one-per-line files pivoted to the hourly layout with missing minutes
  left empty) and analysed by the unchanged steps 020-100, with provenance checked against Exasol's audit log.
  Checked by tests: the SYNTHETIC demo files uploaded give the same 33 result tables as the command-line demo build;
  the 2018 June-August ESMI file uploaded gives the same figures as its command-line build for every Uttar Pradesh
  location and district; the same readings one per line, in a semicolon file with decimal commas, or with a
  12-hour clock give the same results.
- **Isolation:** the upload schema is created by a separate database user (`VP_UPLOADER`) that the database
  refuses any access to the Prayas and SYNTHETIC schemas. User text never enters SQL text. The API answers a
  dataset only from a whitelist (`ds`), and requests that change an upload need the page's own header and origin.
  One database build at a time (a lock shared with the command-line build).
- **The data decides, the user confirms, nothing is guessed:** the day/month order is taken from the data whenever
  a date part is above 12; the user is asked only when it cannot be decided, and an answer never overrides the
  data. Hours 1-24, time zones (only +05:30 is accepted, as India time; one-per-line files must be confirmed as
  local clock time) and typed district and state are asked in plain words, and the summary shows how a date is
  read ("03/04/2018 is read as 3 April 2018").
- **Refused, with the reason:** not numbers; outside 0-500 V; not a 230 V supply (almost every reading at or
  below 130 V, or a typical supply reading outside 150-300 V, counting only readings above 130 V so that a home
  with many cuts is not refused); not 1-minute data; a broken hour column; other time zones; Excel workbooks
  (save as CSV); files over 150 MB (measured: a 140 MB file is checked and built in about a minute and a half, with free memory never below
  1 GB on the 16 GB laptop).
- **Labels:** uploaded data is never presented as Prayas data: banner "Uploaded data — not verified by VoltProof",
  report ids `VP-USER-`, a diagonal mark and a footer on every PDF page, its own file name, time and SHA-256 as the
  source, and a general grievance sentence outside Uttar Pradesh.
- **Unchanged:** sql/010-110, `config/method.yaml`, the oracle, the fixtures and every existing test; the
  command-line builds (`load.ps1 -Set first|up|demo`) behave exactly as before.

## D-038 · 2026-10-16 · Web app look: "Civic calm", one lead number per page, measured contrast

- **What:** the pages lead with one thing each: on the month page the tile "Outage time (at least)" comes first and
  largest, and "Generate evidence report" is its only filled button; the guided demo and the evidence report sit in
  marked cards. Each number tile has a one-line plain explanation under it (new text; no figure or existing sentence
  changed). Calm teal header and footer, white cards, a rule under section titles, page titles in a system serif;
  numbers stay in the sans font with tabular figures. System fonts only, nothing loaded from the internet.
- **What did not change:** every number, the chart state colours (orange outage ramp, blue low, green high, hatched
  grey for no reading; D-027), the frozen wording and the SYNTHETIC and UPLOADED banners (still a warm warning colour,
  never teal), every test id.
- **Why:** before, every card looked the same and the eye had nowhere to start; and the old blue links and buttons
  were just below WCAG AA contrast (4.2-4.4:1; 3.6:1 for the dark-mode button) while pages scrolled sideways on a
  375 px phone.
- **Checked by tests** (`tests/e2e/test_ui_quality.py`, plus the SYNTHETIC and upload page tests): every visible text
  element meets WCAG AA against its background on every screen, light and dark; no sideways scrolling at 375 px;
  the month page leads with the outage lower bound and has one filled button; table rows that open something hold a
  real link or button (keyboard and screen readers, audit F-14). These tests fail on the previous look.
- **Charts in dark mode:** chart text, grid and axes now take the page's colours, so they are readable on the dark
  background; the heat map writes white figures on its darkest step (12 h or more) for contrast. The calendar legend
  is page text, so it wraps on a phone.
- **One switch back:** the look is the `data-skin="civic"` attribute on `<html>` (`app/web/index.html`); without it
  the plain look returns, keeps the page structure, and also passes the contrast checks.
- **Wording after review:** the lead tile says exactly what is measured ("Time when the voltage read 130 V or less,
  which Prayas counts as no supply. Only minutes with a reading count, so this is a minimum.") and its range line says
  "if every minute with no reading next to an outage was also an outage"; the caution box under "Coincidence is not
  cause" has a neutral bar (orange stays for outage data); the chosen monitor is marked by a tick and bold text, not by
  colour alone.

## D-039 · 2026-10-16 · A beginner's guide and an optional first-visit tour

- **What:** a "How to use VoltProof" page (`/guide`, "How to use" in the menu, and "How to read this page" on every
  month page) explains in plain words what VoltProof does and whose data it shows, what the colours and classes mean,
  how to pick a place and read a month and a day (including exact, bounded and censored), the shared-supply check
  (timing only, coincidence is not cause), the evidence report, what VoltProof can and cannot tell you, and uploads.
  It adapts to the dataset: it names Prayas's data only on Prayas's data.
- **Orientation on the pages themselves**, for people who arrive by a link: the start page says these are historical
  records from monitors in Uttar Pradesh, 2016–2019, not the reader's own supply today, and that an unlisted area has no
  record here (the 2019 lower-bound sentence follows on its own line, unchanged); every month page says it shows one
  monitor in one month, which may not be typical; "Minutes read" says it is not a measure of supply quality; the
  report card says the report ends with where a consumer can seek redress (no law named on the page; the report's own
  section carries the sources).
- **Tour:** five short steps on the start page (welcome, the guided demo, picking a place, the dataset switcher when
  there are several datasets, the guide). It appears on a person's first visit, can be skipped (button or Escape) or
  finished, is remembered in this browser's storage (if storage is blocked it simply shows again next time), and can
  be reopened from the guide. Automated browsers (tests, screenshots, the demo recording) never see it unless the
  address asks for it with `?tour=1`.
- **Not done (council P4-A):** a derived "days without supply" figure (a new number), Hindi, more tours, glossary
  pop-ups. **Checked by tests:** `tests/e2e/test_guide.py` (every dataset kind, attribution, blocked words, contrast,
  phone width, tour first visit / finish / skip / Escape / reopen / storage blocked / SYNTHETIC set, stable step count)
  and new assertions in `tests/e2e/test_ui_quality.py` and `tests/e2e/test_upload_ui.py`.

## D-040 · 2026-10-16 · The deck tells one story for a non-technical judge; the figures move to an appendix

- **What:** `docs/deliverables/deck/deck.html` (built into `VoltProof_deck.pdf` by `python -m pipeline.deck`) now
  follows one story, one idea per slide: the shopkeeper's problem (Illustrative), the record that already exists,
  what VoltProof gives him, one evening in Bahraich, how it works in four plain steps, how Exasol Personal is used
  (one diagram with the same four steps, the in-Exasol timings and the audit-log match), why the numbers can be
  checked, the data defects, where we differ from Prayas, what VoltProof does not claim, what changes if adopted, and
  the team.
- **Nothing dropped:** the earlier slides with benchmarks, correctness evidence, the validation table and the data
  defects are kept word for word as appendix A1-A4; A5 adds the headline figures and the "150 of 276 district-months,
  about 13 by chance" sentence from the README. The problem statement, the attribution and every frozen sentence are
  unchanged; every number on a slide also appears in the README or docs (checked by the deck build).
- **No speed comparison** with other engines is made (as in `docs/WHY_EXASOL.md`); the only before/after timings are
  VoltProof's own SQL fixes, timed from Exasol's audit log.
