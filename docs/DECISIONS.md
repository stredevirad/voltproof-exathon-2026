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
- **Choice:** follow the stricter reading. Attribute Prayas (Energy Group) and ESMI everywhere. Never commit raw data (download script + checksums only; test fixtures are synthetic). Send a courtesy notification to esmi@prayaspune.org (human action).
- **Why:** this satisfies both readings at no cost to the project. A competition entry with an open-source, non-commercial tool is research/demo use.

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

## D-009 · 2026-10-11 · No geospatial features

- **Context:** the location metadata has no coordinates.
- **Choice:** coincidence comparison groups are administrative (same district, then same state). No ST_DISTANCE, no map. The GEOMETRY probe in G2 is informational only. The map moves to future scope.
