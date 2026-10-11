# Methodology (v0.1, draft written before implementation)

This document is the **specification** that the SQL pipeline (`sql/`), the independent test oracle
(`tests/oracle/`) and the hand-written fixtures (`tests/fixtures/`) all follow. Rule IDs (R-x) are cited
by fixtures and tests. Parameters live in `config/method.yaml`, each with its source.

Vocabulary: a **measured** minute has a valid voltage reading. An **inferred** quantity (e.g. an upper
bound) depends on minutes without readings. Missing data is **never** counted as an outage.

## 1. Source data

ESMI files are wide: one row per location-hour, `Location name, Date, Hour (0–23), Min 0 … Min 59`,
voltage in volts. Prayas states: "A '0' voltage reading means a power outage" and "Missing data should
be interpreted as unavailable data and not as interruption." Dataverse metadata for the ingested files
reports no invalid (blank) minute cells, so missing data normally appears as **absent location-hours**.

## 2. Cleaning

- **R-1 Unpivot.** Each raw row becomes 60 minute readings at `Date + Hour:Min`. Prayas documents
  `Hour` as "Hour of the day (0 to 23)" without a time zone. We treat timestamps as local Indian time
  (IST), consistent with Prayas's own evening-window analysis, and apply no conversion (D-015). The
  unpivot runs in SQL in Exasol.
- **R-2 Malformed values.** A reading is invalid if the date (`DD-MM-YYYY`) or hour cannot be parsed,
  the hour is outside 0–23, the value is non-numeric, or the value is below `min_valid_v` (or above
  `max_valid_v` when one is configured; none is by default, see D-013). Invalid readings are kept in a
  quarantine table with a reason code, and their minutes become NO_DATA. A blank cell is simply "no
  reading" (NO_DATA), not a quarantined value.
- **R-3 Duplicates.** If the same (location, minute) appears more than once with the same value, one
  reading is kept and the duplicate is counted. If the values differ, the minute is a **conflict**: it
  becomes NO_DATA (uncertain) and is counted. No value is chosen arbitrarily.
- **R-4 Monitoring window.** Per location: from the first to the last minute with a valid reading. The
  location file's From/To dates are recorded and compared, but they do not define the window.
  Expected minutes and coverage are computed only inside the window.

## 3. Minute states

- **R-5 Classification** of a valid reading v (integer volts in ESMI):
  OUTAGE `v ≤ 130` · LOW `130 < v < 205` · NORMAL `205 ≤ v ≤ 270` · HIGH `v > 270`.
- **R-6 NO_DATA.** Every minute inside the monitoring window without a valid, unique reading. Missing
  data **never** becomes OUTAGE.

## 4. Outage events

- **R-7 Islands.** An outage event is a maximal run of consecutive OUTAGE minutes (gaps-and-islands:
  LAG detects a state change; a running SUM numbers the islands).
- **R-8 Bridging** (off by default, `gap_bridge_max_minutes = 0`). If G > 0, an OUTAGE run, then a
  NO_DATA run of length ≤ G, then an OUTAGE run, form one event. Bridged minutes are stored and the
  event is flagged "contains unobserved minutes". Bridged minutes never count toward the lower bound.
- **R-9 Edge certainty.** An event's start is
  - `exact` if the previous minute is a measured non-outage state;
  - `bounded` if the previous minute is NO_DATA;
  - `censored` if the event starts at the first minute of the monitoring window.
  The end is defined symmetrically, using the next minute.
- **R-10 Duration bounds.**
  - `min_duration` (headline) = measured OUTAGE minutes in the event.
  - `max_duration` = `min_duration` + bridged minutes + for each non-exact edge `min(gap length, cap)`,
    where cap = `max_uncertain_extension_minutes`. For a censored edge, the gap length is unknown and
    taken as `cap`.
- **R-11 Interruptions.** An event counts as an interruption if `min_duration ≥ interruption_min_minutes`
  (default 1; validation also reports 2, ESMI's shortest band).

## 5. Daily and monthly aggregates (per location, IST calendar)

- **R-12 Minute attribution.** Minute-based measures are attributed to the calendar day and month of
  each minute. So an event crossing midnight or a month boundary keeps one `event_id`, but its minutes
  are split by day.
- **R-13 Event attribution.** Counts and "longest interruption" are attributed to the day of the
  event's **first** minute.
- **R-14 Outage minutes, lower bound** = OUTAGE minutes in the day.
- **R-15 Outage minutes, upper bound** = lower bound + **possibly-outage** NO_DATA minutes in the day.
  A NO_DATA minute m in a gap [s, e] is possibly-outage if the run before the gap is OUTAGE and
  `m − s < cap`, or the run after the gap is OUTAGE and `e − m < cap`. Each minute counts once even
  when both neighbours claim it. Gaps on the monitoring-window boundary add nothing to aggregates,
  because minutes outside the window are not counted.
- **R-16 Voltage-quality minutes.** LOW and HIGH minutes per day (measured only).
- **R-16b Zero-voltage share.** OUTAGE minutes are also split into `0 V` minutes and `1–130 V`
  minutes. Prayas counts both as no supply. The split shows how much of an outage was measured as
  zero and how much as voltage too low to use. Some monitors report a floor value (101 V or 99 V)
  during deep sags (G1 evidence, D-014).
- **R-17 Evening window.** Minutes from 17:00 to 22:59 (Prayas: "between 5 and 11pm"). Lower and upper
  evening outage minutes follow R-14/R-15, restricted to the window.
- **R-18 Coverage.** Reported two ways:
  - `coverage_window` = observed minutes / minutes of the period that fall inside the monitoring window
    (completeness while the monitor was deployed);
  - `coverage_calendar` = observed minutes / all minutes of the calendar period (1,440 per day).
  A month is **comparable** if `coverage_calendar` > 0.90. This is the conservative reading of Prayas's
  UP method ("months only where more than 90% of data was available"), so a month that is only partly
  inside the monitoring window is not comparable. Non-comparable periods are greyed out in the UI and
  excluded from cross-location comparisons.

## 6. Potential shared supply events (G4; draft)

- **R-19** Two outage events at different locations in the same district are **coincident** if their
  starts differ by ≤ Δ minutes and they overlap by ≥ θ minutes.
- **R-20** Coincident pairs are grouped into connected components, and each group's id is its earliest
  member event. These are called "potential shared supply events", never faults.
- **R-21 Chance baseline.** Recompute coincidences after circularly shifting each location's events
  by whole days (N shifts), then report observed vs mean expected count.

## 7. Known limitations

- A plug-in home monitor is not the utility's meter. It sees the supply at one socket, and its outages
  may also come from a tripped breaker or the monitor itself.
- The data is historical (2014–2019). The method is the contribution; current smart-meter data is
  future scope.
- Monitor accuracy is ±4 V (Prayas), so classifications within 4 V of a boundary are sensitive.
