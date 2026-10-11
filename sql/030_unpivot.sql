-- 030_unpivot.sql
-- Unpivot the wide raw rows (one per location-hour) into one row per location-minute, entirely in SQL.
-- Rules: METHODOLOGY R-1 (unpivot, local time), R-2 (validation + quarantine with reason codes).
-- Exasol stores '' as NULL, so a blank cell is simply "no reading" (not quarantined).

-- Row-level problems: unknown location, unparseable date, bad hour. Such rows produce no readings.
CREATE OR REPLACE TABLE ROW_QUARANTINE AS
SELECT h.FILE_ID, h.LINE_NO, h.LOCATION_NAME, h.DATE_STR, h.HOUR_STR,
       CASE
         WHEN l.LOCATION_ID IS NULL THEN 'unknown_location'
         WHEN NOT IS_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY') OR h.DATE_STR IS NULL THEN 'bad_date'
         ELSE 'bad_hour'
       END AS REASON
FROM RAW_HOURLY h
LEFT JOIN LOCATION l ON l.SOURCE_NAME = TRIM(h.LOCATION_NAME)
WHERE l.LOCATION_ID IS NULL
   OR h.DATE_STR IS NULL OR NOT IS_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY')
   OR h.HOUR_STR IS NULL OR NOT IS_NUMBER(TRIM(h.HOUR_STR))
   OR CAST(TRIM(h.HOUR_STR) AS DOUBLE) NOT BETWEEN 0 AND 23
   OR CAST(TRIM(h.HOUR_STR) AS DOUBLE) <> FLOOR(CAST(TRIM(h.HOUR_STR) AS DOUBLE));

-- Minute grid of every structurally valid row, with the raw cell text (still untouched).
CREATE OR REPLACE TABLE MINUTE_RAW AS
WITH MINUTES AS (
    SELECT CAST(LEVEL - 1 AS DECIMAL(2,0)) AS MI FROM DUAL CONNECT BY LEVEL <= 60
), ROWS_OK AS (
    SELECT h.*, l.LOCATION_ID,
           CAST(TO_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY') AS TIMESTAMP) AS DAY_TS,
           CAST(CAST(TRIM(h.HOUR_STR) AS DOUBLE) AS DECIMAL(2,0))     AS HR
    FROM RAW_HOURLY h
    JOIN LOCATION l ON l.SOURCE_NAME = TRIM(h.LOCATION_NAME)
    WHERE IS_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY')
      AND IS_NUMBER(TRIM(h.HOUR_STR))
      AND CAST(TRIM(h.HOUR_STR) AS DOUBLE) BETWEEN 0 AND 23
      AND CAST(TRIM(h.HOUR_STR) AS DOUBLE) = FLOOR(CAST(TRIM(h.HOUR_STR) AS DOUBLE))
)
SELECT h.LOCATION_ID,
       ADD_MINUTES(h.DAY_TS, h.HR * 60 + m.MI) AS TS,
       m.MI                                     AS MINUTE_IDX,
       TRIM(CASE m.MI
            WHEN 0 THEN h.M00
            WHEN 1 THEN h.M01
            WHEN 2 THEN h.M02
            WHEN 3 THEN h.M03
            WHEN 4 THEN h.M04
            WHEN 5 THEN h.M05
            WHEN 6 THEN h.M06
            WHEN 7 THEN h.M07
            WHEN 8 THEN h.M08
            WHEN 9 THEN h.M09
            WHEN 10 THEN h.M10
            WHEN 11 THEN h.M11
            WHEN 12 THEN h.M12
            WHEN 13 THEN h.M13
            WHEN 14 THEN h.M14
            WHEN 15 THEN h.M15
            WHEN 16 THEN h.M16
            WHEN 17 THEN h.M17
            WHEN 18 THEN h.M18
            WHEN 19 THEN h.M19
            WHEN 20 THEN h.M20
            WHEN 21 THEN h.M21
            WHEN 22 THEN h.M22
            WHEN 23 THEN h.M23
            WHEN 24 THEN h.M24
            WHEN 25 THEN h.M25
            WHEN 26 THEN h.M26
            WHEN 27 THEN h.M27
            WHEN 28 THEN h.M28
            WHEN 29 THEN h.M29
            WHEN 30 THEN h.M30
            WHEN 31 THEN h.M31
            WHEN 32 THEN h.M32
            WHEN 33 THEN h.M33
            WHEN 34 THEN h.M34
            WHEN 35 THEN h.M35
            WHEN 36 THEN h.M36
            WHEN 37 THEN h.M37
            WHEN 38 THEN h.M38
            WHEN 39 THEN h.M39
            WHEN 40 THEN h.M40
            WHEN 41 THEN h.M41
            WHEN 42 THEN h.M42
            WHEN 43 THEN h.M43
            WHEN 44 THEN h.M44
            WHEN 45 THEN h.M45
            WHEN 46 THEN h.M46
            WHEN 47 THEN h.M47
            WHEN 48 THEN h.M48
            WHEN 49 THEN h.M49
            WHEN 50 THEN h.M50
            WHEN 51 THEN h.M51
            WHEN 52 THEN h.M52
            WHEN 53 THEN h.M53
            WHEN 54 THEN h.M54
            WHEN 55 THEN h.M55
            WHEN 56 THEN h.M56
            WHEN 57 THEN h.M57
            WHEN 58 THEN h.M58
            WHEN 59 THEN h.M59
       END)                                     AS RAW_VALUE,
       h.FILE_ID,
       h.LINE_NO
FROM ROWS_OK h
CROSS JOIN MINUTES m;

-- Value-level quarantine (R-2): non-numeric or outside the configured valid range.
CREATE OR REPLACE TABLE VALUE_QUARANTINE AS
SELECT LOCATION_ID, TS, RAW_VALUE, FILE_ID, LINE_NO, MINUTE_IDX,
       CASE WHEN NOT IS_NUMBER(RAW_VALUE) THEN 'non_numeric' ELSE 'out_of_range' END AS REASON
FROM MINUTE_RAW
WHERE RAW_VALUE IS NOT NULL
  AND (NOT IS_NUMBER(RAW_VALUE)
       OR CAST(RAW_VALUE AS DOUBLE) < (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.min_valid_v')
       OR CAST(RAW_VALUE AS DOUBLE) > COALESCE((SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.max_valid_v'),
                                               CAST(RAW_VALUE AS DOUBLE)));

-- Valid readings in long form: the analytical base table.
CREATE OR REPLACE TABLE MINUTE_READING AS
SELECT LOCATION_ID, TS, CAST(RAW_VALUE AS DECIMAL(6,1)) AS VOLTAGE, FILE_ID, LINE_NO, MINUTE_IDX
FROM MINUTE_RAW
WHERE RAW_VALUE IS NOT NULL
  AND IS_NUMBER(RAW_VALUE)
  AND CAST(RAW_VALUE AS DOUBLE) >= (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.min_valid_v')
  AND CAST(RAW_VALUE AS DOUBLE) <= COALESCE((SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.max_valid_v'),
                                            CAST(RAW_VALUE AS DOUBLE));

DROP TABLE MINUTE_RAW;
