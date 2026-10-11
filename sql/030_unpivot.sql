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

-- Date format per file, detected from the data itself (R-1, D-025). Dash dates follow the documented
-- ESMI convention DD-MM-YYYY unless the data contradicts it; slash dates (2019 files) must be decidable
-- from the data (a part > 12), otherwise they are quarantined as ambiguous, never guessed.
CREATE OR REPLACE TABLE FILE_DATE_FORMAT AS
WITH S AS (
    SELECT FILE_ID,
           SUM(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' THEN 1 ELSE 0 END) AS N_DASH,
           SUM(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' THEN 1 ELSE 0 END) AS N_SLASH,
           MAX(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                    THEN CAST(REGEXP_SUBSTR(TRIM(DATE_STR), '[0-9]+', 1, 1) AS DECIMAL(4,0)) END)      AS DASH_MAX1,
           MAX(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                    THEN CAST(REGEXP_SUBSTR(TRIM(DATE_STR), '[0-9]+', 1, 2) AS DECIMAL(4,0)) END)      AS DASH_MAX2,
           MAX(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                    THEN CAST(REGEXP_SUBSTR(TRIM(DATE_STR), '[0-9]+', 1, 1) AS DECIMAL(4,0)) END)      AS SLASH_MAX1,
           MAX(CASE WHEN TRIM(DATE_STR) REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                    THEN CAST(REGEXP_SUBSTR(TRIM(DATE_STR), '[0-9]+', 1, 2) AS DECIMAL(4,0)) END)      AS SLASH_MAX2
    FROM RAW_HOURLY
    GROUP BY FILE_ID
)
SELECT S.*,
       CASE WHEN DASH_MAX2 > 12 AND DASH_MAX1 <= 12 THEN 'MM-DD-YYYY' ELSE 'DD-MM-YYYY' END   AS DASH_FORMAT,
       CASE WHEN SLASH_MAX2 > 12 AND SLASH_MAX1 <= 12 THEN 'MM/DD/YYYY'
            WHEN SLASH_MAX1 > 12 AND SLASH_MAX2 <= 12 THEN 'DD/MM/YYYY' END                   AS SLASH_FORMAT
FROM S;

-- Location name matching (D-029): exact source name first; otherwise the normalised MATCH_KEY, but only
-- when that key identifies exactly one location. Every distinct raw name and how it matched is recorded.
CREATE OR REPLACE TABLE NAME_MATCH AS
WITH N AS (
    SELECT FILE_ID, TRIM(LOCATION_NAME) AS RAW_NAME, COUNT(*) AS N_ROWS,
           TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(TRIM(LOCATION_NAME)), '[offline]', ''),
                                              '\s*-\s*', '-'), '\s+', ' '), ' -') AS MATCH_KEY
    FROM RAW_HOURLY
    GROUP BY FILE_ID, TRIM(LOCATION_NAME)
)
SELECT N.FILE_ID, N.RAW_NAME, N.N_ROWS,
       COALESCE(e.LOCATION_ID, k.LOCATION_ID)                                       AS LOCATION_ID,
       CASE WHEN e.LOCATION_ID IS NOT NULL THEN 'exact'
            WHEN k.LOCATION_ID IS NOT NULL THEN 'normalised'
            ELSE 'unknown' END                                                      AS MATCH_METHOD
FROM N
LEFT JOIN LOCATION e ON e.SOURCE_NAME = N.RAW_NAME
LEFT JOIN LOCATION k ON k.MATCH_KEY = N.MATCH_KEY AND k.MATCH_KEY_UNIQUE;

-- Parsed row header fields (NULL when unparseable) for every raw row.
CREATE OR REPLACE TABLE RAW_ROW_PARSED AS
WITH R AS (
    SELECT h.FILE_ID, h.LINE_NO, h.LOCATION_NAME, h.DATE_STR, h.HOUR_STR, TRIM(h.DATE_STR) AS D,
           f.DASH_FORMAT, f.SLASH_FORMAT
    FROM RAW_HOURLY h
    JOIN FILE_DATE_FORMAT f ON f.FILE_ID = h.FILE_ID
)
SELECT R.FILE_ID, R.LINE_NO, R.LOCATION_NAME, R.DATE_STR, R.HOUR_STR,
       l.LOCATION_ID,
       CASE WHEN sc.LOCATION_ID IS NULL OR dcl.EXCLUDE_REASON IS NOT NULL THEN FALSE ELSE TRUE END AS IN_SCOPE,
       CASE WHEN R.D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' AND R.SLASH_FORMAT IS NULL
            THEN TRUE ELSE FALSE END                                                           AS AMBIGUOUS_DATE,
       CAST(CASE
         WHEN R.D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' AND R.DASH_FORMAT = 'DD-MM-YYYY'
              AND IS_DATE(R.D, 'DD-MM-YYYY') THEN TO_DATE(R.D, 'DD-MM-YYYY')
         WHEN R.D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' AND R.DASH_FORMAT = 'MM-DD-YYYY'
              AND IS_DATE(R.D, 'MM-DD-YYYY') THEN TO_DATE(R.D, 'MM-DD-YYYY')
         WHEN R.D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' AND R.SLASH_FORMAT = 'MM/DD/YYYY'
              AND IS_DATE(R.D, 'MM/DD/YYYY') THEN TO_DATE(R.D, 'MM/DD/YYYY')
         WHEN R.D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' AND R.SLASH_FORMAT = 'DD/MM/YYYY'
              AND IS_DATE(R.D, 'DD/MM/YYYY') THEN TO_DATE(R.D, 'DD/MM/YYYY')
       END AS TIMESTAMP)                                                                       AS DAY_TS,
       CASE WHEN IS_NUMBER(TRIM(R.HOUR_STR)) THEN CAST(TRIM(R.HOUR_STR) AS DOUBLE) END        AS HOUR_NUM,
       dcl.PERIOD_FROM,
       dcl.PERIOD_TO
