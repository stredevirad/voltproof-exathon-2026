-- 095_quality.sql
-- Data-quality summary per in-scope location (spec 5.2 / 8.1): coverage, gaps, duplicates, conflicts,
-- quarantines, value extremes, the 0 V share of outage minutes, and documented vs observed dates.

CREATE OR REPLACE TABLE QUALITY_LOCATION AS
WITH RD AS (
    SELECT LOCATION_ID,
           COUNT(*)                                              AS READINGS_RAW,
           COUNT(DISTINCT FILE_ID)                               AS SOURCE_FILES
    FROM MINUTE_READING GROUP BY LOCATION_ID
), CL AS (
    SELECT LOCATION_ID,
           COUNT(*)                                              AS READINGS_CLEAN,
           SUM(DUPLICATE_COUNT)                                  AS DUPLICATE_READINGS,
           SUM(CASE WHEN SOURCE_FILES > 1 THEN 1 ELSE 0 END)     AS MINUTES_IN_SEVERAL_FILES,
           MAX(VOLTAGE)                                          AS MAX_VOLTAGE,
           SUM(CASE WHEN VOLTAGE = 350 THEN 1 ELSE 0 END)        AS READINGS_AT_350V
    FROM READING_CLEAN GROUP BY LOCATION_ID
), CF AS (
    SELECT LOCATION_ID, COUNT(*) AS CONFLICT_MINUTES,
           SUM(CASE WHEN SOURCE_FILES > 1 THEN 1 ELSE 0 END)     AS CONFLICTS_ACROSS_FILES
    FROM READING_CONFLICT GROUP BY LOCATION_ID
), VQ AS (
    SELECT LOCATION_ID, COUNT(*) AS QUARANTINED_VALUES FROM VALUE_QUARANTINE GROUP BY LOCATION_ID
), SG AS (
    SELECT LOCATION_ID,
           SUM(CASE WHEN SUPPLY_STATE = 'NO_DATA' THEN 1 ELSE 0 END)        AS GAP_COUNT,
           SUM(CASE WHEN SUPPLY_STATE = 'NO_DATA' THEN MINUTES ELSE 0 END)  AS GAP_MINUTES,
           MAX(CASE WHEN SUPPLY_STATE = 'NO_DATA' THEN MINUTES END)         AS LONGEST_GAP_MINUTES
    FROM SEGMENT GROUP BY LOCATION_ID
), MO AS (
    SELECT LOCATION_ID,
           SUM(OUTAGE_MIN_LOWER)                                            AS OUTAGE_MINUTES,
           SUM(OUTAGE_ZERO_MINUTES)                                         AS OUTAGE_ZERO_MINUTES,
           COUNT(*)                                                         AS MONTHS_IN_WINDOW,
           SUM(CASE WHEN IS_COMPARABLE THEN 1 ELSE 0 END)                   AS COMPARABLE_MONTHS
    FROM MONTHLY GROUP BY LOCATION_ID
)
SELECT l.LOCATION_ID, l.SOURCE_NAME, l.DISPLAY_NAME, l.IS_OFFLINE, l.DISTRICT, l.STATE_NAME,
       l.SOURCE_CATEGORY, l.CONNECTION_TYPE, l.DOC_FROM_DATE, l.DOC_TO_DATE,
       w.FIRST_TS, w.LAST_TS,
       CAST(MINUTES_BETWEEN(w.LAST_TS, w.FIRST_TS) + 1 AS DECIMAL(12,0))                 AS WINDOW_MINUTES,
       COALESCE(rd.READINGS_RAW, 0)                                                      AS READINGS_RAW,
       COALESCE(cl.READINGS_CLEAN, 0)                                                    AS READINGS_CLEAN,
       CAST(COALESCE(cl.READINGS_CLEAN, 0) / NULLIF(MINUTES_BETWEEN(w.LAST_TS, w.FIRST_TS) + 1, 0)
            AS DECIMAL(9,6))                                                             AS COVERAGE_WINDOW,
       COALESCE(cl.DUPLICATE_READINGS, 0)                                                AS DUPLICATE_READINGS,
       COALESCE(cf.CONFLICT_MINUTES, 0)                                                  AS CONFLICT_MINUTES,
       COALESCE(cf.CONFLICTS_ACROSS_FILES, 0)                                            AS CONFLICTS_ACROSS_FILES,
       COALESCE(cl.MINUTES_IN_SEVERAL_FILES, 0)                                          AS MINUTES_IN_SEVERAL_FILES,
       COALESCE(vq.QUARANTINED_VALUES, 0)                                                AS QUARANTINED_VALUES,
       COALESCE(sg.GAP_COUNT, 0)                                                         AS GAP_COUNT,
       COALESCE(sg.GAP_MINUTES, 0)                                                       AS GAP_MINUTES,
       COALESCE(sg.LONGEST_GAP_MINUTES, 0)                                               AS LONGEST_GAP_MINUTES,
       cl.MAX_VOLTAGE,
       COALESCE(cl.READINGS_AT_350V, 0)                                                  AS READINGS_AT_350V,
       COALESCE(mo.OUTAGE_MINUTES, 0)                                                    AS OUTAGE_MINUTES,
       COALESCE(mo.OUTAGE_ZERO_MINUTES, 0)                                               AS OUTAGE_ZERO_MINUTES,
       COALESCE(mo.MONTHS_IN_WINDOW, 0)                                                  AS MONTHS_IN_WINDOW,
       COALESCE(mo.COMPARABLE_MONTHS, 0)                                                 AS COMPARABLE_MONTHS,
       CASE WHEN l.DOC_FROM_DATE IS NOT NULL AND CAST(w.FIRST_TS AS DATE) < l.DOC_FROM_DATE
              OR l.DOC_TO_DATE IS NOT NULL AND CAST(w.LAST_TS AS DATE) > l.DOC_TO_DATE
            THEN TRUE ELSE FALSE END                                                    AS READINGS_OUTSIDE_DOC_DATES
