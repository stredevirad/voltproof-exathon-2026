# Judge Q&A: hard questions, evidence-based answers

Each answer points to a file, test or measurement in this repository. Nothing is claimed that has not been run.

## Problem and impact

**1. Who actually has this problem?**
Households and small shops in places with poor supply. For Uttar Pradesh in 2016–19, Prayas reports about
21 min/day of outage in megacities, about 90 min/day in other municipal areas and more than 4 h/day in
rural areas (Prayas, "ESMI in Uttar Pradesh", 7 Aug 2019; docs/VERIFICATION_LOG.md P7). VoltProof's own
measurement of the same monitors, 2016–2018, is higher: 56, 190 and 566 min/day (docs/HEADLINE_FIGURES.md;
the difference is discussed in docs/VALIDATION.md §3). Today the consumer's memory is their only record,
set against the utility's own reports.

**2. Can a consumer actually use this?**
The output is a dated evidence report (PDF) per location-month. It lists every interruption with exact
timestamps, certainty and duration bounds, and other monitors that lost supply at the same time, with
an appendix tracing each number to the source file line and the SQL that produced it
(app/api/report.py; tests/integration/test_report.py). It points to the statutory grievance route
(the Consumer Grievance Redressal Forum and the Electricity Ombudsman under UPERC's 2003 regulations;
VERIFICATION_LOG L1–L2) without
claiming any entitlement. Using it today
needs a monitor like ESMI's; see "future scope" in the README.

**3. Most consumers don't have a monitor. Who can use this today?**
Not most households, and we do not claim otherwise. VoltProof analyses minute-wise records that already
exist; it does not create new ones. Today it is useful to:
- researchers, consumer groups and journalists working with the ESMI records (528 monitors, 2014–2019; 179
  in Uttar Pradesh). They get event-level evidence and a report per location-month instead of raw minute
  files;
- people who lived or worked near one of those monitors, for the historical months it covered;
- anyone with minute-wise voltage readings in the ESMI file layout (`Location name, Date, Hour, Min 0..59`).
  A different layout needs its own load and unpivot step (sql/010–030). The cleaning, event, aggregate and
  coincidence SQL after it stays the same.