FROM R
LEFT JOIN NAME_MATCH nm ON nm.FILE_ID = R.FILE_ID AND nm.RAW_NAME = TRIM(R.LOCATION_NAME)
LEFT JOIN LOCATION l ON l.LOCATION_ID = nm.LOCATION_ID
LEFT JOIN LOCATION_IN_SCOPE sc ON sc.LOCATION_ID = l.LOCATION_ID
LEFT JOIN SOURCE_FILE_DECLARED dcl ON dcl.FILE_ID = R.FILE_ID;

-- Row-level problems: unknown location, unparseable or ambiguous date, bad hour, date outside the
-- file's declared period. Such rows produce no readings. Rows of out-of-scope locations and of excluded
-- files are not analysed and therefore not reported here (excluded files appear in QUALITY_FILE).
CREATE OR REPLACE TABLE ROW_QUARANTINE AS
SELECT p.FILE_ID, p.LINE_NO, p.LOCATION_NAME, p.DATE_STR, p.HOUR_STR,
       CASE
         WHEN p.LOCATION_ID IS NULL THEN 'unknown_location'
         WHEN p.AMBIGUOUS_DATE THEN 'ambiguous_date_format'
         WHEN p.DAY_TS IS NULL THEN 'bad_date'
         WHEN p.HOUR_NUM IS NULL OR p.HOUR_NUM NOT BETWEEN 0 AND 23 OR p.HOUR_NUM <> FLOOR(p.HOUR_NUM) THEN 'bad_hour'
         ELSE 'outside_declared_period'
       END AS REASON
FROM RAW_ROW_PARSED p
WHERE (p.LOCATION_ID IS NULL AND NOT EXISTS (SELECT 1 FROM SOURCE_FILE_DECLARED x
                                             WHERE x.FILE_ID = p.FILE_ID AND x.EXCLUDE_REASON IS NOT NULL)
       OR p.IN_SCOPE)
  AND (p.LOCATION_ID IS NULL OR p.DAY_TS IS NULL OR p.HOUR_NUM IS NULL
       OR p.HOUR_NUM NOT BETWEEN 0 AND 23 OR p.HOUR_NUM <> FLOOR(p.HOUR_NUM)
       OR (p.PERIOD_FROM IS NOT NULL AND CAST(p.DAY_TS AS DATE) < p.PERIOD_FROM)
       OR (p.PERIOD_TO IS NOT NULL AND CAST(p.DAY_TS AS DATE) > p.PERIOD_TO));

-- Minute grid of every valid in-scope row, with the raw cell text (still untouched) and its numeric parse.
CREATE OR REPLACE TABLE MINUTE_RAW AS
WITH MINUTES AS (
    SELECT CAST(LEVEL - 1 AS DECIMAL(2,0)) AS MI FROM DUAL CONNECT BY LEVEL <= 60
), ROWS_OK AS (
    SELECT p.LOCATION_ID, p.FILE_ID, p.LINE_NO, p.DAY_TS, CAST(p.HOUR_NUM AS DECIMAL(2,0)) AS HR
    FROM RAW_ROW_PARSED p
    WHERE p.IN_SCOPE AND p.DAY_TS IS NOT NULL AND p.HOUR_NUM BETWEEN 0 AND 23
      AND p.HOUR_NUM = FLOOR(p.HOUR_NUM)
      AND (p.PERIOD_FROM IS NULL OR CAST(p.DAY_TS AS DATE) >= p.PERIOD_FROM)
      AND (p.PERIOD_TO IS NULL OR CAST(p.DAY_TS AS DATE) <= p.PERIOD_TO)
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

-- One row per valid in-scope raw hour-row. Duplicate minutes can only come from repeated (location, hour)
-- rows, so step 040 checks R-3 over this small table (about 60x fewer rows than minutes) and compares
-- minutes only inside repeated hours.
CREATE OR REPLACE TABLE HOUR_ROW AS
SELECT LOCATION_ID,
       ADD_HOURS(DAY_TS, CAST(HOUR_NUM AS DECIMAL(2,0))) AS HOUR_TS,
       FILE_ID,
       LINE_NO
FROM RAW_ROW_PARSED
WHERE IN_SCOPE AND DAY_TS IS NOT NULL AND HOUR_NUM BETWEEN 0 AND 23 AND HOUR_NUM = FLOOR(HOUR_NUM)
  AND (PERIOD_FROM IS NULL OR CAST(DAY_TS AS DATE) >= PERIOD_FROM)
  AND (PERIOD_TO IS NULL OR CAST(DAY_TS AS DATE) <= PERIOD_TO);

DROP TABLE RAW_ROW_PARSED;
