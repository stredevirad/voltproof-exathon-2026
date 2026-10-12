# Demo script (video ≤ 3:00, and the live demo on Demo Day)

**The submission video** is made from one timeline file, `docs/deliverables/video_timeline.json`. For each
screen it holds the narration and how long the screen stays up. The narration to read aloud is
`docs/deliverables/VOICEOVER_SCRIPT.md` (generated from the timeline).

```powershell
scripts\get-ffmpeg.ps1                                   # once: pinned, SHA-256-verified ffmpeg in .tools\ (video only)
.venv\Scripts\python.exe -m pipeline.video tts --update-holds   # draft narration; raises holds that are too short
.venv\Scripts\python.exe -m pipeline.video record        # warm-up, then the paced silent recording (1366 x 860)
.venv\Scripts\python.exe -m pipeline.video merge --audio tts    # DRAFT with the built-in Windows voice
.venv\Scripts\python.exe -m pipeline.video merge --audio voice  # the team's one-take recording, split at its pauses
```

Each narration piece starts at its screen's actual start in the recording. If a piece is longer than its
screen, the tool says which hold to raise. Then re-record; the audio is never sped up. The silent take and
the drafts stay in the gitignored `reports\video-run\`. Only the final narrated MP4 is committed, as
`docs/deliverables/VoltProof_demo.mp4`, once the team confirms it.

**Live demo:** see docs/deliverables/LIVE_DEMO_RUNBOOK.md. The table below is the original 3-minute plan
that the timeline implements.

## How the guided-demo example is chosen (say this, it pre-empts "cherry-picked?")

Rule (`app/api/service.py`, `DEMO_RULE`):
1. Within June–August 2018 (the file in the smallest download set), take the evening (17:00–22:59)
   potential shared supply event with the **most distinct monitors** (ties: earliest).
2. Within it, take the earliest member whose location-month is **comparable** (> 90% of minutes read;
   ties: lowest location id).

It is one example selected by a rule, not a typical month. The UI says so in a banner.

On the SYNTHETIC demo set (`scripts\load.ps1 -Set demo`, no download), the same rule runs over January 2030.
It lands on the shared interruption the generator was designed to contain: Synthpur (SYNTHETIC),
17 January 2030 at 18:42, nine invented monitors. Every page then carries the SYNTHETIC DEMO DATA banner.
This script and the recorded video use the real data.

## Script

| Time | Screen | Narration (plain English) |
|---|---|---|
| 0:00–0:20 | Start page; caption **"Illustrative example"** while the shopkeeper is mentioned | "Imagine a shopkeeper in a small Uttar Pradesh town who can't get a fix for daily power cuts, because her memory is the only record, against the utility's own reports. Prayas, which ran independent voltage monitors, reports more than four hours of outage a day in rural Uttar Pradesh. VoltProof turns those minute-by-minute voltage records into traceable evidence." |
| 0:20–0:35 | Click **Start guided demo**; banner | "The demo opens one real monitor and month, chosen by a fixed rule shown here, not hand-picked." |
| 0:35–1:05 | Month dashboard: KPI tiles, calendar, quality badge | "In July 2018 this monitor in Bahraich recorded 320 interruptions and at least 366 hours without usable supply. That headline is a lower bound: missing readings are never counted as outage, and hatched days had too few readings. The range shows what the gaps *could* add: here, about one more hour." |
| 1:05–1:35 | Click the demo day; voltage trace | "Minute by minute: the grey line is measured voltage. Orange blocks are outages; hatched grey means no reading, not counted. On 25 July at 18:27 the supply drops to zero." |
| 1:35–2:10 | Open the event; certainty; **How was this computed?**; coincidence panel | "Exact start and end, and how certain they are. Every number traces to the source file line and to the SQL statement Exasol ran; its audit log shows the same SQL. Sixteen other monitors in Bahraich lost supply within two minutes. That is a *potential* shared supply event: against a chance baseline it is far more common than shifted timings would give, but VoltProof does not claim a cause." |
| 2:10–2:35 | Back to month, **Generate evidence report**, open PDF, scroll to appendix | "One click gives a PDF a consumer can take to the distribution company's grievance forum. It has the calendar, every event with bounds, data quality, methodology and a reproducibility appendix with file checksums and statement ids. It is not legal advice and claims no entitlement." |
| 2:35–2:55 | Data & sources page (2019 files: one excluded, one marked lower bound), then the BENCHMARKS table | "The whole analysis runs as versioned SQL inside Exasol Personal on this laptop: about 103 million minutes of Uttar Pradesh data, loaded with native IMPORT in about 30 seconds, and every outage found with one window function in about 36 seconds; the full build takes about three and a half minutes. We even caught defects in the published data, like a file that lost its hour column, and one that leaves out most zero-volt hours, and we show both instead of hiding them." |
| 2:55–3:00 | Start page with footer | "VoltProof: traceable evidence of power cuts. Data: Prayas Energy Group, ESMI." |

Numbers checked against the build on 2026-10-12. Huzurpur-Bahraich, 2018-07: 320 interruptions; outage at
least 21,970 minutes (366.2 h), up to 22,030 minutes (367.2 h); 90.7% of minutes read (comparable). The
scale and build time come from docs/HEADLINE_FIGURES.md and docs/BENCHMARKS.md. Never quote a number that
is not on screen or in those files. The shopkeeper is an illustrative example, not a real person in the
data; the video must caption her as "Illustrative example".

## Live demo (Stage 2, 15 minutes) and backup

1. Before the call: database started, `scripts\start.ps1` running, browser open on the start page, a
   pre-generated report PDF open in a second tab.
2. Walk the same flow as above (5 minutes), then spend time on Q&A material (docs/JUDGE_QA.md).
3. **Backup if the database misbehaves:** the recorded video, plus the screenshots in
   `docs/deliverables/screenshots/` and the pre-generated PDF.
