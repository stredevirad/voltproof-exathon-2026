# Voice-over script (demo video, under 2:50 of speech)

Generated from `docs/deliverables/video_timeline.json` by `python -m pipeline.video script`; do not edit by hand.

**How to record (one take, on a phone):**
- **Pace:** read each block at a calm pace. The times show when each screen appears in the video.
- **Pauses:** pause for **about 2 seconds** wherever it says *(pause)*. The pauses are where the recording is
  cut into its 8 pieces, so there must be exactly 7 of them and no other long silence.
- **Running long:** if a block runs long, keep going. The video is re-timed to your reading; the audio is
  never sped up.
- **Where to save:** any common format (m4a, mp3, wav, aac, ogg), named `voiceover.<ext>` (for example
  `voiceover.m4a`), in the team's private voice-over folder (gitignored; the path is in the team's notes).

Speech: 343 words. At about 140 words a minute that is 2:27; the limit is 2:50.

## 0:01 — Start page (the new look), with the caption 'Illustrative example'

Imagine a shopkeeper in a small town in Uttar Pradesh. The power fails every evening, and when she complains, her memory is all she has. Prayas, an independent research group, recorded the voltage every minute at homes and shops. VoltProof turns those readings into evidence anyone can check.

*(On screen: "Illustrative example")*

*(pause)*

## 0:27 — Start guided demo: the month view, lead tile 'Outage time (at least)' with its plain caption, then the calendar

The guided demo opens one real monitor, chosen by a fixed rule, not by hand: Huzurpur, in Bahraich, July 2018. The first number is the one that matters: at least 366 hours without supply that month. It is a minimum: a minute without a reading is never counted, and even if every unread minute next to a cut were a cut, it would be 367.

*(pause)*

## 0:53 — The demo day: the minute-by-minute voltage trace

This is the twenty-fifth of July, minute by minute. The grey line is the measured voltage. Orange blocks are outages, and hatching means there was no reading. At 6:27 in the evening, the voltage drops to zero.

*(pause)*

## 1:11 — The outage's evidence page: times, certainty, source lines and statement ids, and the panel of other monitors

The evidence page gives the exact start and end, how certain each one is, and the lines of the source file, with the database statements that computed them. Sixteen other monitors in the district lost supply within two minutes. VoltProof calls this a potential shared supply event. Coincidence is not cause, and no cause or equipment is named.

*(pause)*

## 1:44 — Back to the month: Generate evidence report, the report links

One click makes an evidence report: every outage with its bounds, data quality, checksums and statement ids. It ends with where a consumer can seek redress. It is not legal advice and states no amount owed.

*(pause)*

## 0:00 — Upload your data: the page that says the file stays on this computer

Anyone can also upload readings from their own monitor. The file stays on this computer and is analysed by the same steps, in its own space.

*(pause)*

## 2:02 — Data and sources: the two 2019 files

Defects in the published data are shown, not hidden. One 2019 file lost its hour column, so it is excluded; another leaves out most zero-volt hours, so its figures are lower bounds.

*(pause)*

## 2:23 — Start page

All of this runs as versioned SQL inside Exasol: about 103 million minutes of Uttar Pradesh data, rebuilt from the raw files in about three and a half minutes on this laptop. VoltProof. Data: Prayas Energy Group, Electricity Supply Monitoring Initiative.
