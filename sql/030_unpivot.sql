-- 030_unpivot.sql
-- Unpivot the wide raw rows (one per location-hour) into one row per location-minute, entirely in SQL.
-- Rules: METHODOLOGY R-1 (unpivot, local time), R-2 (validation + quarantine with reason codes),
-- D-019 (analytical subset). Exasol stores '' as NULL, so a blank cell is "no reading" (not quarantined).
-- Every conversion is guarded by CASE so that malformed input is quarantined instead of aborting the step.

-- Analytical scope (D-019): states / locations listed in PARAMS ('|'-separated; empty = all).
CREATE OR REPLACE TABLE LOCATION_IN_SCOPE AS
SELECT l.LOCATION_ID
FROM LOCATION l
WHERE ((SELECT STR_VALUE FROM PARAMS WHERE NAME = 'subset.states') IS NULL
       OR INSTR('|' || (SELECT STR_VALUE FROM PARAMS WHERE NAME = 'subset.states') || '|',
                '|' || l.STATE_NAME || '|') > 0)
  AND ((SELECT STR_VALUE FROM PARAMS WHERE NAME = 'subset.locations') IS NULL
       OR INSTR('|' || (SELECT STR_VALUE FROM PARAMS WHERE NAME = 'subset.locations') || '|',
                '|' || l.SOURCE_NAME || '|') > 0);

-- Parsed row header fields (NULL when unparseable) for every raw row.
CREATE OR REPLACE TABLE RAW_ROW_PARSED AS
SELECT h.FILE_ID, h.LINE_NO, h.LOCATION_NAME, h.DATE_STR, h.HOUR_STR,
       l.LOCATION_ID,
       CASE WHEN sc.LOCATION_ID IS NULL THEN FALSE ELSE TRUE END                          AS IN_SCOPE,
       CASE WHEN IS_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY')
            THEN CAST(TO_DATE(TRIM(h.DATE_STR), 'DD-MM-YYYY') AS TIMESTAMP) END           AS DAY_TS,
       CASE WHEN IS_NUMBER(TRIM(h.HOUR_STR)) THEN CAST(TRIM(h.HOUR_STR) AS DOUBLE) END   AS HOUR_NUM
FROM RAW_HOURLY h
LEFT JOIN LOCATION l ON l.SOURCE_NAME = TRIM(h.LOCATION_NAME)
LEFT JOIN LOCATION_IN_SCOPE sc ON sc.LOCATION_ID = l.LOCATION_ID;

-- Row-level problems: unknown location, unparseable date, bad hour. Such rows produce no readings.
-- Rows of out-of-scope (known) locations are not analysed and therefore not reported here.
CREATE OR REPLACE TABLE ROW_QUARANTINE AS
SELECT FILE_ID, LINE_NO, LOCATION_NAME, DATE_STR, HOUR_STR,
       CASE
         WHEN LOCATION_ID IS NULL THEN 'unknown_location'
         WHEN DAY_TS IS NULL THEN 'bad_date'
         ELSE 'bad_hour'
       END AS REASON
FROM RAW_ROW_PARSED
WHERE (LOCATION_ID IS NULL OR IN_SCOPE)
  AND (LOCATION_ID IS NULL OR DAY_TS IS NULL OR HOUR_NUM IS NULL
       OR HOUR_NUM NOT BETWEEN 0 AND 23 OR HOUR_NUM <> FLOOR(HOUR_NUM));

-- Minute grid of every valid in-scope row, with the raw cell text (still untouched) and its numeric parse.
CREATE OR REPLACE TABLE MINUTE_RAW AS
WITH MINUTES AS (
    SELECT CAST(LEVEL - 1 AS DECIMAL(2,0)) AS MI FROM DUAL CONNECT BY LEVEL <= 60
), ROWS_OK AS (
    SELECT p.LOCATION_ID, p.FILE_ID, p.LINE_NO, p.DAY_TS, CAST(p.HOUR_NUM AS DECIMAL(2,0)) AS HR
    FROM RAW_ROW_PARSED p
    WHERE p.IN_SCOPE AND p.DAY_TS IS NOT NULL AND p.HOUR_NUM BETWEEN 0 AND 23
      AND p.HOUR_NUM = FLOOR(p.HOUR_NUM)
), CELLS AS (
    SELECT r.LOCATION_ID, r.FILE_ID, r.LINE_NO, r.DAY_TS, r.HR, m.MI,
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
           END) AS RAW_VALUE
    FROM ROWS_OK r
    JOIN RAW_HOURLY h ON h.FILE_ID = r.FILE_ID AND h.LINE_NO = r.LINE_NO
    CROSS JOIN MINUTES m
)
SELECT LOCATION_ID,
       ADD_MINUTES(DAY_TS, HR * 60 + MI)                                   AS TS,
       MI                                                                   AS MINUTE_IDX,
       RAW_VALUE,
       CASE WHEN IS_NUMBER(RAW_VALUE) THEN CAST(RAW_VALUE AS DOUBLE) END    AS V_NUM,
       FILE_ID,
       LINE_NO
FROM CELLS;

-- Value-level quarantine (R-2): non-numeric or outside the configured valid range.
CREATE OR REPLACE TABLE VALUE_QUARANTINE AS
SELECT LOCATION_ID, TS, RAW_VALUE, FILE_ID, LINE_NO, MINUTE_IDX,
       CASE WHEN V_NUM IS NULL THEN 'non_numeric' ELSE 'out_of_range' END AS REASON
FROM MINUTE_RAW
WHERE RAW_VALUE IS NOT NULL
  AND (V_NUM IS NULL
       OR V_NUM < (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.min_valid_v')
       OR V_NUM > COALESCE((SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.max_valid_v'), V_NUM));

-- Valid readings in long form: the analytical base table (duplicates still present; see 040).
CREATE OR REPLACE TABLE MINUTE_READING AS
SELECT LOCATION_ID, TS, CAST(V_NUM AS DECIMAL(6,1)) AS VOLTAGE, FILE_ID, LINE_NO, MINUTE_IDX
FROM MINUTE_RAW
WHERE V_NUM IS NOT NULL
  AND V_NUM >= (SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.min_valid_v')
  AND V_NUM <= COALESCE((SELECT NUM_VALUE FROM PARAMS WHERE NAME = 'data_quality.max_valid_v'), V_NUM);

DROP TABLE MINUTE_RAW;

DROP TABLE RAW_ROW_PARSED;
