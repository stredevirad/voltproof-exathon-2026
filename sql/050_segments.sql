-- 050_segments.sql
-- R-5 classification, R-6 NO_DATA, R-7 islands (D-018: NO_DATA stored as runs, not per minute).

-- R-5: state of every clean reading, thresholds from PARAMS (never hard-coded). A view, not a table: it is
-- a CASE over READING_CLEAN, and materialising it rewrote ~90M rows on the full UP load for no gain (D-028).
DROP TABLE IF EXISTS READING_STATE;

CREATE OR REPLACE VIEW READING_STATE AS
SELECT r.LOCATION_ID,
       r.TS,
       r.VOLTAGE,
       CASE WHEN r.VOLTAGE <= p.OUT_MAX  THEN 'OUTAGE'
            WHEN r.VOLTAGE <  p.NORM_MIN THEN 'LOW'
            WHEN r.VOLTAGE <= p.NORM_MAX THEN 'NORMAL'
            ELSE 'HIGH' END AS SUPPLY_STATE
FROM READING_CLEAN r
CROSS JOIN (
    SELECT MAX(CASE WHEN NAME = 'classification.outage_max_v' THEN NUM_VALUE END) AS OUT_MAX,
           MAX(CASE WHEN NAME = 'classification.normal_min_v' THEN NUM_VALUE END) AS NORM_MIN,
           MAX(CASE WHEN NAME = 'classification.normal_max_v' THEN NUM_VALUE END) AS NORM_MAX
    FROM PARAMS
) p;

-- Gaps-and-islands over readings (R-7): maximal runs of consecutive minutes in the same state. Within one
-- location and state, (minute number - ROW_NUMBER) is constant along consecutive minutes and jumps at any
-- gap or interruption by another state, so it identifies the run. One window function over the readings,
-- no LAG and no running SUM: the earlier LAG + running-SUM version needed two full sorts of the ~90M UP
-- minutes and ran for more than 10 minutes, with ~6 GB temporary RAM (D-028). Same runs (fixtures + oracle).
CREATE OR REPLACE TABLE MEASURED_RUN AS
WITH K AS (
    SELECT LOCATION_ID, TS, VOLTAGE, SUPPLY_STATE,
           MINUTES_BETWEEN(TS, TIMESTAMP '2000-01-01 00:00:00')
             - ROW_NUMBER() OVER (PARTITION BY LOCATION_ID, SUPPLY_STATE ORDER BY TS) AS RUN_KEY
    FROM READING_STATE
)
SELECT LOCATION_ID,
       SUPPLY_STATE,
       MIN(TS)                                            AS START_TS,
       MAX(TS)                                            AS END_TS,
       COUNT(*)                                           AS MINUTES,
       SUM(CASE WHEN VOLTAGE = 0 THEN 1 ELSE 0 END)       AS ZERO_MINUTES,
       MIN(VOLTAGE)                                       AS MIN_VOLTAGE,
       MAX(VOLTAGE)                                       AS MAX_VOLTAGE
FROM K
GROUP BY LOCATION_ID, SUPPLY_STATE, RUN_KEY;

-- R-6: NO_DATA runs are the gaps between consecutive measured runs inside the monitoring window.
CREATE OR REPLACE TABLE SEGMENT AS
WITH G AS (
    SELECT LOCATION_ID, START_TS, END_TS, SUPPLY_STATE, MINUTES, ZERO_MINUTES, MIN_VOLTAGE, MAX_VOLTAGE,
           LEAD(START_TS) OVER (PARTITION BY LOCATION_ID ORDER BY START_TS) AS NEXT_START
    FROM MEASURED_RUN
), U AS (
    SELECT LOCATION_ID, START_TS, END_TS, SUPPLY_STATE, MINUTES, ZERO_MINUTES, MIN_VOLTAGE, MAX_VOLTAGE
    FROM G
    UNION ALL
    SELECT LOCATION_ID,
           ADD_MINUTES(END_TS, 1),
           ADD_MINUTES(NEXT_START, -1),
           'NO_DATA',
           MINUTES_BETWEEN(NEXT_START, END_TS) - 1,
           0,
           NULL,
           NULL
    FROM G
    WHERE NEXT_START IS NOT NULL AND MINUTES_BETWEEN(NEXT_START, END_TS) > 1
)
SELECT LOCATION_ID,
       CAST(ROW_NUMBER() OVER (PARTITION BY LOCATION_ID ORDER BY START_TS) AS DECIMAL(12,0)) AS SEG_NO,
       SUPPLY_STATE, START_TS, END_TS, CAST(MINUTES AS DECIMAL(12,0)) AS MINUTES, ZERO_MINUTES,
       MIN_VOLTAGE, MAX_VOLTAGE
FROM U;
