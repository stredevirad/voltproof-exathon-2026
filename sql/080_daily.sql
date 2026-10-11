-- 080_daily.sql
-- R-12..R-18 per location and calendar day. The calendar covers every day of each monitoring window,
-- so days without any reading are kept (observed 0, coverage 0) instead of disappearing.

CREATE OR REPLACE TABLE LOCATION_DAY AS
WITH N AS (
    SELECT CAST(LEVEL - 1 AS DECIMAL(6,0)) AS K FROM DUAL CONNECT BY LEVEL <= 10000
)
SELECT w.LOCATION_ID,
       ADD_DAYS(CAST(w.FIRST_TS AS DATE), N.K)                                  AS CAL_DAY,
       CAST(ADD_DAYS(CAST(w.FIRST_TS AS DATE), N.K) AS TIMESTAMP)               AS DAY_START,
       ADD_MINUTES(CAST(ADD_DAYS(CAST(w.FIRST_TS AS DATE), N.K) AS TIMESTAMP), 1439) AS DAY_END,
       w.FIRST_TS,
       w.LAST_TS
FROM MONITOR_WINDOW w
JOIN N ON ADD_DAYS(CAST(w.FIRST_TS AS DATE), N.K) <= CAST(w.LAST_TS AS DATE);

CREATE OR REPLACE TABLE DAILY AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'windows.evening_start_hour'         THEN NUM_VALUE END) AS EV_START,
           MAX(CASE WHEN NAME = 'windows.evening_end_hour_exclusive' THEN NUM_VALUE END) AS EV_END
    FROM PARAMS
), M AS (   -- measured minutes per day (R-14, R-16, R-16b, R-17 lower bound)
    SELECT rs.LOCATION_ID,
           CAST(rs.TS AS DATE)                                                         AS CAL_DAY,
           COUNT(*)                                                                    AS OBSERVED,
           SUM(CASE WHEN rs.SUPPLY_STATE = 'OUTAGE' THEN 1 ELSE 0 END)                         AS OUT_LOWER,
           SUM(CASE WHEN rs.SUPPLY_STATE = 'OUTAGE' AND rs.VOLTAGE = 0 THEN 1 ELSE 0 END)       AS OUT_ZERO,
           SUM(CASE WHEN rs.SUPPLY_STATE = 'LOW'  THEN 1 ELSE 0 END)                           AS LOW_MIN,
           SUM(CASE WHEN rs.SUPPLY_STATE = 'HIGH' THEN 1 ELSE 0 END)                           AS HIGH_MIN,
           SUM(CASE WHEN rs.SUPPLY_STATE = 'OUTAGE' AND HOUR(rs.TS) >= P.EV_START AND HOUR(rs.TS) < P.EV_END
                    THEN 1 ELSE 0 END)                                                  AS EV_LOWER
    FROM READING_STATE rs CROSS JOIN P
    GROUP BY rs.LOCATION_ID, CAST(rs.TS AS DATE)
), CL AS (  -- possibly-outage NO_DATA minutes overlapping each day and its evening window (R-15, R-17)
    SELECT d.LOCATION_ID, d.CAL_DAY,
           SUM(GREATEST(0, MINUTES_BETWEEN(LEAST(c.CLAIM_END, d.DAY_END),
                                           GREATEST(c.CLAIM_START, d.DAY_START)) + 1))  AS CLAIM_MIN,
           SUM(GREATEST(0, MINUTES_BETWEEN(
                   LEAST(c.CLAIM_END, ADD_MINUTES(d.DAY_START, P.EV_END * 60 - 1)),
                   GREATEST(c.CLAIM_START, ADD_MINUTES(d.DAY_START, P.EV_START * 60))) + 1)) AS CLAIM_EV_MIN
    FROM LOCATION_DAY d
    JOIN UNCERTAIN_CLAIM c
      ON c.LOCATION_ID = d.LOCATION_ID AND c.CLAIM_START <= d.DAY_END AND c.CLAIM_END >= d.DAY_START
    CROSS JOIN P
    GROUP BY d.LOCATION_ID, d.CAL_DAY
), EV AS (  -- interruptions attributed to the day of their first minute (R-13)
    SELECT LOCATION_ID, CAST(START_TS AS DATE) AS CAL_DAY,
           COUNT(*) AS INTERRUPTIONS, MAX(MIN_DURATION) AS LONGEST
    FROM EVENT
    WHERE IS_INTERRUPTION
    GROUP BY LOCATION_ID, CAST(START_TS AS DATE)
)
SELECT d.LOCATION_ID,
       d.CAL_DAY,
       CAST(MINUTES_BETWEEN(LEAST(d.DAY_END, d.LAST_TS), GREATEST(d.DAY_START, d.FIRST_TS)) + 1
            AS DECIMAL(6,0))                                                     AS EXPECTED_MINUTES,
       CAST(COALESCE(m.OBSERVED, 0) AS DECIMAL(6,0))                             AS OBSERVED_MINUTES,
       CAST(COALESCE(m.OUT_LOWER, 0) AS DECIMAL(6,0))                            AS OUTAGE_MIN_LOWER,
       CAST(COALESCE(m.OUT_LOWER, 0) + COALESCE(cl.CLAIM_MIN, 0) AS DECIMAL(6,0)) AS OUTAGE_MIN_UPPER,
       CAST(COALESCE(m.OUT_ZERO, 0) AS DECIMAL(6,0))                             AS OUTAGE_ZERO_MINUTES,
       CAST(COALESCE(m.LOW_MIN, 0) AS DECIMAL(6,0))                              AS LOW_MINUTES,
       CAST(COALESCE(m.HIGH_MIN, 0) AS DECIMAL(6,0))                             AS HIGH_MINUTES,
       CAST(COALESCE(m.EV_LOWER, 0) AS DECIMAL(6,0))                             AS EVENING_OUTAGE_LOWER,
       CAST(COALESCE(m.EV_LOWER, 0) + COALESCE(cl.CLAIM_EV_MIN, 0) AS DECIMAL(6,0)) AS EVENING_OUTAGE_UPPER,
       CAST(COALESCE(ev.INTERRUPTIONS, 0) AS DECIMAL(6,0))                       AS INTERRUPTIONS,
       CAST(COALESCE(ev.LONGEST, 0) AS DECIMAL(6,0))                             AS LONGEST_INTERRUPTION
FROM LOCATION_DAY d
LEFT JOIN M  m  ON m.LOCATION_ID  = d.LOCATION_ID AND m.CAL_DAY  = d.CAL_DAY
LEFT JOIN CL cl ON cl.LOCATION_ID = d.LOCATION_ID AND cl.CAL_DAY = d.CAL_DAY
LEFT JOIN EV ev ON ev.LOCATION_ID = d.LOCATION_ID AND ev.CAL_DAY = d.CAL_DAY;
