# Verification log

> This log is a history of what was checked and when. Items not verified here (⏳ not checked, ❌ contradicted) are not cited anywhere in the app, the reports, the deck or the README.

Every external fact we rely on, checked by hand. The last column records whether the check agreed with
our initial planning assumption. Raw evidence copies are kept locally in a gitignored evidence folder
(third-party pages are not redistributed).

Legend: ✅ verified · ⚠️ verified with differences · ❌ contradicted · ⏳ not yet checked

## 2026-10-11 (Day 1, G0/G1/G2 groundwork)

### Environment

| # | Claim | How checked | Result | Initial assumption agreed? |
|---|---|---|---|---|
| E1 | Hardware is AMD Ryzen 9 8940HX, 24 GB RAM | `Get-CimInstance Win32_Processor / Win32_OperatingSystem` | ❌ **Intel Core Ultra 5 125H (14 cores / 18 threads), 15.6 GB RAM**, Lenovo 83DA | No: prompt snapshot was wrong or from another machine |
| E2 | Claude Code v2.1.289 | `claude --version` | ⚠️ 2.1.296 | Minor version drift |
| E3 | ~32 GB free on C:, ~408 GB on D: | `Get-PSDrive` | ✅ C: 32.2 GB free, D: 408.9 GB free | Yes |
| E4 | WSL2 available | `wsl --status`, `wsl --version` | ✅ WSL 2.7.13.0, kernel 6.18.33.2-2, default v2; distros Debian12 + docker-desktop (both stopped) | n/a |
| E5 | WSL memory | `%USERPROFILE%\.wslconfig` (read only) | ✅ `memory=11GB, processors=18, swap=4GB`, shared by all WSL2 distros incl. Docker Desktop and any Podman machine | n/a |
| E6 | Virtualisation enabled | `Win32_ComputerSystem.HypervisorPresent` | ✅ True (Win32_Processor.VirtualizationFirmwareEnabled reads False, which is normal when Hyper-V is already running) | n/a |
| E7 | Docker Desktop disk on C: | file listing | ✅ `docker_data.vhdx` 22.69 GB on C: | n/a (not in prompt) |

### Competition (https://www.exasol.com/events/exathon-india-2026/)

| # | Claim | Result |
|---|---|---|
| C1 | Registration closes Thu 15 Oct 2026 11:59 pm IST | ✅ (page also states registration opened Mon 05 Oct 2026 12:00 pm) |
| C2 | Submission deadline Sun 25 Oct 2026 11:59 pm IST | ✅ |
| C3 | Finalists Fri 30 Oct 6:00 pm, Demo day Wed 04 Nov 10:00 am | ✅ |
| C4 | Teams 1–3; Exasol Personal must be the data platform; public or synthetic data only; original work in challenge window; any language/LLM | ✅ quoted: "Public or synthetic data only. No employer data and nothing proprietary." / "Exasol Personal must be used as the project's data platform." |
| C5 | Licence Apache 2.0 or MIT | ✅ "Public GitHub repository under an OSI-approved licence (Apache 2.0 or MIT)." |
| C6 | Deliverables: problem statement, public repo, deck (PDF/PPT), video ≤3 min, README, deployment + run guide, licence | ✅ |
| C7 | Stage 1 weights 25/25/20/15/10/5; Stage 2 40/30/20/10; 15 min + 5 min Q&A | ✅ |
| C8 | Prizes ₹75k/40k/20k + ₹15k Biggest Impact Idea | ✅ |
| C9 | Track 3 "Factories, Fleets & Supply Chains" includes energy | ✅ "Manufacturing, logistics, mobility, and energy. Work with operational data that is delayed, distributed, incomplete, or difficult to use." |

No differences from the prompt found.

### Exasol Personal (docs v2.3, https://exasol.github.io/exasol-personal/2.3/)

