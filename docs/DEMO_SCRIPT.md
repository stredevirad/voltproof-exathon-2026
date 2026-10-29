# Demo script (video ≤ 3:00, and the live demo on demo day, Fri 6 Nov 2026, 10:00 am IST, virtual)

**The committed video was made outside this repository's video pipeline, and its narration differs from this
script.** `docs/deliverables/VoltProof_demo.mp4` (2:51, subtitles burned in) is an animated intro of about 1:00
(synthetic Piper TTS narration, original synthesized music; the shopkeeper is captioned "Illustrative"), then the
team's live walkthrough of the app on the real Prayas data, in a teammate's own voice. Its full text is
`docs/deliverables/VoltProof_demo.srt`; README "About the video" states precisely what the walkthrough says loosely.
It is not a `pipeline.video merge` output: the tooling below is how the earlier drafts were made.

**The draft videos** were made from one timeline file, `docs/deliverables/video_timeline.json`. For each
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
`docs/deliverables/VoltProof_demo.mp4` (now the team's video described above).

**Live demo:** see docs/deliverables/LIVE_DEMO_RUNBOOK.md.

The timeline's holds are estimates from the word count until `tts --update-holds` has measured the narration;
run it before recording.

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
This script and the committed video use the real data.

## Script

The narration lives only in `docs/deliverables/video_timeline.json` (eight screens: start page with the
"Illustrative example" caption, the guided month with its lead tile, the demo day, the outage's evidence page,
the evidence report, the upload page, the 2019 files on Data & sources, and the start page again) and is read
aloud from `docs/deliverables/VOICEOVER_SCRIPT.md`: 343 words, about 2:27 of speech. An earlier hand-written
table here was replaced by the timeline so that there is one source.

Numbers checked against the build on 2026-10-12 (and again on 2026-10-16 for the new screens). Huzurpur-Bahraich, 2018-07: 320 interruptions; outage at
least 21,970 minutes (366.2 h), up to 22,030 minutes (367.2 h); 90.7% of minutes read (comparable). The
scale and build time come from docs/HEADLINE_FIGURES.md and docs/BENCHMARKS.md. The narration rounds them: 366 and
367 hours; about 103 million minutes (102,845,781 clean minute readings); about three and a half minutes (the
210.4 s full build). At 18:27 on 25 July the recorded voltage is 0 V (all 67 minutes of that cut read exactly 0 V). Never quote a number that
is not on screen or in those files. The shopkeeper is an illustrative example, not a real person in the
data; the committed video captions her as "Illustrative".

## Live demo (Stage 2, 15 minutes + 5 minutes questions, over a video call) and backup

1. Before the call: database started, `scripts\start.ps1` running, browser open on the start page, a
   pre-generated report PDF open in a second tab.
2. Walk the same flow as the video (about 6 minutes, including a pre-built upload), then spend time on Q&A
   material (docs/JUDGE_QA.md).
3. **Backup if the database misbehaves:** the committed video, plus the screenshots in
   `docs/deliverables/screenshots/` and the pre-generated PDF.
