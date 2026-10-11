-- 050_segments.sql
-- R-5 classification, R-6 NO_DATA, R-7 islands (D-018: NO_DATA stored as runs, not per minute).

-- R-5: state of every clean reading, thresholds from PARAMS (never hard-coded).
CREATE OR REPLACE TABLE READING_STATE AS
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

-- Gaps-and-islands over readings: a new run starts when the state changes OR the previous reading is
-- not exactly one minute earlier (a gap ends any run).
CREATE OR REPLACE TABLE MEASURED_RUN AS
WITH C AS (
    SELECT LOCATION_ID, TS, VOLTAGE, SUPPLY_STATE,
           CASE WHEN SUPPLY_STATE = LAG(SUPPLY_STATE) OVER (PARTITION BY LOCATION_ID ORDER BY TS)
                 AND MINUTES_BETWEEN(TS, LAG(TS) OVER (PARTITION BY LOCATION_ID ORDER BY TS)) = 1
                THEN 0 ELSE 1 END AS IS_NEW
    FROM READING_STATE
), I AS (
    SELECT LOCATION_ID, TS, VOLTAGE, SUPPLY_STATE,
           SUM(IS_NEW) OVER (PARTITION BY LOCATION_ID ORDER BY TS
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RUN_NO
    FROM C
)
SELECT LOCATION_ID,
       RUN_NO,
       MIN(SUPPLY_STATE)                                         AS SUPPLY_STATE,
       MIN(TS)                                            AS START_TS,
       MAX(TS)                                            AS END_TS,
       COUNT(*)                                           AS MINUTES,
       SUM(CASE WHEN VOLTAGE = 0 THEN 1 ELSE 0 END)       AS ZERO_MINUTES,
       MIN(VOLTAGE)                                       AS MIN_VOLTAGE,
       MAX(VOLTAGE)                                       AS MAX_VOLTAGE
FROM I
GROUP BY LOCATION_ID, RUN_NO;

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
