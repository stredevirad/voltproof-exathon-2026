# VoltProof for judges: a 3-minute brief

▶ [Watch the demo video in the browser (2:51)](https://stredevirad.github.io/voltproof-exathon-2026/) · [download the MP4](docs/deliverables/VoltProof_demo.mp4?raw=true) · [subtitles (SRT)](docs/deliverables/VoltProof_demo.srt)

VoltProof turns public minute-by-minute voltage records into a dated, checkable record of every power cut, with its
uncertainty stated, analysed in SQL inside Exasol Personal. The video is an animated intro, then a live walkthrough
of the app on the real data ([About the video](README.md#about-the-video)); then the
[pitch deck (PDF)](docs/deliverables/VoltProof_deck.pdf).

**Real public data, not synthetic: about 103 million readings** (102,845,781 clean minutes from 176 monitors in Uttar
Pradesh), from Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI). Synthetic data appears only in
the test fixtures and the no-download demo set, always labelled.

## Stage 1

### Innovation and problem impact (25%)
When households and small shops complain, their own memory is usually all they have to set against the utility's
records. VoltProof gives each cut an exact start and end, the certainty of each edge, and lower and upper durations.
The headline is the lower bound; a missing reading is never an outage.

Evidence: [problem statement](docs/deliverables/PROBLEM_STATEMENT.md), [Why this matters](README.md#for-judges-start-here)

### Effective use of Exasol Personal (25%)
Full table with files and evidence: [How VoltProof uses Exasol](README.md#how-voltproof-uses-exasol). In short:
- native `IMPORT` of the raw files; in-database unpivot to about 103 million minute readings
- one `ROW_NUMBER` window for gaps-and-islands: 665 s before the rewrite, 35.6 s after
- `CONNECT BY` row generators; a band join rewritten as bucketed equality joins for coincidence
- every recorded statement matched against Exasol's audit log `EXA_DBA_AUDIT_SQL`; each statement's duration and
  memory peak, measured by Exasol, shown in the app and the PDF
- a schema per upload, under a restricted database user
- CI on Exasol's own `exasol/nano` image ([ci.yml](.github/workflows/ci.yml))
- Ask VoltProof: a read-only user `VP_READER` that sees only seven commented views, queried through Exasol's
  open-source MCP server ([ASK_VOLTPROOF](docs/ASK_VOLTPROOF.md))

Evidence: [WHY_EXASOL](docs/WHY_EXASOL.md), [BENCHMARKS](docs/BENCHMARKS.md), [sql/](sql/)

### Technical excellence (20%)
The SQL must equal an independent Python oracle exactly: 18 hand-written fixtures, 40 random Hypothesis batches and
real Uttar Pradesh slices. The latest full run (29 Oct): 224 of 224 tests passed; every push also runs the fixtures,
the synthetic set and the read-only-user tests on `exasol/nano` in CI.

Evidence: [TEST_REPORT](docs/TEST_REPORT.md), [VALIDATION](docs/VALIDATION.md), [tests/](tests/)

### Solution design and UX (15%)
A guided demo walks one real case: calendar, minute trace, event evidence, PDF report. A plain-words guide, a
skippable tour, WCAG AA text contrast, and upload of your own readings (labelled "not verified").

Evidence: [screenshots](docs/deliverables/screenshots/), [Use your own data](README.md#use-your-own-data)

### Documentation and reproducibility (10%)
The quick start needs no data download; on 12 Oct a fresh clone reached a working app in 5 min 28 s. Every number
traces to its source line, SQL step and Exasol statement id.

Evidence: [Quick start](README.md#quick-start-windows-1011-amd64-no-data-download), [clean-start test](docs/VALIDATION.md#4-clean-start-test-g6-a-fresh-clone-following-only-the-readme)

### Open-source quality (5%)
MIT licence, third-party notices, a contributing guide, CI on every push (lint and unit tests on Windows, the database
tests on `exasol/nano`). The data is credited to Prayas everywhere and never committed.

Evidence: [LICENSE](LICENSE), [CONTRIBUTING](CONTRIBUTING.md), [data terms](docs/data/SOURCE_TERMS.md)

## Stage 2 (top 5 only)

### Live demo (40%)
Real data: Huzurpur-Bahraich, July 2018, at least 366.2 h of outage in the month (up to 367.2 h). At 18:27 on
25 July, 16 other monitors lost supply within 2 minutes.

Evidence: [runbook](docs/deliverables/LIVE_DEMO_RUNBOOK.md), [BENCHMARKS](docs/BENCHMARKS.md)

### Depth under Q&A (30%)
29 hard questions, each answered with a file, test or measurement. Start with why our daily averages are 2.0 to 2.6
times Prayas's Figure 2 (reported, not tuned away) and whether coincidence is chance.

Evidence: [JUDGE_QA](docs/JUDGE_QA.md), [VALIDATION](docs/VALIDATION.md)

### Real-world applicability (20%)
It serves people working with ESMI records or readings in the ESMI layout. For a household without a monitor it is a
method, not a service. Next, not claimed today: new monitors or smart-meter data through the same SQL, and each
state's standards of performance.

Evidence: [JUDGE_QA](docs/JUDGE_QA.md), [Use your own data](README.md#use-your-own-data)

### Communication (10%)
A one-sentence problem statement, a demo video (an animated intro, then a live walkthrough narrated by the team), and
a plain-words deck that shows every data defect and the gap to Prayas's figures.

Evidence: [About the video](README.md#about-the-video)

## What we do not claim
- No cause and no equipment is named; coincidence is not cause.
- No amount owed and no breach is stated; this is not legal advice.
- Durations next to gaps are bounds; the headline is the lower one.
- A plug-in monitor is not the utility's meter.
- The data is historical (ESMI, 2014–2019), not today's supply.
- Groups are districts, not map areas: the source has no coordinates.
- Uploads are not verified by VoltProof; the uploader needs the right to use them.
- No speed comparison with other engines.
- No language model in the app or the reports; an AI client's answers through Ask VoltProof are its own sentences.
