# Progress log

## Gate status

| Gate | Status | Evidence / blocker |
|---|---|---|
| G0 Environment & repo | ✅ passed 2026-10-11 (commit pending) | Environment report below; scaffold staged. The local `git commit` was denied twice at the permission prompt, so it awaits user approval. Tag `gate-0-env` follows the commit |
| G1 Data access & licence | ✅ passed 2026-10-11 | Terms + exact citation in `docs/data/SOURCE_TERMS.md`; 3 sample files MD5-verified (original CSV); 542,518 rows confirmed; outage = 0 V, missing = absent hours; corrections D-013 to D-016. Tag `gate-1-data` |
| G2 Exasol | 🟡 DB running; needs the real sample | Exasol 2026.2.0-nano.3 installed via `scripts\exa.ps1 install local`; pyexasol 2.4.1 connects; feature probes recorded (`reports/exasol_probes.json`). Pass criterion (one real ESMI query) pending the sample |
| G3 Correctness core | ⬜ not started | — |
| G4 Coincidence | ⬜ not started | — |
| G5 Product | ⬜ not started | — |
| G6 Validation & hardening | ⬜ not started | — |
| G7 Submission | ⬜ not started | — |

## Remaining risks (top 5)

1. **C: disk.** 32.2 GB free; Exasol data will live in Podman's WSL disk on C:. Docker Desktop already uses 22.7 GB there. Growth per million rows must be measured before sizing the load.
2. **RAM.** 15.6 GB total (not 24 GB); WSL2 is capped at 11 GB and shared with Docker Desktop. The UP subset should fit; the full national load may not.
3. **Data download gate.** A Guestbook response is required per download. Judges will need to supply their own details (the reproducibility story must cover this).
4. **New platform path.** Windows local deployment is new in launcher 2.3.0 (released 2026-09-21); expect rough edges.
5. **Schedule.** ~7 build days; SHOULD items only after G6.

---

## 2026-10-11 — Day 1

### Done
- Re-verified the competition page: no changes vs the brief (VERIFICATION_LOG C1–C9).
- Environment inventory (G0), recorded below.
- Exasol Personal docs v2.3 read in full for: requirements, local deployment, managed deployments, connect, limitations, UDFs, troubleshooting, release notes.
- ESMI dataset located on Harvard Dataverse via the native API: `doi:10.7910/DVN/CLLZZM`, **CC0 1.0**, 14 files, 2,185,993,808 bytes, Nov 2014 – Dec 2019. Row counts measured from DDI metadata (no download needed).
- Prayas thresholds and UP-article methodology captured verbatim (VERIFICATION_LOG P1–P11).
- Scaffold: `.gitignore`, `.gitattributes`, `CLAUDE.md`, `docs/{PROGRESS,DECISIONS,VERIFICATION_LOG}.md`, `.claude/settings.json` (project permissions; destroy/remove deny-listed, bypass mode disabled), verbatim prompt in `docs/private/`.
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
- **Step 1, history scan:** `gitleaks git --redact -v` → 1 commit scanned (~184 KB), **no leaks found**. Commit contents checked: no data, `.cache`, `.tools`, `.venv` or `docs/private`.
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

### Next
1. G1 inspection + G2 load and first real query (files landed 14:50–14:54, MD5-verified).
2. G1: download the location file + `About the initiative.pdf` + one data file; inspect the real encodings; write `docs/data/SOURCE_TERMS.md`.
3. G2: install the launcher, have the user install Podman, run `exasol install local` into `D:\ExasolDeployments\voltproof`, measure C:, load the sample, run the first window-function query.
