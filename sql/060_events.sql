-- 060_events.sql
-- R-7 outage events, R-8 bridging (off when gap_bridge_max_minutes = 0), R-9 edge certainty,
-- R-10 duration bounds, R-11 interruption flag. Works on SEGMENT runs (second gaps-and-islands pass).

CREATE OR REPLACE TABLE EVENT AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'events.gap_bridge_max_minutes'          THEN NUM_VALUE END) AS G,
           MAX(CASE WHEN NAME = 'events.max_uncertain_extension_minutes' THEN NUM_VALUE END) AS CAP,
           MAX(CASE WHEN NAME = 'events.interruption_min_minutes'        THEN NUM_VALUE END) AS INT_MIN
    FROM PARAMS
), S AS (
    SELECT s.*,
           LAG(SUPPLY_STATE)  OVER (PARTITION BY LOCATION_ID ORDER BY SEG_NO) AS PREV_STATE,
           LEAD(SUPPLY_STATE) OVER (PARTITION BY LOCATION_ID ORDER BY SEG_NO) AS NEXT_STATE
    FROM SEGMENT s
), F AS (
    -- a segment belongs to an event if it is OUTAGE, or a short NO_DATA run between two OUTAGE runs
    SELECT S.*,
           CASE WHEN SUPPLY_STATE = 'OUTAGE' THEN 1
                WHEN SUPPLY_STATE = 'NO_DATA' AND PREV_STATE = 'OUTAGE' AND NEXT_STATE = 'OUTAGE'
                     AND MINUTES <= P.G THEN 1
                ELSE 0 END AS IN_EV
    FROM S CROSS JOIN P
), F2 AS (
    SELECT F.*,
           CASE WHEN IN_EV = 1
                 AND COALESCE(LAG(IN_EV) OVER (PARTITION BY LOCATION_ID ORDER BY SEG_NO), 0) = 0
                THEN 1 ELSE 0 END AS EV_START
    FROM F
), E AS (
    SELECT F2.*,
           SUM(EV_START) OVER (PARTITION BY LOCATION_ID ORDER BY SEG_NO
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS EV_GRP
    FROM F2
), EV AS (
    SELECT LOCATION_ID, EV_GRP,
           MIN(SEG_NO)                                                   AS FIRST_SEG,
           MAX(SEG_NO)                                                   AS LAST_SEG,
           MIN(START_TS)                                                 AS START_TS,
           MAX(END_TS)                                                   AS END_TS,
           SUM(CASE WHEN SUPPLY_STATE = 'OUTAGE'  THEN MINUTES ELSE 0 END)      AS MIN_DURATION,
           SUM(CASE WHEN SUPPLY_STATE = 'NO_DATA' THEN MINUTES ELSE 0 END)      AS BRIDGED_MINUTES,
           SUM(ZERO_MINUTES)                                             AS ZERO_MINUTES
    FROM E
    WHERE IN_EV = 1
    GROUP BY LOCATION_ID, EV_GRP
), B AS (
    SELECT ev.*,
           pr.SUPPLY_STATE AS BEFORE_STATE, pr.MINUTES AS BEFORE_MINUTES,
           nx.SUPPLY_STATE AS AFTER_STATE,  nx.MINUTES AS AFTER_MINUTES
    FROM EV ev
    LEFT JOIN SEGMENT pr ON pr.LOCATION_ID = ev.LOCATION_ID AND pr.SEG_NO = ev.FIRST_SEG - 1
    LEFT JOIN SEGMENT nx ON nx.LOCATION_ID = ev.LOCATION_ID AND nx.SEG_NO = ev.LAST_SEG + 1
), C AS (
    SELECT B.*,
           CASE WHEN BEFORE_STATE IS NULL THEN 'censored'
                WHEN BEFORE_STATE = 'NO_DATA' THEN 'bounded' ELSE 'exact' END          AS START_CERTAINTY,
           CASE WHEN AFTER_STATE IS NULL THEN 'censored'
                WHEN AFTER_STATE = 'NO_DATA' THEN 'bounded' ELSE 'exact' END           AS END_CERTAINTY,
           CASE WHEN BEFORE_STATE IS NULL THEN P.CAP
                WHEN BEFORE_STATE = 'NO_DATA' THEN LEAST(BEFORE_MINUTES, P.CAP) ELSE 0 END AS START_EXT,
           CASE WHEN AFTER_STATE IS NULL THEN P.CAP
                WHEN AFTER_STATE = 'NO_DATA' THEN LEAST(AFTER_MINUTES, P.CAP) ELSE 0 END   AS END_EXT,
           P.INT_MIN
    FROM B CROSS JOIN P
)
SELECT CAST(ROW_NUMBER() OVER (ORDER BY LOCATION_ID, START_TS) AS DECIMAL(18,0))         AS EVENT_ID,
       LOCATION_ID,
       'OUTAGE'                                                                        AS EVENT_TYPE,
       START_TS,
       END_TS,
       CAST(MIN_DURATION AS DECIMAL(12,0))                                             AS MIN_DURATION,
       CAST(MIN_DURATION + BRIDGED_MINUTES + START_EXT + END_EXT AS DECIMAL(12,0))     AS MAX_DURATION,
       CAST(BRIDGED_MINUTES AS DECIMAL(12,0))                                          AS BRIDGED_MINUTES,
       CAST(ZERO_MINUTES AS DECIMAL(12,0))                                             AS ZERO_MINUTES,
       START_CERTAINTY,
       END_CERTAINTY,
       CASE WHEN MIN_DURATION >= INT_MIN THEN TRUE ELSE FALSE END                      AS IS_INTERRUPTION,
       FIRST_SEG,
       LAST_SEG
FROM C;
