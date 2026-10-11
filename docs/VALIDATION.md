# Validation

This file collects evidence that VoltProof's numbers are right: comparisons with independent
implementations, hand-checked examples, and (G6) a comparison with Prayas's published Uttar Pradesh
figures. Every number here comes from a recorded run. Commands are given so each can be reproduced.

## 1. Independent oracle vs Exasol SQL (G3/G4)

| Check | Scope | Result | Command |
|---|---|---|---|
| Hand-written fixtures (R-1 to R-21) | 14 synthetic fixtures, every hand-derived expected value | all pass | `scripts\test.ps1 -Suite integration` |
| Fixtures, SQL = oracle | all events, daily and monthly rows, pairs, groups, baselines | identical | same |
| Harness sensitivity | a single perturbed expected value or oracle field must be reported | detected | same |
| Random inputs (Hypothesis) | 40 random multi-location batches, randomised parameters | identical (1,874 raw rows, 2,162 events, 228 bridged, 1,063 bounded edges) | `scripts\test.ps1 -Suite differential -Examples 40` |
| Real data, events and aggregates | 4 UP locations, 2018 Jun–Aug | identical (4,930 events, 365 days, 12 months) | same |
| Real data, coincidence | Bahraich + Barabanki, all 49 locations, 2018 Jun–Aug | identical (20,127 pairs, 6,683 groups, 6 district-month baselines) | same |

## 2. Coincidence sanity check on one real month (G4)

**Data:** 2018 June–August, Uttar Pradesh scope; Δ = 2 min, θ = 1 min, N = 20 shifts.
Command: `.venv\Scripts\python.exe -m pipeline.g4_sanity Bahraich 2018-07` (output reproduced below,
run 2026-10-11).

**Observed vs chance (selected district-months):**

| District | Month | Locations | Interruptions | Observed pairs | Expected by chance | Ratio | Empirical p |
|---|---|---:|---:|---:|---:|---:|---:|
| Bahraich | 2018-07 | 21 | 5,985 | 4,322 | 2,149.6 | 2.0 | < 0.05 |
| Bahraich | 2018-08 | 19 | 4,754 | 3,839 | 1,358.4 | 2.8 | < 0.05 |
| Barabanki | 2018-07 | 24 | 5,397 | 2,748 | 1,749.8 | 1.6 | < 0.05 |
| Sitapur | 2018-07 | 19 | 3,895 | 1,712 | 1,008.1 | 1.7 | < 0.05 |
| Lucknow | 2018-06 | 5 | 446 | 59 | 11.8 | 5.0 | < 0.05 |
| Lucknow | 2018-08 | 5 | 203 | 2 | 1.9 | 1.0 | 0.60 |
| Fatehpur | 2018-08 | 2 | 290 | 0 | 1.2 | 0.0 | 1.00 |

"< 0.05" means none of the 20 shifted versions reached the observed count. With N = 20 the smallest
resolvable p is 1/20.

**Reading:** in the large rural districts, coincident interruptions are about 1.6–2.8 times more frequent
than the time-shifted baseline. The baseline keeps each monitor's own daily rhythm, including scheduled
evening cuts, so this excess is not explained by time-of-day routine alone. Some district-months sit at
chance (e.g. Lucknow 2018-08, Fatehpur 2018-08), which is the expected contrast.

**Example group, Bahraich, 25 July 2018 (evening):** group key `Bahraich | 2018-07-25 18:27`, 17 member
interruptions at 17 different monitors, 136 coincident pairs, starts between 18:27 and 18:29. 21
Bahraich monitors had interruptions that month. Each member was checked against the raw CSV
(independently of the SQL): the minute before the start shows supply (137–243 V) and the start minute
reads **0 V**. All 17 pass.

**What this does and does not show:** it shows that independent monitors in one district recorded
loss of supply within two minutes of each other far more often than chance. It does **not** show a
common fault or identify one. A shared upstream cause is plausible, but independent local causes and
scheduled supply arrangements remain possible, and VoltProof reports these only as
"potential shared supply events".

## 3. Comparison with Prayas's published UP figures (G6)

Not yet run. It needs the full 2016–2019 UP files (requested from the user on 2026-10-11).
