-- 090_monthly.sql
-- Monthly roll-up of DAILY (R-12, R-18). coverage_calendar uses all minutes of the calendar month,
-- so a month only partly inside the monitoring window is never "comparable".

CREATE OR REPLACE TABLE MONTHLY AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'coverage.comparable_month_min_coverage_exclusive' THEN NUM_VALUE END) AS COMP
    FROM PARAMS
), A AS (
    SELECT LOCATION_ID,
           CAST(TRUNC(CAL_DAY, 'MM') AS DATE)       AS MONTH_START,
           SUM(EXPECTED_MINUTES)                AS EXPECTED_MINUTES,
           SUM(OBSERVED_MINUTES)                AS OBSERVED_MINUTES,
           SUM(OUTAGE_MIN_LOWER)                AS OUTAGE_MIN_LOWER,
           SUM(OUTAGE_MIN_UPPER)                AS OUTAGE_MIN_UPPER,
           SUM(OUTAGE_ZERO_MINUTES)             AS OUTAGE_ZERO_MINUTES,
           SUM(LOW_MINUTES)                     AS LOW_MINUTES,
           SUM(HIGH_MINUTES)                    AS HIGH_MINUTES,
           SUM(EVENING_OUTAGE_LOWER)            AS EVENING_OUTAGE_LOWER,
           SUM(EVENING_OUTAGE_UPPER)            AS EVENING_OUTAGE_UPPER,
           SUM(INTERRUPTIONS)                   AS INTERRUPTIONS,
           MAX(LONGEST_INTERRUPTION)            AS LONGEST_INTERRUPTION,
           COUNT(*)                             AS DAYS_IN_WINDOW
    FROM DAILY
    GROUP BY LOCATION_ID, CAST(TRUNC(CAL_DAY, 'MM') AS DATE)
)
SELECT A.LOCATION_ID,
       A.MONTH_START,
       TO_CHAR(A.MONTH_START, 'YYYY-MM')                                               AS MONTH_KEY,
       A.EXPECTED_MINUTES, A.OBSERVED_MINUTES, A.OUTAGE_MIN_LOWER, A.OUTAGE_MIN_UPPER,
       A.OUTAGE_ZERO_MINUTES, A.LOW_MINUTES, A.HIGH_MINUTES,
       A.EVENING_OUTAGE_LOWER, A.EVENING_OUTAGE_UPPER, A.INTERRUPTIONS, A.LONGEST_INTERRUPTION,
       A.DAYS_IN_WINDOW,
       CAST(DAYS_BETWEEN(ADD_MONTHS(A.MONTH_START, 1), A.MONTH_START) * 1440 AS DECIMAL(9,0)) AS CALENDAR_MINUTES,
       CAST(A.OBSERVED_MINUTES / A.EXPECTED_MINUTES AS DECIMAL(9,6))                   AS COVERAGE_WINDOW,
       CAST(A.OBSERVED_MINUTES / (DAYS_BETWEEN(ADD_MONTHS(A.MONTH_START, 1), A.MONTH_START) * 1440)
            AS DECIMAL(9,6))                                                           AS COVERAGE_CALENDAR,
       CASE WHEN A.OBSERVED_MINUTES > P.COMP * DAYS_BETWEEN(ADD_MONTHS(A.MONTH_START, 1), A.MONTH_START) * 1440
            THEN TRUE ELSE FALSE END                                                   AS IS_COMPARABLE
FROM A CROSS JOIN P;