FROM LOCATION l
JOIN MONITOR_WINDOW w ON w.LOCATION_ID = l.LOCATION_ID
LEFT JOIN RD rd ON rd.LOCATION_ID = l.LOCATION_ID
LEFT JOIN CL cl ON cl.LOCATION_ID = l.LOCATION_ID
LEFT JOIN CF cf ON cf.LOCATION_ID = l.LOCATION_ID
LEFT JOIN VQ vq ON vq.LOCATION_ID = l.LOCATION_ID
LEFT JOIN SG sg ON sg.LOCATION_ID = l.LOCATION_ID
LEFT JOIN MO mo ON mo.LOCATION_ID = l.LOCATION_ID;

-- One-row summary per source file (rows loaded, quarantined, in-scope), so a format change that silently
-- empties a file is visible immediately.
CREATE OR REPLACE TABLE QUALITY_FILE AS
SELECT f.FILE_ID, f.FILE_NAME, f.FILE_KIND, f.ROWS_EXPECTED, f.ROWS_LOADED,
       dcl.PERIOD_FROM, dcl.PERIOD_TO, dcl.EXCLUDE_REASON,
       CASE WHEN fmt.N_DASH >= fmt.N_SLASH THEN fmt.DASH_FORMAT ELSE fmt.SLASH_FORMAT END AS DATE_FORMAT,
       COALESCE(q.ROWS_QUARANTINED, 0)                                    AS ROWS_QUARANTINED,
       COALESCE(q.UNKNOWN_LOCATION, 0)                                    AS ROWS_UNKNOWN_LOCATION,
       COALESCE(q.BAD_DATE, 0)                                            AS ROWS_BAD_DATE,
       COALESCE(q.AMBIGUOUS_DATE, 0)                                      AS ROWS_AMBIGUOUS_DATE,
       COALESCE(q.BAD_HOUR, 0)                                            AS ROWS_BAD_HOUR,
       COALESCE(q.OUTSIDE_PERIOD, 0)                                      AS ROWS_OUTSIDE_DECLARED_PERIOD,
       COALESCE(v.VALUES_QUARANTINED, 0)                                  AS VALUES_QUARANTINED,
       COALESCE(m.MINUTES_IN_SCOPE, 0)                                    AS MINUTES_IN_SCOPE
FROM SOURCE_FILE f
LEFT JOIN SOURCE_FILE_DECLARED dcl ON dcl.FILE_ID = f.FILE_ID
LEFT JOIN FILE_DATE_FORMAT fmt ON fmt.FILE_ID = f.FILE_ID
LEFT JOIN (SELECT FILE_ID, COUNT(*) AS ROWS_QUARANTINED,
                  SUM(CASE WHEN REASON = 'unknown_location' THEN 1 ELSE 0 END)        AS UNKNOWN_LOCATION,
                  SUM(CASE WHEN REASON = 'bad_date' THEN 1 ELSE 0 END)                AS BAD_DATE,
                  SUM(CASE WHEN REASON = 'ambiguous_date_format' THEN 1 ELSE 0 END)   AS AMBIGUOUS_DATE,
                  SUM(CASE WHEN REASON = 'bad_hour' THEN 1 ELSE 0 END)                AS BAD_HOUR,
                  SUM(CASE WHEN REASON = 'outside_declared_period' THEN 1 ELSE 0 END) AS OUTSIDE_PERIOD
           FROM ROW_QUARANTINE GROUP BY FILE_ID) q ON q.FILE_ID = f.FILE_ID
LEFT JOIN (SELECT FILE_ID, COUNT(*) AS VALUES_QUARANTINED FROM VALUE_QUARANTINE GROUP BY FILE_ID) v
       ON v.FILE_ID = f.FILE_ID
LEFT JOIN (SELECT FILE_ID, COUNT(*) AS MINUTES_IN_SCOPE FROM MINUTE_READING GROUP BY FILE_ID) m
       ON m.FILE_ID = f.FILE_ID;