| # | Claim (initial assumption) | Source | Result |
|---|---|---|---|
| X1 | Windows amd64 local deployment supported via Podman | system-requirements, local-deployment, release notes 2.3.0 (2026-09-21) | ✅ "Windows: Windows 10 or later on AMD64, Windows Package Manager (winget), and the prerequisites for a Podman machine." Added in launcher 2.3.0. |
| X2 | Launcher asks before installing Podman | local-deployment | ✅ "the launcher displays the exact command and asks for approval"; non-interactive runs **refuse** unless `--auto-approve` |
| X3 | Launcher for Windows | GitHub release v2.3.0 assets | ✅ `exasol-personal_Windows_x86_64.zip` (140,278,281 bytes), SHA256 `6300c83528d2f6a7a79a468351564bc75e88004f07b5cf28429be80ff94e6fcf` from `exasol-personal_2.3.0_checksums.txt`. The documented `installer.sh` explicitly supports only macOS/Linux. |
| X4 | PowerShell starter kit `irm …starter-kit.ps1 \| iex` | README | ⚠️ Current README documents a starter kit via `curl https://www.exasol.com/install/ \| sh` (MCP server + agent skills). Not inspected yet; not needed for MVP. |
| X5 | `--deployment-dir` supported | manage-deployments | ✅ "select an arbitrary path with --deployment-dir <path>". Such deployments are **not** listed by `exasol deployments list`. Default: `~/.exasol/personal/deployments/default`. |
| X6 | Database data location on Windows | local-deployment | ✅ "On Windows, the database runs through Podman's default machine" → data lives in the Podman machine's WSL disk (expected under the user profile on C:). **To be measured.** |
| X7 | No SLC installed by default; `exasol slc install python3` | limitations, udfs | ✅ verbatim. Installing an SLC **restarts the database**; with no terminal attached it restarts **without asking**. |
| X8 | Single node; Admin UI cloud-only | limitations | ✅ "A local deployment always runs as a single node." "Exasol Admin is available on cloud deployments only." |
| X9 | 20 connections limit | — | ⏳ not found in v2.3 docs pages read; check in DB (G2) |
| X10 | Lua scripting native | — | ⏳ probe in G2 |
| X11 | Audit (EXA_DBA_AUDIT_SQL) on local | — | ⏳ probe in G2 |
| X12 | Default credentials | local-deployment | ✅ "The initial local database credentials are sys / exasol." Credentials are in the deployment's `secrets.json`. |
| X13 | Destructive commands without a terminal | manage-deployments | ✅ "a command with no terminal attached proceeds without asking, so a script that reaches exasol destroy or exasol remove destroys the deployment." → deny-listed in project permissions. |
| X14 | Database licence | privacy-and-licensing | ✅ "Exasol Database is proprietary software provided by Exasol AG and is free for personal use." Deploying accepts the Exasol Personal EULA. Launcher is MIT. |
| X15 | Windows reboot behaviour | troubleshooting | ✅ deployment shows `stopped` after reboot; `exasol start` restarts it (and the Podman machine). |

### ESMI data (Harvard Dataverse native API)

| # | Claim | Source | Result | Initial assumption agreed? |
|---|---|---|---|---|
| D3a | Formal licence unknown ("public domain" informally) | `GET https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/CLLZZM` | ✅ **Licence field: CC0 1.0** (`http://creativecommons.org/publicdomain/zero/1.0`, SPDX `CC0-1.0`). Version 2.0, released 2021-02-18. | Resolves the licence question |
| D3b | Terms of use text | same, `dsDescription` | ⚠️ Description also contains: "Anybody is welcome to make full use of the information available herein for any non-commercial, academic and research purpose, provided source of the information is clearly acknowledged. We will highly appreciate if we are intimated of use of this data…" → We follow the **stricter** reading (attribution, non-commercial research/demo use, no raw redistribution) and send Prayas a courtesy note. | n/a |
| D3c | Download gate | `GET /api/guestbooks/251` | ⚠️ Every file download requires a **Guestbook** response: name, email, institution, position (all required) and "Brief dscription of the intended use of the downloaded data." (required). The API supports supplying it via POST (Dataverse 6.10.1 Data Access API docs). | Not anticipated |
| D4 | Data may end ~2021 | file list | ⚠️ Files cover **Nov 2014 – Dec 2019** (14 files: 2014…2018 as ingested `.tab`, 2019 as two `.csv`). Description says Nov 2014–Dec 2018 (not updated after the 2019 files were added). `dateOfCollectionStart` 2014-11-01. | Partly: data ends 2019, not 2021 |
| D2 | ~600M minute rows (estimate) | DDI metadata `GET /api/access/datafile/{id}/metadata/ddi` (no download needed) | ⚠️ **2014–2018: 6,601,854 location-hour rows → 396,111,240 minute values (measured from DDI caseQnty).** 2019 CSVs (428 MB) are not ingested, so their row count is not yet measured. | Lower than the ~600M estimate |
| G1a | Format | DDI + description | ✅ **Wide format:** `Location name, Date, Hour (0–23), Min 0 … Min 59` (63 columns). Location file: 528 rows × 7 cols `Location name, From date, To date, District, State, Category, Connection Type`. | Initially assumed long format |
| G1b | Outage encoding | dataset description | ✅ "A '0' voltage reading means a power outage" and "Missing data should be interpreted as unavailable data and not as interruption". Some locations marked "[Offline]" = monitoring discontinued. **Still to confirm empirically on a real sample.** | Consistent with our rule "missing ≠ outage" |
| G1c | Coordinates available | DDI variable list | ❌ **No coordinates.** Only district/state. → no ST_DISTANCE, no map; comparison groups are district-based. | Initially flagged as conditional |
| G1d | Category vocabulary | description | ⚠️ Source categories "rural, town, or a mega city"; Prayas UP article uses megacity / other municipal area / rural. Mapping to be confirmed on the real location file. | n/a |
| G1e | Monitor accuracy | description | ✅ "measures and records voltage with an accuracy of +/- 4 V … for every minute" | n/a |
| G1f | Checksums | dataset JSON | ✅ MD5 per file listed (e.g. location file `f3e785dd06350a6c8e714ceca9b743a7`). Which variant (`.tab` vs `?format=original`) the MD5 refers to is **not yet verified**. | n/a |

