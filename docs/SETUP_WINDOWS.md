# Setup and run guide (Windows)

This guide takes a fresh Windows machine to a running VoltProof demo. Every step is a script in
`scripts\`. Times and sizes were measured on the build machine (Intel Core Ultra 5 125H, 15.6 GB RAM;
see docs/BENCHMARKS.md). The clean-start test (docs/VALIDATION.md) repeats this guide from a fresh clone.

## 0. What you need

| Requirement | Why | Check |
|---|---|---|
| Windows 10/11, **AMD64** | Exasol Personal local deployment (Windows ARM64 is not supported) | `$env:PROCESSOR_ARCHITECTURE` → `AMD64` |
| 16 GB RAM recommended | The database gets about 80% of the WSL memory (8.9 GiB on the build machine) | — |
| WSL 2 + virtualisation | Podman runs the database in a WSL 2 machine | `wsl --status` |
| Git, [uv](https://docs.astral.sh/uv/), Node.js ≥ 20 | code, Python environment, web app build | `git --version`, `uv --version`, `node --version` |
| Podman (installed in step 3) | container runtime for Exasol Personal | `podman --version` |
| Disk | **C:** about 3 GB (Podman machine + image); **repository drive** about 2 GB raw data + database volume (10 GB for the full Uttar Pradesh load) | `Get-PSDrive C, D` |

Keep Docker Desktop **closed** while the database runs; it shares the WSL memory.

## 1. Get the code

```powershell
git clone https://github.com/stredevirad/voltproof-exathon-2026.git D:\Projects\VoltProof
cd D:\Projects\VoltProof
```

## 2. Bootstrap (Python, tools, browser, web build): one command

```powershell
Set-ExecutionPolicy -Scope Process Bypass    # this terminal only; repeat in every new terminal
scripts\bootstrap.ps1
```

All of this goes into the repository's own gitignored folders (`.cache\`, `.tools\`, `.venv\`). Nothing is
installed system-wide.
- CPython 3.12 (managed by uv) and the locked Python dependencies.
- Exasol Launcher **v2.3.0** and gitleaks v8.30.1 from their GitHub releases, each **verified against the
  published SHA-256** before unpacking.
- Playwright Chromium (PDF reports and browser tests) and the web app build (`app\web\dist`).

## 3. Podman (one-time, may show a Windows admin prompt)

```powershell
winget install -e --id RedHat.Podman
```

Open a **new** terminal afterwards so `podman` is on PATH.

## 4. Start Exasol Personal (one-time install, then start/stop)

First check whether a deployment already exists and is running:

```powershell
scripts\exa.ps1 status                            # database_ready → skip to step 5
```

Only if there is no deployment yet:

```powershell
scripts\exa.ps1 install local --auto-approve     # first time: about 2 minutes
```

- This creates Podman's default WSL machine and starts a single-node Exasol Personal database.
  **Installing it means accepting the Exasol Personal End User License Agreement.**
- The deployment directory (configuration, `secrets.json`, **and the database data**) is
  `<repository drive>\ExasolDeployments\voltproof`. Set `EXASOL_DEPLOYMENT_DIR` in `.env` to choose
  another location.
- `scripts\exa.ps1` always passes that directory and refuses `destroy`/`remove`. Those commands delete
  without asking when scripted, so run them yourself if you ever need them.
- After a Windows reboot the database is stopped: `scripts\exa.ps1 start`.

## 5. Fastest path: the SYNTHETIC demo set (no download)

```powershell
scripts\load.ps1 -Set demo      # seconds; schema VOLTPROOF_DEMO
scripts\start.ps1               # → http://127.0.0.1:8000/
```

- `pipeline\synthetic.py` writes 20 invented monitors in the ESMI file format (one month, about 4 MB, the
  same every time) into `data\demo\`. They are built into their own schema, `VOLTPROOF_DEMO`, by the same
  SQL that analyses the real data.
- The app and every report show a **SYNTHETIC DEMO DATA** banner. Synthetic and real data never share a
  schema, and the tools that compute published figures refuse a synthetic schema (DECISIONS D-033).
- Steps 6–8 below build the real data. Once `VOLTPROOF` is built, `start.ps1`, `test.ps1` and `warmup.ps1`
  use it. To use the demo set again, set `$env:VOLTPROOF_SCHEMA = 'VOLTPROOF_DEMO'` in the terminal first.

## 6. Get the real data (Harvard Dataverse, Guestbook required)

The ESMI data is published by Prayas (Energy Group) on Harvard Dataverse (doi:10.7910/DVN/CLLZZM,
CC0 1.0; see docs/data/SOURCE_TERMS.md). Each download asks for a short Guestbook form. Choose one way:

- **Browser:** open https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/CLLZZM and
  download into `data\raw\` without renaming. For tabular files choose **"Original File Format
  (Comma Separated Values)"**.
  - **Minimum set ("first", ~141 MB):** `ESMI location information`, `About the initiative.pdf`,
    `ESMI minute-wise voltage data 2018 June-Aug`. Enough for the guided demo.
  - **Full Uttar Pradesh set ("up", ~1.9 GB):** add 2016 Jan-June, 2016 July-Dec, 2017 Jan-April,
    2017 May-Aug, 2017 Sept-Dec, 2018 Jan-May, 2018 Sep-Dec, 2019 Jan-June and 2019 July-Dec.
- **Script:** copy `.env.example` to `.env`, fill in **your own** `DATAVERSE_GB_*` details, then
  `scripts\get-data.ps1 -Set first -Download`.

Then verify the checksums against Dataverse (also run automatically by step 7):

```powershell
scripts\get-data.ps1 -Set first     # or -Set up
```

## 7. Build the analysis inside Exasol: one command

```powershell
scripts\load.ps1 -Set first     # minimum set; or -Set up for all of Uttar Pradesh 2016-2019
```

To build into a separate schema next to an existing build (for example a clean-start test), first set
`$env:VOLTPROOF_SCHEMA = 'VOLTPROOF_CLEAN'` in the terminal. `load.ps1`, `start.ps1` and `test.ps1` all
use it.

This:
1. verifies the files;
2. loads them with Exasol's native `IMPORT` (each line keeps its file and line number);
3. runs the versioned SQL steps `sql\020`–`sql\100` **inside Exasol**: unpivot, cleaning, segments,
   events, uncertainty, daily/monthly aggregates, quality, coincidence;
4. fails if a file looks malformed;
5. checks that every executed statement appears in Exasol's audit log.

**The first large load is slower:** Exasol grows its data volume file the first time.

## 8. Start the app: one command

```powershell
scripts\start.ps1               # → http://127.0.0.1:8000/
```

Open the URL and press **Start guided demo**. Stop with Ctrl+C. Don't run `load.ps1` while the app is
running. **How to use** in the menu explains every colour and number in plain words; a short tour appears on a
first visit.

**Your own readings:** **Upload your data** in the menu (or `python -m pipeline.upload`, see the README section
"Use your own data"). An upload needs at least 10 GB free on C: and is built while the app runs; only one build
(upload or `load.ps1`) runs at a time.

## 9. Run the tests

```powershell
scripts\test.ps1                 # unit, integration, differential, e2e (needs the database and step 5 or 7)
scripts\test.ps1 -Suite unit     # no database needed
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Exasol is not ready` | `scripts\exa.ps1 start` (the database stops when Windows restarts) |
| `podman` not found after installing | open a new terminal |
| `Port 8000 is already in use` | `scripts\start.ps1 -Port 8010` |
| A load step is very slow the first time | expected while the database volume grows; later loads are much faster (docs/BENCHMARKS.md) |
| Windows becomes sluggish during a full load | close other heavy apps and Docker Desktop; the database uses most of the WSL memory |
| `Raw files missing or not verified` | download the files into `data\raw\` with unchanged names (step 6) |
| Report generation fails | rerun `scripts\bootstrap.ps1` (installs Playwright Chromium) |
| An upload says another build is running ("Only one analysis can run at a time") | wait for the other build (an upload or `load.ps1`) to finish; one build runs at a time |
| An upload is refused | the page says why (for example not one reading a minute, or not a 230 V supply); the README section "Use your own data" lists the checks |
