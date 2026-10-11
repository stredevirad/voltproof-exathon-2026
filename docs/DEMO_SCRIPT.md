# Demo script (video ≤ 3:00, and the live demo on Demo Day)

**Setup before recording:** `scripts\exa.ps1 status` shows `database_ready`; `scripts\start.ps1`; browser
at http://127.0.0.1:8000/, window about 1366 × 860; Docker Desktop closed. A silent screen recording of
this exact flow can be produced automatically:
`$env:VOLTPROOF_RECORD_VIDEO='1'; scripts\test.ps1 -Suite e2e` (writes a .webm to
`docs\deliverables\video\`). Record the voice-over on top of it.

## How the guided-demo example is chosen (say this, it pre-empts "cherry-picked?")

Rule (`app/api/service.py`, `DEMO_RULE`):
1. Within June–August 2018 (the file in the smallest download set), take the evening (17:00–22:59)
   potential shared supply event with the **most distinct monitors** (ties: earliest).
2. Within it, take the earliest member whose location-month is **comparable** (> 90% of minutes read;
   ties: lowest location id).

It is one example selected by a rule, not a typical month. The UI says so in a banner.

## Script

| Time | Screen | Narration (plain English) |
|---|---|---|
| 0:00–0:20 | Start page | "A shopkeeper in a small Uttar Pradesh town can't get a fix for daily power cuts, because her memory is the only record, against the utility's own reports. Prayas, which runs independent voltage monitors, reports more than four hours of outage a day in rural Uttar Pradesh. VoltProof turns those minute-by-minute voltage records into traceable evidence." |
| 0:20–0:35 | Click **Start guided demo**; banner | "The demo opens one real monitor and month, chosen by a fixed rule shown here, not hand-picked." |
| 0:35–1:05 | Month dashboard: KPI tiles, calendar, quality badge | "This month the monitor recorded N interruptions and at least H hours without usable supply. The headline is a lower bound: hatched days had too few readings, and missing readings are never counted as outage. The range shows what the gaps *could* add." |
| 1:05–1:35 | Click the demo day; voltage trace | "Minute by minute: the grey line is measured voltage. Orange blocks are outages; hatched grey means no reading, not counted. On 25 July at 18:27 the supply drops to zero." |
| 1:35–2:10 | Open the event; certainty; **How was this computed?**; coincidence panel | "Exact start and end, and how certain they are. Every number traces to the source file line and to the SQL statement Exasol ran; its audit log shows the same SQL. Sixteen other monitors in Bahraich lost supply within two minutes. That is a *potential* shared supply event: against a chance baseline it is far more common than shifted timings would give, but VoltProof does not claim a cause." |
| 2:10–2:35 | Back to month, **Generate evidence report**, open PDF, scroll to appendix | "One click gives a PDF a consumer can take to the distribution company's grievance forum. It has the calendar, every event with bounds, data quality, methodology and a reproducibility appendix with file checksums and statement ids. It is not legal advice and claims no entitlement." |
| 2:35–2:55 | Data & sources page (2019 file excluded), then a terminal running `scripts\load.ps1` (or BENCHMARKS table) | "The whole analysis runs as versioned SQL inside Exasol Personal on this laptop: about X million minutes of Uttar Pradesh data, loaded with native IMPORT and segmented with window functions in Y seconds. We even caught defects in the published data, like a file that lost its hour column, and excluded it with the reason shown." |
| 2:55–3:00 | Start page with footer | "VoltProof: traceable evidence of power cuts. Data: Prayas Energy Group, ESMI." |

Numbers N, H, X, Y are read from the app and from docs/BENCHMARKS.md at recording time. Never quote a
number that is not on screen or in those files.

## Live demo (Stage 2, 15 minutes) and backup

1. Before the call: database started, `scripts\start.ps1` running, browser open on the start page, a
   pre-generated report PDF open in a second tab.
2. Walk the same flow as above (5 minutes), then spend time on Q&A material (docs/JUDGE_QA.md).
3. **Backup if the database misbehaves:** the recorded video, plus the screenshots in
   `docs/deliverables/screenshots/` and the pre-generated PDF.