### Prayas ESMI publications

| # | Claim | Source | Result | Initial assumption agreed? |
|---|---|---|---|---|
| P1 | Thresholds | https://energy.prayaspune.org/how-does-esmi-work | ✅ "a broad voltage range of 205 to 270 V … is marked as 'Normal'. Voltage from 204 V and upto 131 V is shown as 'Low' voltage and voltage above 271 V is marked as 'High' voltage. Voltage below 131 (i.e. 130 and less) is considered as no supply (or zero voltage)". Also: "Any voltage below 130 V is treated as no-supply condition for calculating these interruptions". | New information (no initial assumption) |
| P2 | Interruption bands | same | ✅ "A short interruption is classified as one which lasts between 2-15 minutes and 16-60 minutes … A long interruption … 1-3 hours and more than 3 hours" → suggests interruptions are counted from **2 minutes**; to be treated as a method parameter, both 1-min and 2-min variants reported in validation. | New |
| P3 | Scale | same + ESMI blog | ✅ "more than 89 districts spread over 20 states", "more than 400 consumer locations", "almost 10 million location hours of data"; data "available in the public domain on watchyourpower.org and the Harvard Dataverse" | ✅ |
| P4 | UP article metadata | https://energy.prayaspune.org/our-work/article-and-blog/esmi-in-uttar-pradesh | ✅ "ESMI in Uttar Pradesh", 07 Aug 2019, S. Kulkarni, A. Sahasrabudhe, A. Chunekar, S. Dixit | — |
| P5 | UP locations | same, Table 1 | ✅ Megacity 9 domestic + 7 non-domestic = 16; Other municipal 57 + 11 = 68; Rural 79 + 0 = 79; **Total 145 + 18 = 163**; "about 160 … locations … over the years 2016-19, spread across 14 districts" | ✅ |
| P6 | **Coverage filter used by Prayas** | same | ✅ "Data from a location was considered for months only where more than 90% of data was available." → our default `comparable_coverage_threshold` must be **>90%** for validation | New, important |
| P7 | Daily outage duration | same | ✅ "megacity locations experienced 21 minutes of daily outage, while that was about 90 minutes for locations in other municipal areas. Rural areas … in excess of 4 hours (>240 minutes) a day." | ✅ |
| P8 | Outages per day | same | ✅ "megacity … a couple of outages a day on an average, … other municipal areas … nearly five outages a day while rural locations experienced up to 10 outages a day." | ✅ |
| P9 | Evening outages | same | ✅ "Lucknow … did not receive the entire six hours of evening supply between 5 and 11pm, and faced 12 minutes of outage on an average every day. This increased to about 53 minutes … other municipal areas and close to 1 hour and 30 minutes … in rural areas" | ✅ (note: the megacity evening figure is **Lucknow**, not all megacities) |
| P10 | >270 V / >300 V | same | ✅ Sikanderabad (Sitapur): "around 12 hours of high voltage (>270 volts) supply each day in the initial month"; Baraulia (Barabanki): "high voltage supply exceeding 300 volts on multiple occasions" | ✅ |
| P11 | Duration mix | same | ✅ "About 37% of the outages … were longer than three hours each, and another 33% outages ranged between one - three hours long" (extra validation target) | New |
| P12 | Figure 2 | same, `/images/ESMI-blog/4-Uttar-Pradesh/4_UP_2_Daily_outage.png` (viewed 2026-10-11) | ✅ "Daily hours of outage averaged from 2016 to 2019": megacity 21 minutes, other municipal 1 hour 27 min, rural 4 hours 20 min; range bars up to ≈1.3 / ≈14.8 / ≈14.4 h/day | New |
| P13 | Figure 5 | `4_UP_5_Outage_breakup.png` | ✅ "Duration-wise breakup of outages across all ESMI locations": up to 15 min 11%, 15 min–1 hour 19%, 1–3 hours 33%, more than 3 hours 37% | New |
| P14 | Figures 6, 8 | `4_UP_6_daily_interruptions.png`, `4_UP_8_Outage_ToD.png` | ✅ Fig 6: monthly interruptions/day per category, Jan 2016–Nov 2019 with gaps (no megacity bars Jan–Oct 2019; no rural Feb 2016, Jun–Aug 2016, Mar–Jun 2019). Fig 8: heatmap of hours of outage within each 6-hour slot (scale 0–5 h), one column per month | New |
| P15 | Figure 9 | `4_UP_9_EHS.png` | ✅ "Daily evening hours of supply": Megacity 5 hr 48 min, Other Municipal Area 5 hr 7 min, Rural 3 hr 36 min (the bulb is labelled "Megacity"; the text says Lucknow and, for rural, "close to 1 hour and 30 minutes" of outage) | New |
| P16 | Figures 10–12, 14 | `4_UP_10_…SIkanderabad.png`, `4_UP_11_Biswan.png`, `4_UP_12_…Baraulia.png`, `4_UP_14_Huzurpur_road_Kaisarganj.png` | ✅ Monthly stacked hours/day by class (normal, low, high, no supply, no data) per monitor. Huzurpur road Kaisarganj is our location 182, **not** the demo monitor 183 (Huzurpur-Bahraich) | New |