For an ordinary household without a monitor, VoltProof is a method today, not a service. Running it on other
minute-wise sources, such as smart-meter data, is future scope (see #4), not a claim.

**4. Is this data current?**
No. ESMI data covers Nov 2014 – Dec 2019. Our Uttar Pradesh analysis covers January 2016 to June 2019, and
headline figures use 2016–2018 because the 2019 file has a known defect (D-031; docs/data/SOURCE_TERMS.md). We present it as a historical case study that demonstrates a method. The
same pipeline would run on smart-meter or new monitor data; that is future scope, not a claim.

**5. Isn't this what Prayas already publishes?**
Prayas publishes summaries and dashboards. VoltProof adds event-level evidence with explicit uncertainty
(exact / bounded / censored edges; lower and upper bounds). It also adds coincidence analysis with a
chance baseline, quarantine and provenance down to the source line and the Exasol statement id, and a
reproducible report per location-month. We also compare our numbers with Prayas's published UP figures
(docs/VALIDATION.md §3):
- Prayas's single-monitor supply profiles for 2017–2018 agree with ours to within 0.2 h/day.
- Its time-of-day and evening outage figures agree.
- Our daily-outage averages are higher than Prayas's Figure 2. Prayas's Figure 2 and its Figures 8–9 imply
  different averages, and the article does not state the averaging used for Figure 2 (docs/VALIDATION.md §3).
  We report the difference; no parameter was tuned to close it.

## Method and honesty

**6. How do you know a missing reading isn't a power cut?**
We don't, so we never count it as one. Prayas: "Missing data should be interpreted as unavailable data and
not as interruption." Missing minutes become NO_DATA (METHODOLOGY R-6). An outage next to a gap is
reported with a measured lower bound (headline) and an upper bound that may claim at most 60 minutes per
side (R-10, R-15). Fixtures F05, F06 and F09 test exactly this.

**7. "A home monitor isn't the utility's meter."**
Correct, and every report says so (report limitations). Two mitigations: (a) corroboration, because
interruptions that start within 2 minutes at other monitors in the district are shown as potential shared
supply events (17 Bahraich monitors at 18:27–18:29 on 25 July 2018; docs/VALIDATION.md §2); (b) the
0 V share is reported separately from 1–130 V readings (D-014).

**8. Isn't coincidence just chance?**
Sometimes, and we measure it. Each district-month is compared with a baseline where every monitor's
interruptions are shifted by whole days (keeping its time-of-day pattern; R-21). In large rural
districts we observed about 1.4–3.1 times more coincident pairs than the shifted baseline, with none of
20 shifts reaching the observed count (Bahraich, July 2018: 3,945 pairs observed, 1,827.5 expected). Over
the 276 district-months of 2016–2018 with at least two monitors: 91,532 observed against 40,704.6 expected.
150 are above all 20 shifts. If the coincidences were pure chance, at most about 1 in 21 district-months
would beat all 20 shifted versions (ties count against us): about 13 of 276. Many others sit at chance
(docs/HEADLINE_FIGURES.md, docs/VALIDATION.md §2). The baseline uses only comparable months, to avoid an anti-conservative bias (D-023). Its known
conservative bias in 30-day months is disclosed.

**9. Why ≤ 130 V as "no supply"? Isn't that arbitrary?**
It is Prayas's published definition ("Voltage below 131 (i.e. 130 and less) is considered as no supply"),
used so our numbers are comparable with theirs (config/method.yaml cites the source and retrieval date).
We also report the 0 V minutes separately, because some monitors report floor values of about 101 V
during deep sags (D-014).

**10. You found data errors. How do you know your pipeline isn't hiding them?**
Nothing is dropped silently. Malformed rows and values are quarantined with reason codes. Conflicting
duplicates become NO_DATA. Every file's rows, quarantines and analysed minutes are reported
(QUALITY_FILE), and the build fails if a file is mostly quarantined. Examples found in the real data: the
2019 files use M/D/YYYY dates (D-025); 72 `#VALUE!` dates; the published 2019 July–Dec file lost its
Hour column and is excluded with that reason (D-026). The 2019 Jan–June file omits most hours in which
every minute read 0 V. We found this by comparing with Prayas's own charts. The minutes stay NO_DATA, so
2019 outage is a lower bound (docs/VALIDATION.md §3.4, D-031).

**11. How do you know your SQL is correct?**
Three independent checks (docs/VALIDATION.md §1, docs/TEST_REPORT.md):
- 18 hand-written fixtures whose expected values were derived from the rules by hand;
- an independent plain-Python oracle, with exact equality against the SQL on all fixtures, 40 random
  Hypothesis batches and real UP slices;
- harness-sensitivity tests showing that a single wrong value is caught.

**12. Could you have tuned parameters to match Prayas's numbers?**
No parameter was changed to match. Thresholds and the 90% coverage rule are Prayas's published ones,
and the primary definition was fixed before comparing. Where we test alternatives (1 vs 2-minute
interruptions, averaging method, connection type, 0 V only, years), every result is reported. None of
them closes the gap to Prayas's Figure 2, and we say so (docs/VALIDATION.md §3.3).

**13. Does VoltProof work out what a consumer is owed?**
No. VoltProof never states an amount owed or an entitlement. A UI and report test fails on any phrase
that asserts one (the exact list is in tests/support/claims.py). The report only points to
the grievance route. Encoding one state's standards-of-performance rules from the primary regulation is
future scope.

**14. What exactly is "a potential shared supply event"? Does it identify faulty equipment?**
It is a chain of interruptions at different monitors in one district whose starts are at most 2 minutes
apart, with overlapping outage minutes (R-19, R-20). We do not identify any equipment, and phrases naming an
equipment fault are blocked by the claims test.

## Exasol

**15. Why Exasol? Wouldn't Excel or DuckDB do?**
Excel cannot hold this data: about 400 million minute values for 2014–18 alone. DuckDB could run the
queries. What Exasol gives this project, measured (docs/WHY_EXASOL.md, docs/BENCHMARKS.md):
- the whole pipeline as versioned SQL inside the database (native `IMPORT`, unpivot, window-function
  gaps-and-islands, interval band joins), with no Python data engine;
- statement-level provenance, because every report cites Exasol session and statement ids that match
  `EXA_DBA_AUDIT_SQL` by exact SQL text (pipeline/check_provenance.py);
- performance statistics from Exasol's own audit log (`EXA_DBA_AUDIT_SQL`): duration, CPU and temporary
  memory per statement, which is how docs/BENCHMARKS.md is produced;
- one local database that judges can start with one command.

We make no "X times faster than DuckDB" claim: we did not benchmark DuckDB on the same data.

**16. ~600 M rows on a 24 GB laptop?**
Measured instead of estimated: 2014–18 contains 6,601,854 location-hours, which is 396,111,240 minute
values (Dataverse DDI metadata). The build machine has 15.6 GB RAM, not 24, and Exasol gets 8.9 GiB.
For the Uttar Pradesh data (102.8 million clean minutes), the whole build including the native IMPORT
takes 210.4 s warm and 238.6 s cold (medians of 3 runs, docs/BENCHMARKS.md). On this 15.6 GB laptop that needs other memory-heavy
applications closed. With them open, free host RAM fell below our 0.4 GiB guard and two runs were stopped;
both are recorded.

**17. What did you learn about Exasol Personal on Windows?**
Several things, all recorded with evidence (VERIFICATION_LOG X6, X22, X31; D-010, D-021):
- It installs in about 2 minutes.
- The database data lives in the deployment folder (bind-mounted), not on C:.
- The first growth of the data volume over the Windows→WSL path is slow (434 s), then fast (21 s for the
  same write).
- A naive non-equality band join cost 348 s, against 1.8 s with bucketed equality joins.

**18. What would Exasol R&D build next, from your experience?**
- A first-class "gaps-and-islands" or sessionisation operator.
- Native interval/range joins (we emulate them with buckets).
- Pre-growing the data volume on Windows local deployments.
- A documented way to get the statement id of the last executed statement (we use
  `CURRENT_STATEMENT + 1` in non-autocommit mode, verified against the audit log).

## Data and licence

**19. Is the data licensed for this?**
Harvard Dataverse lists the dataset licence as **CC0 1.0**. Prayas's description also asks for
non-commercial, academic and research use with acknowledgement. We follow the stricter reading: we cite
the dataset as the page requires, credit Prayas everywhere and never redistribute the raw data
(docs/data/SOURCE_TERMS.md).

**20. Why is 2019 July–December missing?**
The published file has lost its Hour column: 690,915 of 695,974 rows say hour 0, so minute timestamps
cannot be determined without guessing. It is verified, loaded raw and excluded with that reason (D-026).
Prayas's UP article is dated August 2019, but some of its charts (Figures 6 and 11) run to November 2019,
so the published figures include months we cannot use. VALIDATION §3 lists this among the differences.

**21. Why "Uttar Pradesh"?**
Prayas published UP-specific statistics, which lets us validate against an independent published
result. UP also has the most ESMI monitors (179 of 528).

## Demo and engineering

**22. How did you choose the demo example? Cherry-picked?**
By a committed rule (app/api/service.py `DEMO_RULE`, docs/DEMO_SCRIPT.md):
1. the evening potential shared supply event with the most monitors in June–August 2018;
2. within it, the earliest monitor whose month is comparable.

The UI labels it as one example selected by that rule, not a typical month.

**23. Is the demo data real?**
It depends on which demo:
- **The recorded video and the live demo: real.** They use ESMI measurements: a monitor in Bahraich in
  July 2018, chosen by the rule in #22.
- **The no-download quick start (`scripts\load.ps1 -Set demo`): SYNTHETIC.** It has 20 invented monitors
  in three invented districts in January 2030, written by `pipeline/synthetic.py` with a fixed seed in the
  ESMI file format. It lets a judge run the whole app without a download. The numbers it shows describe no
  real supply.

How the two are kept apart (DECISIONS D-033):
- Every synthetic name contains "SYNTHETIC". Every page and report shows a SYNTHETIC DEMO DATA banner, and
  report ids start with `VP-DEMO`.
- The synthetic set has its own schema, `VOLTPROOF_DEMO`. The build refuses to mix synthetic and real files.
- The tools that compute published figures refuse a synthetic schema.
- tests/e2e/test_demo_dataset_ui.py checks every page of the synthetic app for real-data numbers and place
  names.
- The synthetic set still tests the SQL: its complete output equals the independent oracle
  (tests/integration/test_demo_dataset.py).

**24. Can a judge reproduce this?**
Yes, and we tested it, with no data download. On 2026-10-12 a fresh clone from GitHub followed the README
quick start (docs/VALIDATION.md §4.4):
- clone 36 s, then bootstrap 235 s;
- the database already existed, so the install was skipped;
- the SYNTHETIC demo set was built in 25 s;
- the app served the synthetic guided demo 13 s after start.

That is **5 min 28 s from clone to a working app**. Then every test suite passed in 139 s; the tests that need real files skipped.

Earlier runs on the real minimum data set (§4.1–4.3) found two bugs: the server stopped when its output
was redirected, and an end-to-end test assumed the full data set. Both were fixed, and a repeat cloned from
GitHub passed every step. The real data needs each user's own Dataverse Guestbook entry, by script or
browser (README "Real data"). The full Uttar Pradesh build is optional.

**25. Why are your daily-outage averages 2.0–2.6 times Prayas's Figure 2?**
We do not know, and we report the gap rather than tune it away (docs/VALIDATION.md §3.3). What we checked:
- The pipeline does not appear to inflate outage. Prayas's own single-monitor supply profiles for 2017–2018
  and its time-of-day and evening figures (Figures 8–9) agree with ours. In Lucknow our daily figure is higher
  than Prayas's but our evening figure is lower; a uniform inflation would push both up.
- The SQL equals an independent Python oracle, and each of the 17 interruptions in the guided demo's group was
  checked against the raw CSV (docs/VALIDATION.md §1, §2).
- No single definition closes the gap: averaging method, connection type, 0 V only, years, the 2019 data,
  inferred minutes, and the coverage threshold. Dropping the 90% coverage rule raises our rural average
  slightly (566 to 574 min/day), because months with less coverage have more outage.
- What we cannot test from the publication: Prayas's exact location-months, how Figure 2 averages, and any
  verification or exclusion step applied to it.

## Security

**26. `npm audit` reports an ECharts advisory. Is the app exposed?**
No. The advisory (ECharts before 6.1.0) is about text placed in a chart tooltip being shown as HTML. VoltProof
puts only dates, numbers and its own fixed wording in tooltips, never a monitor name or anything from an
uploaded file. Even so, every tooltip value goes through an escape function (`esc()` in
`app/web/src/charts.tsx`), so text could never become markup. We kept ECharts 5.6 rather than upgrade to 6 a
week before submission, because version 6 changes the default chart styling (DECISIONS D-036).
