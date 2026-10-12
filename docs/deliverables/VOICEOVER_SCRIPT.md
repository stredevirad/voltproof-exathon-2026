# Voice-over script (demo video, under 2:50 of speech)

Generated from `docs/deliverables/video_timeline.json` by `python -m pipeline.video script`; do not edit by hand.

**How to record (one take, on a phone):**
- **Pace:** read each block at a calm pace. The times show when each screen appears in the video.
- **Pauses:** pause for **about 2 seconds** wherever it says *(pause)*. The pauses are where the recording is
  cut into its 7 pieces, so there must be exactly 6 of them and no other long silence.
- **Running long:** if a block runs long, keep going. The video is re-timed to your reading; the audio is
  never sped up.
- **Where to save:** any common format (m4a, mp3, wav, aac, ogg), named `voiceover.<ext>` (for example
  `voiceover.m4a`), in the team's private voice-over folder (gitignored; the path is in the team's notes).

Speech: 339 words. At about 140 words a minute that is 2:25; the limit is 2:50.

## 0:01 — Start page, with the caption 'Illustrative example'

Imagine a shopkeeper in a small town in Uttar Pradesh. The power fails every day. When she complains, her memory is all she has against the utility's records. Prayas, an independent research group, recorded the supply minute by minute at homes and shops like hers. VoltProof turns those readings into evidence anyone can check.

*(On screen: "Illustrative example")*

*(pause)*

## 0:27 — Start guided demo: the month view with its banner, KPI tiles and calendar

The guided demo opens one real monitor, chosen by a fixed rule rather than by hand: Huzurpur, in Bahraich district, in July 2018. That month it recorded 320 interruptions and at least 366 hours without usable supply. That figure is a lower bound: a minute without a reading is never counted as an outage.

*(pause)*

## 0:53 — The demo day: the minute-by-minute voltage trace

This is the twenty-fifth of July, minute by minute. The grey line is the measured voltage. Orange blocks are outages, and hatching means there was no reading. At 6:27 in the evening, the supply drops to zero.

*(pause)*

## 1:11 — The outage's evidence page: times, certainty, source lines and statement ids, and the panel of other monitors

The evidence page gives the outage's exact start and end, how certain each edge is, and the two lines of the source file it comes from, with the database statements that computed it. Sixteen other monitors in the district lost supply within two minutes. This month, coincidences like this happened about twice as often as a time-shifted baseline predicts. VoltProof calls this a potential shared supply event: it is not proof of a common cause.

*(pause)*

## 1:44 — Back to the month: Generate evidence report, the report links

One click makes an evidence report: the calendar, every outage with its bounds, data quality and the grievance route, plus file checksums and statement ids for anyone who wants to check. It is not legal advice and states no amount owed.

*(pause)*

## 2:02 — Data and sources: the two 2019 files

Defects in the published data are shown, not hidden. The July to December 2019 file lost its hour column, so it is excluded. The January to June 2019 file leaves out most zero-volt hours, so its outage figures are lower bounds.

*(pause)*

## 2:23 — Start page

All of this runs as versioned SQL inside Exasol: about 103 million minutes of Uttar Pradesh data, rebuilt from the raw files in about three and a half minutes on this laptop. VoltProof. Data: Prayas Energy Group.
