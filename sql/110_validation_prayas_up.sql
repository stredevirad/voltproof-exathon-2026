-- 110_validation_prayas_up.sql
-- Comparison with Prayas (Energy Group), "ESMI in Uttar Pradesh" (7 Aug 2019). See docs/VALIDATION.md §3.
-- Prayas's method as published: UP, calendar years 2016-19, "Data from a location was considered for months only
-- where more than 90% of data was available", categories megacity / other municipal area / rural, evening
-- = 5-11 pm (megacity evening figure is for Lucknow). Prayas does not state how averages were formed, so several
-- definitions are computed side by side; none is tuned to match.

-- Category mapping (D-030). Our location file says State Capital / District Headquarters / Other Municipal Area /
-- Gram Panchayat. Lucknow (State Capital) + Kanpur's District Headquarters monitors = 10 domestic + 7
-- non-domestic, vs Prayas's megacity 9 + 7.
CREATE OR REPLACE TABLE VALIDATION_CATEGORY AS
SELECT l.LOCATION_ID, l.SOURCE_NAME, l.DISTRICT, l.SOURCE_CATEGORY, l.CONNECTION_TYPE,
       CASE WHEN l.SOURCE_CATEGORY = 'State Capital' THEN 'megacity'
            WHEN l.SOURCE_CATEGORY = 'District Headquarters' AND l.DISTRICT = 'Kanpur' THEN 'megacity'
            WHEN l.SOURCE_CATEGORY IN ('District Headquarters', 'Other Municipal Area') THEN 'other municipal'
            WHEN l.SOURCE_CATEGORY = 'Gram Panchayat' THEN 'rural' END AS PRAYAS_CATEGORY
FROM LOCATION l
JOIN MONITOR_WINDOW w ON w.LOCATION_ID = l.LOCATION_ID
WHERE l.STATE_NAME = 'Uttar Pradesh';

-- Evening (17:00-22:59) measured minutes per location-month, so evening averages can be per measured evening.
CREATE OR REPLACE TABLE VALIDATION_EVENING_OBS AS
SELECT rs.LOCATION_ID, CAST(TRUNC(rs.TS, 'MM') AS DATE) AS MONTH_START, COUNT(*) AS EVENING_OBSERVED_MINUTES
FROM READING_STATE rs
WHERE HOUR(rs.TS) >= (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'windows.evening_start_hour')
  AND HOUR(rs.TS) <  (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'windows.evening_end_hour_exclusive')
GROUP BY rs.LOCATION_ID, CAST(TRUNC(rs.TS, 'MM') AS DATE);

-- Interruptions of at least 2 minutes (ESMI's shortest band), attributed to the start month, for the
-- alternative counting rule.
CREATE OR REPLACE TABLE VALIDATION_INT2 AS
SELECT LOCATION_ID, CAST(TRUNC(START_TS, 'MM') AS DATE) AS MONTH_START, COUNT(*) AS INTERRUPTIONS_2MIN
FROM EVENT
WHERE MIN_DURATION >= 2
GROUP BY LOCATION_ID, CAST(TRUNC(START_TS, 'MM') AS DATE);

-- Comparable location-months in the study period (2016-01 .. 2019-12; our usable 2019 data ends in June).
CREATE OR REPLACE TABLE VALIDATION_LM AS
SELECT c.PRAYAS_CATEGORY, c.DISTRICT, m.LOCATION_ID, m.MONTH_START,
       m.OBSERVED_MINUTES / 1440.0                              AS OBS_DAYS,
       COALESCE(e.EVENING_OBSERVED_MINUTES, 0) / 360.0          AS OBS_EVENINGS,
       m.OUTAGE_MIN_LOWER, m.OUTAGE_MIN_UPPER, m.INTERRUPTIONS, COALESCE(i2.INTERRUPTIONS_2MIN, 0) AS INTERRUPTIONS_2MIN,
       m.EVENING_OUTAGE_LOWER, m.EVENING_OUTAGE_UPPER
FROM MONTHLY m
JOIN VALIDATION_CATEGORY c ON c.LOCATION_ID = m.LOCATION_ID
LEFT JOIN VALIDATION_EVENING_OBS e ON e.LOCATION_ID = m.LOCATION_ID AND e.MONTH_START = m.MONTH_START
LEFT JOIN VALIDATION_INT2 i2 ON i2.LOCATION_ID = m.LOCATION_ID AND i2.MONTH_START = m.MONTH_START
WHERE m.IS_COMPARABLE
  AND m.MONTH_START >= DATE '2016-01-01' AND m.MONTH_START < DATE '2020-01-01';

-- Results per category (and Lucknow alone for the megacity evening figure).
CREATE OR REPLACE TABLE VALIDATION_PRAYAS_UP AS
WITH G AS (
    SELECT PRAYAS_CATEGORY AS GRP, LOCATION_ID, MONTH_START, OBS_DAYS, OBS_EVENINGS, OUTAGE_MIN_LOWER,
           OUTAGE_MIN_UPPER, INTERRUPTIONS, INTERRUPTIONS_2MIN, EVENING_OUTAGE_LOWER, EVENING_OUTAGE_UPPER
    FROM VALIDATION_LM
    UNION ALL
    SELECT 'Lucknow (megacity evening)', LOCATION_ID, MONTH_START, OBS_DAYS, OBS_EVENINGS, OUTAGE_MIN_LOWER,
           OUTAGE_MIN_UPPER, INTERRUPTIONS, INTERRUPTIONS_2MIN, EVENING_OUTAGE_LOWER, EVENING_OUTAGE_UPPER
    FROM VALIDATION_LM WHERE DISTRICT = 'Lucknow'
)
SELECT GRP,
       COUNT(DISTINCT LOCATION_ID)                                                       AS LOCATIONS,
       COUNT(*)                                                                          AS LOCATION_MONTHS,
       ROUND(SUM(OBS_DAYS), 1)                                                           AS OBSERVED_DAYS,
       -- daily outage minutes
       ROUND(SUM(OUTAGE_MIN_LOWER) / SUM(OBS_DAYS), 1)                                   AS OUTAGE_MIN_PER_DAY_POOLED,
       ROUND(AVG(OUTAGE_MIN_LOWER / OBS_DAYS), 1)                                        AS OUTAGE_MIN_PER_DAY_MEAN_LM,
       ROUND(SUM(OUTAGE_MIN_UPPER) / SUM(OBS_DAYS), 1)                                   AS OUTAGE_MIN_PER_DAY_UPPER,
       -- outages per day
       ROUND(SUM(INTERRUPTIONS) / SUM(OBS_DAYS), 2)                                      AS INTERRUPTIONS_PER_DAY_1MIN,
       ROUND(SUM(INTERRUPTIONS_2MIN) / SUM(OBS_DAYS), 2)                                 AS INTERRUPTIONS_PER_DAY_2MIN,
       ROUND(AVG(INTERRUPTIONS / OBS_DAYS), 2)                                           AS INTERRUPTIONS_PER_DAY_1MIN_MEAN_LM,
       -- evening (17:00-23:00) outage minutes per day
       ROUND(SUM(EVENING_OUTAGE_LOWER) / SUM(OBS_EVENINGS), 1)                           AS EVENING_MIN_PER_EVENING,
       ROUND(SUM(EVENING_OUTAGE_LOWER) / SUM(OBS_DAYS), 1)                               AS EVENING_MIN_PER_DAY,
       MIN(MONTH_START)                                                                  AS FIRST_MONTH,
       MAX(MONTH_START)                                                                  AS LAST_MONTH
FROM G
GROUP BY GRP;