### Exasol deployment and probes (2026-10-11, measured on this machine)

| # | Claim | How checked | Result |
|---|---|---|---|
| X16 | Launcher binary | GitHub release v2.3.0 zip, SHA256 compared with `exasol-personal_2.3.0_checksums.txt` | ✅ match `6300c835…f6a7a79a…6fcf`; `exasol version` → `2.3.0` |
| X17 | gitleaks binary | release v8.30.1 zip vs `gitleaks_8.30.1_checksums.txt` | ✅ match `d29144de…afc4e`; `gitleaks version` → `8.30.1` |
| X18 | Podman | `podman --version` (user-installed via winget) | ✅ 5.8.3 |
| X19 | Install path | `scripts\exa.ps1 install local --auto-approve` | ✅ completed in ~2 min (14:26:08 → 14:28:19 IST). Launcher ran `podman machine init --disk-size 40` (source: `internal/podmanmachine/podmanmachine.go` @v2.3.0) and imported `quay.io/podman/machine-os:5.8` into WSL as `podman-machine-default` |
| X20 | DB version | `SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME='databaseProductVersion'` | ✅ `2026.2.0-nano.3` |
| **X6 (corrected)** | "Database data lives in the Podman machine's disk on C:" | launcher source `internal/localinstall/podman_install.go` (`-v <DataDir>:/exa:Z`) + `internal/localruntime/host_runtime.go` (`DataDir = <deployment>/local/runtime/exa`) + measurement | ❌ **The data directory is a bind mount from the deployment directory on the host: `D:\ExasolDeployments\voltproof\local\runtime\exa` (2.003 GB after install).** The Podman disk on C: holds the machine OS and the loaded database image. |
| X21 | Disk impact of install | free space before/after (`disk_before_install.json`) | C: 31.895 → 28.999 GB (**−2.90 GB**: Podman machine dir 2.49 GB incl. `ext4.vhdx` 1.51 GB; `%LOCALAPPDATA%\.exasol` runtime cache 0.13 GB; Podman program 0.06 GB). D: 408.515 → 406.329 GB (−2.19 GB; deployment dir 2.0 GB) |
| X22 | Upstream verification status of Windows local | `openspec/changes/add-windows-host-podman-runtime/tasks.md` @v2.3.0 | ⚠️ Open items: "5.5 Verify the Windows lifecycle on a Windows AMD64 runner" and "5.6 Confirm the database tolerates its data directory being reached across the Podman machine's filesystem passthrough". → **I/O over the Windows→WSL passthrough is a known-unverified path; watch for errors and slow writes, and report timings honestly.** |
| X23 | Python client | pyexasol 2.4.1, `encryption=True`, cert validation skipped for loopback only (launcher's own `insecureSkipCertValidation: true`) | ✅ session opened; queries ran |
| X24 | Window functions (LAG, running SUM) | `pipeline/probe_exasol.py` | ✅ gaps-and-islands toy case returned 4 islands as expected |
| X25 | Interval self-join | same | ✅ |
| X26 | GEOMETRY / ST_DISTANCE | same | ✅ `ST_DISTANCE('POINT(0 0)','POINT(3 4)') = 5` (not needed: no coordinates in the data) |
| X10 | Lua scripting native | same | ✅ `EXECUTE SCRIPT` works (`exit({rows_affected=…})`); **Lua scalar UDFs also work without any SLC** |
| D6 | Python UDF needs SLC | same | ✅ confirmed: "No usable script language container is installed for the requested language." (`SCRIPT_LANGUAGES` lists `PYTHON3=builtin_python3` but no container is present) |
| X27 | FLUSH STATISTICS + EXA_SQL_LAST_DAY | same | ✅ rows present after flush |
| X11 / D7 | EXA_DBA_AUDIT_SQL on local | same | ✅ table is readable as `sys` and **contains rows** (auditing appears active). No AUDIT parameter visible in EXA_METADATA. Column-level use to be checked in G5 |
| X9 | 20-connection limit | `EXA_SYSTEM_EVENTS.PARAMETERS` at STARTUP; `EXA_METADATA.maxConnections` | ✅ `-maxConnectionsLicenseLimit=20`; `maxConnections = 18` reported to clients |
| X29 | DB RAM | `EXA_SYSTEM_EVENTS` (STARTUP 2026-10-11 08:58 UTC), `exasol.conf` `[DB_PARAMS] dbram=auto` | ✅ `DB_RAM_SIZE = 8.9` GiB, `VCPU = 9`, 1 node; `EXA_DB_SIZE_LAST_DAY.RECOMMENDED_DB_RAM_SIZE = 8.9` |
| X30 | WSL/Podman VM limits | `.wslconfig` (memory=11GB, processors=18, swap=4GB); `free -m` / `nproc` inside `podman-machine-default` | ✅ VM sees 10,951 MiB RAM, 4,096 MiB swap, 18 CPUs; container has no own memory cap (`podman stats`: limit 11.48 GB = VM) |
| X28 | `wsl --manage <distro> --move <Location>` | `wsl --help` (WSL 2.7.13) | ✅ supported, also `--set-sparse`. **Not used** (see DECISIONS D-010) |

### G1 real-sample inspection (2026-10-11; files downloaded by the user via browser, 14:50–14:54 IST)

| # | Claim / question | How checked | Result |
|---|---|---|---|
| G1f | Which variant the published MD5 describes | `scripts\get-data.ps1 -Set first` | ✅ **Original-format CSV** files match the published MD5 exactly (all 3 files `verified`). A `.tab` export therefore cannot match; the verifier now accepts it by exact size + DDI row count (`verified-size-and-rows`, unit-tested) |
| G1g | Formats | `head` / `cat -A`; `pipeline/profile_raw.py` | ✅ ASCII, comma-separated, CRLF, header row. Dates **`DD-MM-YYYY`** in both files; `Hour` 0–23; 63 columns in every one of the 542,518 rows |
| G1h | Row count 2018 June–Aug | line count + profiler | ✅ **542,518** data rows (= Dataverse observation count); 295 locations; 2018-06-01 to 2018-08-31 |
| G1i | Missing data encoding | profiler | ✅ 0 blank, 0 non-numeric, 0 non-integer cells; 0 duplicate (location, date, hour) keys. **Missing data = absent location-hours** (e.g. Dhule 16-06-2018 has hours 0 and 17, nothing in between) |
| G1b | Outage encoding | profiler + examples | ✅ 4,337,926 zero readings (13.3%). Example: Dhule 16-06-2018 hour 17 is 0 V for minutes 0–37, then 247 V |
| G1j | 350 V ceiling? | `pipeline/inspect_values.py` | ⚠️ **Not a ceiling.** Max 364 V (1 reading, transient at restoration). 285 readings at exactly 350 V, 284 from one monitor (Pachmori) that saturates at 350 for whole hours → sensor cap at that device. D-013 |
| G1k | Low-voltage floor values | same | ⚠️ 101 V ×116,494 (102 monitors), 99 V ×15,694 (25 monitors) inside deep sags, never a whole hour → device floors. Prayas classes them as no supply (≤130 V). D-014 |
| G1l | Location metadata | profiler | ✅ 528 rows, unique names, 177 "[Offline]"; columns as documented; **no coordinates**; categories Gram Panchayat 199 / District Headquarters 159 / State Capital 105 / Other Municipal Area 65; connection Domestic 433 / Non Domestic 83 / Agriculture 12. UP: 179 locations, 17 districts. D-016 |
| G1m | Time zone | About the initiative.pdf | ⚠️ Not stated ("Hour of the day (0 to 23)"). Treated as local IST (D-015) |
| G1n | Dataset citation | Dataverse citation API | ✅ "Prayas, Energy Group, 2019, "Minute-wise voltage data collected in Electricity Supply Monitoring Initiative", https://doi.org/10.7910/DVN/CLLZZM, Harvard Dataverse, V2, UNF:6:CQzM5yPH9GilZHSqyRRyEQ== [fileUNF]" |

### G2 load and first query (2026-10-11, measured)

| # | Claim / measurement | How | Result |
|---|---|---|---|
| G2a | Native IMPORT of the raw sample | `pipeline/load_raw.py` (pyexasol `import_from_callback`, i.e. Exasol `IMPORT … FROM CSV` over the HTTP transport; lines streamed unchanged, prefixed with file id + physical line number) | ✅ 542,518 rows in **1.23 s** (~440,000 rows/s, ~114 MB/s); loaded = counted lines (hard check). Location file 528 rows in 0.20 s |
| G2b | In-database unpivot | `sql/030_unpivot.sql` via `pipeline/run_sql.py` | ✅ 32,551,080 minute rows (= 542,518 × 60) in **4.77 s**; typed `MINUTE_READING` in 3.92 s; 0 row-level and 0 value-level quarantines (consistent with the G1 profile) |
| G2c | **First real gaps-and-islands query** (LAG + running SUM) | `pipeline/g2_first_query.py "80 feet road- Dhule" 2018-06-16` | ✅ Islands: NORMAL 00:00–00:59 (60) · gap · **OUTAGE 17:00–17:36 (37 min)** · NORMAL 17:37–23:59 (383). An independent plain-Python check on the raw CSV gives **identical** islands. Raw line confirms 37 zero minutes, first non-zero at minute 37 |
| G2d | Storage | `EXA_ALL_OBJECT_SIZES` | MINUTE_READING 305.0 MiB stored (776.1 MiB raw), 9.82 bytes/row; RAW_HOURLY 52.7 MiB stored |
| X22 (update) | Windows→WSL bind-mount write path | volume file timestamps + run without errors | ✅ No I/O errors or visible slowness at this scale (persistent volume `storage\vol_1000.dat` written at 15:08:33 during the load) |
| X31 | Persistent volume sizing | file listing of `<deployment>\local\runtime\exa\storage` | ⚠️ `vol_1000.dat` is a **preallocated 1,024 MB** file (plus `vol_1001.dat` 1,024 MB). Current data is 358 MiB stored. **What happens when data exceeds it is untested.** Test before the full UP load |

### Full Uttar Pradesh load (2026-10-11 evening; files downloaded by the user, all 12 MD5-verified)

| # | Finding | How | Result |
|---|---|---|---|
| U1 | 2019 date format | `pipeline/profile_2019.py` | ⚠️ `M/D/YYYY` (2nd part up to 31) in both 2019 files; 72 `#VALUE!` dates in Jan–June → D-025 |
| U2 | 2019 July–Dec Hour column | same + row inspection | ❌ 690,915 of 695,974 rows have Hour = 0; 24 rows per location-day all labelled 0 → excluded (D-026) |
| U3 | Name variants in 2019 | `ROW_QUARANTINE` / `NAME_MATCH` | ⚠️ 187 names with an added "[Offline]" or extra spaces; 169 match uniquely after normalisation, 19 match nothing → D-029 |
| U4 | Full build size | `scripts\load.ps1 -Set up` | 7,367,053 raw rows in 10 analysed files; **102,845,781 clean UP minutes**, 176 locations, 408,223 outage events, 83,929 location-days, 2,870 location-months (1,876 comparable), 184,299 coincident pairs, 64,526 potential shared supply events |
| U5 | Full build time | RUN_LOG | 160 s SQL / 194 s wall after D-028 (first attempt > 60 min, see D-028) |
| U6 | Provenance at full scale | `pipeline/check_provenance.py` | ✅ 199/199 statements match `EXA_DBA_AUDIT_SQL` by exact text |
| U7 | Host memory during the load | `free -m` in the VM, Windows free RAM | VM 8.5 of 11 GB used, no swap; Windows free RAM fell to 0.8 GB (tight, as predicted in step 2) |

### Legal sources for the report's grievance-route text (2026-10-11)

"Read" means the text was extracted and read, not only downloaded. Local copies and verbatim excerpts are in the
gitignored evidence folder (third-party documents are not redistributed).

| # | Claim | Source | Result |
|---|---|---|---|
| L1 | A Consumer Grievance Redressal Forum is constituted by each distribution licensee under s.42(5); an Electricity Ombudsman is appointed or designated by the Commission under s.42(6) | UPERC (Consumer Grievance Redressal Forum & Electricity Ombudsman) Regulations, 2003, No. U.P.E.R.C.-A.O.-Printing/03-2917, 9 Dec 2003, clauses 2.1(l), 2.1(n); copy hosted at https://dvvnl.org/UploadFiles/regulation/Consumer-20Grivevance-20Redressal-20Forum20and20Electricity20Ombudsman20-209th20Dec202003.pdf | ✅ read. Preamble: made "by Section 181 read with sub-sections (5) to (8) of Section 42". 2.1(i) lists "Interruption/ failure of Power Supply, Voltage complaints" as deficiencies. Not claimed to be the regulation in force today |
| L2 | A consumer whose grievance is not redressed may make a representation to the Ombudsman | Press Information Bureau, Ministry of Power, "Ombudsman under Electricity Act", 30 Dec 2010, https://pib.gov.in/newsite/PrintRelease.aspx?relid=68781 | ✅ read ("Any consumer, who is aggrieved by non-redressal of his grievances, may make a representation …") |
| L3 | Section 42 text in the Act itself | https://www.indiacode.nic.in/bitstream/123456789/2058/1/A2003-36.pdf | ⏳ **not read**: 403 (WebFetch), then 504 Gateway Time-out ×4 on 2026-10-11. The report's wording follows L1 and L2 only |
| L4 | Electricity (Rights of Consumers) Rules, 2020 exist and cover reliability of supply, standards of performance, a compensation mechanism and grievance redressal | PIB, Ministry of Power, 21 Dec 2020, https://www.pib.gov.in/PressReleasePage.aspx?PRID=1682384 ; pre-publication text hosted by PIB, https://static.pib.gov.in/WriteReadData/userfiles/final%20-%20Copy%202.pdf | ✅ read (rules 1–4 of the text; G.S.R. number and date are blank in that copy) |
| L5 | 2023 amendment of those Rules (Time of Day tariff, smart metering) | PIB, Ministry of Power, 23 Jun 2023, https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=1934673 | ✅ read |
| L6 | Gazette G.S.R. number and publication date of the 2020 Rules; complete list of amendments | Ministry of Power PDFs (all 404 on 2026-10-11): `…/uploads/Consumers_Rules_2020.pdf`, `…/uploads/15_f_Electricity_Second_Amendment_Rules_2023.pdf`, `…/Electricity_Rights_of_Consumers_Amendment_Rules_2024_0.pdf` | ⏳ not verified; not cited anywhere until verified |
| L7 | Timing | L4 | ✅ the Rules date from December 2020, after the ESMI data (2014–2019); they did not apply to the period analysed |

### Not yet verified (carried forward)

- ⏳ Electricity (Rights of Consumers) Rules, 2020: gazette number/date and amendment list (L6); Electricity Act text (L3).
- ⏳ UPERC standards-of-performance regulations in force 2016–2019 (only if Section 8.6 is attempted).
- ⏳ watchyourpower.org access route and terms.
- ⏳ pyexasol compatibility with the installed DB version (G2).
- ⏳ Raw sample: actual encodings of blanks/NA, timestamp format, timezone (G1, needs the data download).
