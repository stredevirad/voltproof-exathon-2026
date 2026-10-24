# VoltProof — project rules for Claude Code

ExaThon India 2026, Track 3. Turns ESMI minute-wise voltage records (Prayas Energy Group) into traceable
evidence of power cuts and poor supply. The analysis runs **inside Exasol Personal**. The full brief is private
(not in the repository); local pointers are in the gitignored `CLAUDE.local.md`.

## Resume rule (every session)
1. Read this file, `docs/PROGRESS.md`, `docs/DECISIONS.md`.
2. Run G0-lite: `git status`, free space on C:/D:, `scripts\exa.ps1 status` (once the DB exists).
3. Continue from the first incomplete gate in PROGRESS. Trust only claims with recorded evidence.

## Gates (status lives in docs/PROGRESS.md)
G0 env · G1 data/licence · G2 Exasol · G3 correctness core · G4 coincidence · G5 product · G6 validation/hardening · G7 submission.
Tag each passed gate (`gate-N-name`). Deadline: submit by Sun 25 Oct 2026 11:59 pm IST (the submit page's date; the
main rules page, changed 21 Oct, says Sat 31 Oct, but we keep 25 Oct as binding). Top 5 announced Wed 4 Nov 6:00 pm
IST; demo day and winners Fri 6 Nov 10:00 am IST, virtual (15 min presentation + 5 min jury questions over video; a
deck and a working live demo are both required). Unrelated Oracle services on the build laptop stay stopped (Manual)
until after 6 Nov.

## Stack
- Python 3.12 (uv-managed, on D:), pyexasol, FastAPI, pytest + Hypothesis, Playwright (Python) for e2e + PDF.
- React + Vite + TypeScript + Apache ECharts, built to static files and served by FastAPI (one process).
- Exasol Personal via launcher **v2.3.0** (`.tools\exasol\exasol.exe`), local deployment through Podman's
  default machine; deployment dir `D:\ExasolDeployments\voltproof` (outside the repo).
- PowerShell scripts in `scripts\` are the entry points.

## Key paths
- `sql/` numbered DDL + analytical SQL. **The single source of analytical truth.**
- `pipeline/` download, checksum, load, run SQL steps, manifests (Python orchestration only).
- `config/method.yaml` thresholds and parameters, each with source URL + retrieval date.
- `tests/fixtures/` synthetic hand-specified CSV + expected YAML · `tests/oracle/` independent Python reference.
- `data/` (gitignored) raw downloads · `.cache/` (gitignored) uv/npm/playwright caches · `.tools/` (gitignored) binaries.
- `docs/` PROGRESS, DECISIONS, VERIFICATION_LOG, and the deliverable docs.

## Environment conventions
- All caches on D:. Scripts set `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `PIP_CACHE_DIR`, `npm_config_cache`,
  `PLAYWRIGHT_BROWSERS_PATH`, `TEMP`/`TMP` (for our tools) under `D:\Projects\VoltProof\.cache\`.
- `uv python install` must use `--no-bin --no-registry` (avoid writing shims to `~\.local\bin` or HKCU).
- **Every** launcher call goes through `scripts\exa.ps1`, which always passes `--deployment-dir`
  (a missing flag silently targets `~\.exasol\personal\deployments\default`).
- Exasol data physically lives in Podman's WSL disk on **C:**. Keep ≥10 GB free on C: at all times;
  measure before/after every load.
- Machine: Intel Core Ultra 5 125H, 15.6 GB RAM; `.wslconfig` caps WSL2 at 11 GB (shared with Docker Desktop).
  Docker Desktop should be quit while Exasol runs.

## Analytical rules (non-negotiable)
- Exasol does the analysis: classification, events, aggregates, coincidence = SQL in Exasol. Python only
  orchestrates, loads, presents, and hosts the separate test oracle.
- Raw ESMI files are wide (`Location name, Date, Hour, Min 0..Min 59`). Load as-is, unpivot **in SQL**.
- Prayas thresholds (default profile): OUTAGE ≤130 V · LOW 131–204 · NORMAL 205–270 · HIGH ≥271.
- **Missing data is never an outage.** NO_DATA is its own state; events bordering gaps get bounded
  certainty with min/max durations; the headline is the lower bound.
- Comparable month = coverage >90% (Prayas UP methodology).
- No coordinates in the source → no geospatial features; coincidence groups are administrative (district).

## Claims vocabulary
- Say "potential shared supply event"; never name an equipment fault or assert a common cause.
- Say "may warrant review through …"; never state an amount owed, an entitlement or a certainty claim.
- The exact blocked phrases (and internal-only terms) are in `tests/support/claims.py`; every tracked file is
  scanned by `tests/unit/test_published_text.py`.
- Label anything illustrative/simulated as **Illustrative**. Measured ≠ inferred, in every UI string and doc.
- Attribute "Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI)" wherever the data appears.

## Git
- Small commits at stable milestones; at least one per gate; tag gates. Never force-push or rewrite pushed history.
- Before every push: secret scan (gitleaks in `.tools\`), size check (>5 MB flagged; the one exception is the
  final narrated video `docs/deliverables/VoltProof_demo.mp4`, up to 40 MB, enforced by
  `tests/unit/test_tracked_sizes.py`), no raw data/private docs tracked.
- Pushing to origin was approved by the owner (the repository is public); every push still needs the checks above.

## Never do
- Never commit raw ESMI data, `.env`, `secrets.json`, the private docs folder (see `.gitignore`), or anything under `data/`.
- Never print or log credentials (Exasol `secrets.json`, guestbook details in `.env`).
- Never run `exasol destroy` / `exasol remove` (deny-listed; the human runs them if ever needed).
- Never change git remotes, create/rename repos, edit `.wslconfig`, or relocate WSL/Podman disks without approval.
- Never claim a test passed, a benchmark was measured, or a feature works without the actual output.
- Never tune parameters just to match Prayas's published numbers.
- Never invent thresholds or regulatory numbers; every value needs a cited primary source.
