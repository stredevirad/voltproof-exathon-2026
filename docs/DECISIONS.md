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
  the optional in-database orchestration (SHOULD), uses Lua. No Python SLC unless a later need is proven.

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

## D-017 · 2026-10-11 · One transaction per SQL step; statement ids proven against the audit log

- **Finding:** in autocommit mode Exasol inserts `COMMIT /* AUTO */` after every statement, so a
  "current statement − 1" lookup pointed at COMMITs (caught by `pipeline/check_provenance.py`: 6 of 11
  RUN_LOG ids were wrong).
- **Choice:** `run_steps` requires `autocommit=False` and commits once per step. A step that fails then
  rolls back as a unit, and `CURRENT_STATEMENT + 1` taken before each statement is exact. Result: 6/6 RUN_LOG
  rows match `EXA_DBA_AUDIT_SQL` by exact SQL text hash. The pre-fix dev RUN_LOG rows were deleted.

## D-018 · 2026-10-11 · NO_DATA represented as runs, not per-minute rows

- **Context:** the master prompt's `MINUTE_STATE` would synthesise one row per missing minute
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

## D-009 · 2026-10-11 · No geospatial features

- **Context:** the location metadata has no coordinates.
- **Choice:** coincidence comparison groups are administrative (same district, then same state). No ST_DISTANCE, no map. The GEOMETRY probe in G2 is informational only. The map moves to future scope.
