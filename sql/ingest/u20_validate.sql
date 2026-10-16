-- u20_validate.sql (uploads only; never run on VOLTPROOF or VOLTPROOF_DEMO)
-- Plain counts about an uploaded file, computed in Exasol before anything is built, so the upload page can say
-- what would be set aside and why, ask about dates it cannot decide, and refuse files that are not 1-minute
-- voltage readings. Reads the staging tables (u10) and PARAMS (the user's confirmed choices, upload.*).
-- The canonical view UPLOAD_WIDE_CANON is also what u30 copies into RAW_HOURLY, so the summary and the build use
-- exactly the same date and hour rules.

-- Wide layout, one canonical row per staged row. Dates become DD-MM-YYYY using the order the data decides (or
-- the user confirmed when the data cannot decide: upload.dash_order and upload.slash_order, DMY or MDY).
-- dates that cannot be read keep their text, so step 030 sets them aside exactly as for any other file. Hours
-- 1-24 become 0-23 only when the user confirmed that hour 1 is the first hour of the day (upload.hour_base = 1).
-- In a semicolon-separated file the decimal mark is a comma (230,5): it becomes a point (upload.decimal_comma = 1).
CREATE OR REPLACE VIEW UPLOAD_WIDE_CANON AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'upload.dash_order' THEN STR_VALUE END)  AS DASH_ORDER,
           MAX(CASE WHEN NAME = 'upload.slash_order' THEN STR_VALUE END) AS SLASH_ORDER,
           MAX(CASE WHEN NAME = 'upload.hour_base' THEN NUM_VALUE END)   AS HOUR_BASE,
           MAX(CASE WHEN NAME = 'upload.decimal_comma' THEN NUM_VALUE END) AS DC
    FROM PARAMS
), W AS (
    SELECT w.FILE_ID, w.LINE_NO, w.LOCATION_NAME, w.DATE_STR AS RAW_DATE, w.HOUR_STR AS RAW_HOUR,
           TRIM(w.DATE_STR) AS D,
           CASE WHEN IS_NUMBER(TRIM(w.HOUR_STR)) THEN CAST(TRIM(w.HOUR_STR) AS DOUBLE) END AS HN,
           P.DASH_ORDER, P.SLASH_ORDER, P.HOUR_BASE, P.DC,
           w.M00, w.M01, w.M02, w.M03, w.M04, w.M05, w.M06, w.M07, w.M08, w.M09,
           w.M10, w.M11, w.M12, w.M13, w.M14, w.M15, w.M16, w.M17, w.M18, w.M19,
           w.M20, w.M21, w.M22, w.M23, w.M24, w.M25, w.M26, w.M27, w.M28, w.M29,
           w.M30, w.M31, w.M32, w.M33, w.M34, w.M35, w.M36, w.M37, w.M38, w.M39,
           w.M40, w.M41, w.M42, w.M43, w.M44, w.M45, w.M46, w.M47, w.M48, w.M49,
           w.M50, w.M51, w.M52, w.M53, w.M54, w.M55, w.M56, w.M57, w.M58, w.M59
    FROM UPLOAD_WIDE w CROSS JOIN P
)
SELECT FILE_ID, LINE_NO, LOCATION_NAME,
       CASE
         WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' AND DASH_ORDER = 'DMY' AND IS_DATE(D, 'DD-MM-YYYY')
              THEN TO_CHAR(TO_DATE(D, 'DD-MM-YYYY'), 'DD-MM-YYYY')
         WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' AND DASH_ORDER = 'MDY' AND IS_DATE(D, 'MM-DD-YYYY')
              THEN TO_CHAR(TO_DATE(D, 'MM-DD-YYYY'), 'DD-MM-YYYY')
         WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' AND SLASH_ORDER = 'DMY' AND IS_DATE(D, 'DD/MM/YYYY')
              THEN TO_CHAR(TO_DATE(D, 'DD/MM/YYYY'), 'DD-MM-YYYY')
         WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' AND SLASH_ORDER = 'MDY' AND IS_DATE(D, 'MM/DD/YYYY')
              THEN TO_CHAR(TO_DATE(D, 'MM/DD/YYYY'), 'DD-MM-YYYY')
         WHEN D REGEXP_LIKE '[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}' AND IS_DATE(D, 'YYYY-MM-DD')
              THEN TO_CHAR(TO_DATE(D, 'YYYY-MM-DD'), 'DD-MM-YYYY')
         ELSE RAW_DATE
       END                                                                                   AS DATE_STR,
       CASE WHEN HOUR_BASE = 1 AND HN BETWEEN 1 AND 24 AND HN = FLOOR(HN)
            THEN CAST(CAST(HN AS DECIMAL(2,0)) - 1 AS VARCHAR(2))
            ELSE RAW_HOUR END                                                                AS HOUR_STR,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M00, ',', '.') ELSE M00 END, 1, 40) AS M00,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M01, ',', '.') ELSE M01 END, 1, 40) AS M01,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M02, ',', '.') ELSE M02 END, 1, 40) AS M02,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M03, ',', '.') ELSE M03 END, 1, 40) AS M03,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M04, ',', '.') ELSE M04 END, 1, 40) AS M04,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M05, ',', '.') ELSE M05 END, 1, 40) AS M05,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M06, ',', '.') ELSE M06 END, 1, 40) AS M06,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M07, ',', '.') ELSE M07 END, 1, 40) AS M07,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M08, ',', '.') ELSE M08 END, 1, 40) AS M08,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M09, ',', '.') ELSE M09 END, 1, 40) AS M09,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M10, ',', '.') ELSE M10 END, 1, 40) AS M10,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M11, ',', '.') ELSE M11 END, 1, 40) AS M11,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M12, ',', '.') ELSE M12 END, 1, 40) AS M12,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M13, ',', '.') ELSE M13 END, 1, 40) AS M13,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M14, ',', '.') ELSE M14 END, 1, 40) AS M14,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M15, ',', '.') ELSE M15 END, 1, 40) AS M15,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M16, ',', '.') ELSE M16 END, 1, 40) AS M16,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M17, ',', '.') ELSE M17 END, 1, 40) AS M17,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M18, ',', '.') ELSE M18 END, 1, 40) AS M18,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M19, ',', '.') ELSE M19 END, 1, 40) AS M19,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M20, ',', '.') ELSE M20 END, 1, 40) AS M20,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M21, ',', '.') ELSE M21 END, 1, 40) AS M21,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M22, ',', '.') ELSE M22 END, 1, 40) AS M22,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M23, ',', '.') ELSE M23 END, 1, 40) AS M23,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M24, ',', '.') ELSE M24 END, 1, 40) AS M24,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M25, ',', '.') ELSE M25 END, 1, 40) AS M25,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M26, ',', '.') ELSE M26 END, 1, 40) AS M26,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M27, ',', '.') ELSE M27 END, 1, 40) AS M27,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M28, ',', '.') ELSE M28 END, 1, 40) AS M28,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M29, ',', '.') ELSE M29 END, 1, 40) AS M29,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M30, ',', '.') ELSE M30 END, 1, 40) AS M30,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M31, ',', '.') ELSE M31 END, 1, 40) AS M31,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M32, ',', '.') ELSE M32 END, 1, 40) AS M32,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M33, ',', '.') ELSE M33 END, 1, 40) AS M33,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M34, ',', '.') ELSE M34 END, 1, 40) AS M34,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M35, ',', '.') ELSE M35 END, 1, 40) AS M35,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M36, ',', '.') ELSE M36 END, 1, 40) AS M36,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M37, ',', '.') ELSE M37 END, 1, 40) AS M37,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M38, ',', '.') ELSE M38 END, 1, 40) AS M38,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M39, ',', '.') ELSE M39 END, 1, 40) AS M39,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M40, ',', '.') ELSE M40 END, 1, 40) AS M40,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M41, ',', '.') ELSE M41 END, 1, 40) AS M41,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M42, ',', '.') ELSE M42 END, 1, 40) AS M42,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M43, ',', '.') ELSE M43 END, 1, 40) AS M43,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M44, ',', '.') ELSE M44 END, 1, 40) AS M44,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M45, ',', '.') ELSE M45 END, 1, 40) AS M45,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M46, ',', '.') ELSE M46 END, 1, 40) AS M46,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M47, ',', '.') ELSE M47 END, 1, 40) AS M47,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M48, ',', '.') ELSE M48 END, 1, 40) AS M48,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M49, ',', '.') ELSE M49 END, 1, 40) AS M49,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M50, ',', '.') ELSE M50 END, 1, 40) AS M50,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M51, ',', '.') ELSE M51 END, 1, 40) AS M51,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M52, ',', '.') ELSE M52 END, 1, 40) AS M52,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M53, ',', '.') ELSE M53 END, 1, 40) AS M53,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M54, ',', '.') ELSE M54 END, 1, 40) AS M54,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M55, ',', '.') ELSE M55 END, 1, 40) AS M55,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M56, ',', '.') ELSE M56 END, 1, 40) AS M56,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M57, ',', '.') ELSE M57 END, 1, 40) AS M57,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M58, ',', '.') ELSE M58 END, 1, 40) AS M58,
       SUBSTR(CASE WHEN DC = 1 THEN REPLACE(M59, ',', '.') ELSE M59 END, 1, 40) AS M59
FROM W;

-- Wide layout counts: date shapes (per separator, as step 030 decides them), hours, names, date range.
CREATE OR REPLACE TABLE UPLOAD_WIDE_STATS AS
WITH W AS (
    SELECT TRIM(LOCATION_NAME) AS LOC, TRIM(DATE_STR) AS D,
           CASE WHEN IS_NUMBER(TRIM(HOUR_STR)) THEN CAST(TRIM(HOUR_STR) AS DOUBLE) END AS HN
    FROM UPLOAD_WIDE
), C AS (
    SELECT MIN(CASE WHEN IS_DATE(DATE_STR, 'DD-MM-YYYY') THEN TO_DATE(DATE_STR, 'DD-MM-YYYY') END) AS FIRST_DAY,
           MAX(CASE WHEN IS_DATE(DATE_STR, 'DD-MM-YYYY') THEN TO_DATE(DATE_STR, 'DD-MM-YYYY') END) AS LAST_DAY
    FROM UPLOAD_WIDE_CANON
    WHERE DATE_STR REGEXP_LIKE '[0-9]{2}-[0-9]{2}-[0-9]{4}'
)
SELECT COUNT(*)                                                                               AS N_ROWS,
       COUNT(DISTINCT LOC)                                                                    AS N_MONITORS,
       SUM(CASE WHEN LOC IS NULL THEN 1 ELSE 0 END)                                           AS N_NO_NAME,
       SUM(CASE WHEN LENGTH(LOC) > 300 THEN 1 ELSE 0 END)                                     AS N_LONG_NAME,
       SUM(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' THEN 1 ELSE 0 END)       AS N_DASH,
       MAX(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                THEN CAST(REGEXP_SUBSTR(D, '[0-9]+', 1, 1) AS DECIMAL(4,0)) END)              AS DASH_MAX1,
       MAX(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                THEN CAST(REGEXP_SUBSTR(D, '[0-9]+', 1, 2) AS DECIMAL(4,0)) END)              AS DASH_MAX2,
       MIN(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}' THEN D END)              AS DASH_EXAMPLE,
       SUM(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' THEN 1 ELSE 0 END)       AS N_SLASH,
       MAX(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                THEN CAST(REGEXP_SUBSTR(D, '[0-9]+', 1, 1) AS DECIMAL(4,0)) END)              AS SLASH_MAX1,
       MAX(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                THEN CAST(REGEXP_SUBSTR(D, '[0-9]+', 1, 2) AS DECIMAL(4,0)) END)              AS SLASH_MAX2,
       MIN(CASE WHEN D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}' THEN D END)              AS SLASH_EXAMPLE,
       SUM(CASE WHEN D REGEXP_LIKE '[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}' THEN 1 ELSE 0 END)       AS N_ISO,
       SUM(CASE WHEN D IS NULL OR NOT (D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                                       OR D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                                       OR D REGEXP_LIKE '[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}')
                THEN 1 ELSE 0 END)                                                            AS N_DATE_OTHER,
       MIN(CASE WHEN D IS NOT NULL AND NOT (D REGEXP_LIKE '[0-9]{1,2}-[0-9]{1,2}-[0-9]{4}'
                                            OR D REGEXP_LIKE '[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'
                                            OR D REGEXP_LIKE '[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}')
                THEN D END)                                                                   AS DATE_OTHER_EXAMPLE,
       SUM(CASE WHEN HN = 0 THEN 1 ELSE 0 END)                                                AS N_HOUR_0,
       SUM(CASE WHEN HN = 24 THEN 1 ELSE 0 END)                                               AS N_HOUR_24,
       SUM(CASE WHEN HN IS NULL OR HN < 0 OR HN > 24 OR HN <> FLOOR(HN) THEN 1 ELSE 0 END)    AS N_HOUR_BAD,
       MAX(C.FIRST_DAY)                                                                       AS FIRST_DAY,
       MAX(C.LAST_DAY)                                                                        AS LAST_DAY
FROM W CROSS JOIN C;

-- Long layout: timestamps parsed with the order the user picked (upload.long_order = 'YMD' | 'DMY' | 'MDY').
-- Accepted shape: a date with '-', '/' or '.', a space or 'T', then HH:MI or HH:MI:SS (an optional fraction is
-- allowed so that sub-minute data can be recognised and refused), with an optional AM/PM (12-hour clocks, as
-- spreadsheets write them) and an optional time-zone suffix. Clock times are read as local time. The suffix
-- +05:30 (India) is accepted and ignored; any other suffix (Z means UTC, +01:00, ...) is recognised and refused,
-- never converted. A comma used as the decimal mark (230,5, in files separated by semicolons) becomes a point
-- (upload.decimal_comma = 1).
CREATE OR REPLACE TABLE UPLOAD_LONG_PARSED AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'upload.long_order' THEN STR_VALUE END)          AS LONG_ORDER,
           MAX(CASE WHEN NAME = 'upload.single_monitor_name' THEN STR_VALUE END) AS SINGLE_NAME,
           MAX(CASE WHEN NAME = 'upload.decimal_comma' THEN NUM_VALUE END)       AS DC
    FROM PARAMS
), L AS (
    SELECT u.FILE_ID, u.LINE_NO, TRIM(COALESCE(u.LOCATION_NAME, P.SINGLE_NAME)) AS LOC,
           TRIM(u.TS_STR) AS S,
           CASE WHEN P.DC = 1 THEN REPLACE(TRIM(u.VALUE_STR), ',', '.') ELSE TRIM(u.VALUE_STR) END AS V,
           P.LONG_ORDER
    FROM UPLOAD_LONG u CROSS JOIN P
), N1 AS (
    SELECT L.*,
           CASE WHEN S REGEXP_LIKE '[0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4}[ T][0-9]{1,2}:[0-9]{2}(:[0-9]{2}(\.[0-9]+)?)?( ?[AaPp][Mm])?( ?(Z|[+-][0-9]{2}:?[0-9]{2}))?'
                THEN TRUE ELSE FALSE END                                                     AS SHAPE_OK,
           CASE WHEN S REGEXP_LIKE '.*[0-9]( ?(Z|[+-][0-9]{2}:?[0-9]{2}))' THEN TRUE ELSE FALSE END AS HAS_ZONE,
           CASE WHEN S REGEXP_LIKE '.*[0-9] ?\+05:?30' THEN TRUE ELSE FALSE END             AS IS_IST,
           CASE WHEN S REGEXP_LIKE '.*:[0-9]{2}:[0-9]{2}\.[0-9]*[1-9][0-9]*.*' THEN TRUE ELSE FALSE END AS HAS_FRACTION,
           UPPER(REGEXP_SUBSTR(S, '[AaPp][Mm]'))                                             AS AP,
           CAST(REGEXP_SUBSTR(REGEXP_SUBSTR(S, '[0-9]{1,2}:[0-9]{2}'), '^[0-9]+') AS DECIMAL(4,0)) AS HH,
           REGEXP_SUBSTR(S, '^[0-9]+[-/.][0-9]+[-/.][0-9]+')                                AS DATEPART,
           REGEXP_SUBSTR(S, '[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?')                              AS TIMEPART
    FROM L
), N AS (
    SELECT N1.*,
           HAS_ZONE AND NOT IS_IST                                                           AS HAS_OFFSET,
           CASE WHEN SHAPE_OK AND (AP IS NULL OR HH BETWEEN 1 AND 12)
                THEN REGEXP_REPLACE(DATEPART, '[/.]', '-') || ' '
                     || LPAD(CAST(CASE WHEN AP = 'PM' AND HH < 12 THEN HH + 12
                                       WHEN AP = 'AM' AND HH = 12 THEN 0 ELSE HH END AS VARCHAR(2)), 2, '0')
                     || ':' || REGEXP_SUBSTR(TIMEPART, '(?<=:)[0-9]{2}')
                     || ':' || CASE WHEN TIMEPART REGEXP_LIKE '[0-9]{1,2}:[0-9]{2}:[0-9]{2}'
                                    THEN REGEXP_SUBSTR(TIMEPART, '[0-9]{2}$') ELSE '00' END
           END                                                                               AS S3
    FROM N1
)
SELECT FILE_ID, LINE_NO, LOC, S AS TS_TEXT, V, HAS_OFFSET, HAS_FRACTION, IS_IST,
       CASE WHEN LONG_ORDER = 'YMD' AND IS_TIMESTAMP(S3, 'YYYY-MM-DD HH24:MI:SS')
                 THEN TO_TIMESTAMP(S3, 'YYYY-MM-DD HH24:MI:SS')
            WHEN LONG_ORDER = 'DMY' AND IS_TIMESTAMP(S3, 'DD-MM-YYYY HH24:MI:SS')
                 THEN TO_TIMESTAMP(S3, 'DD-MM-YYYY HH24:MI:SS')
            WHEN LONG_ORDER = 'MDY' AND IS_TIMESTAMP(S3, 'MM-DD-YYYY HH24:MI:SS')
                 THEN TO_TIMESTAMP(S3, 'MM-DD-YYYY HH24:MI:SS')
       END                                                                                   AS TS,
       CASE WHEN S3 IS NOT NULL THEN CAST(REGEXP_SUBSTR(S3, '[0-9]+', 1, 1) AS DECIMAL(4,0)) END AS PART1,
       CASE WHEN S3 IS NOT NULL THEN CAST(REGEXP_SUBSTR(S3, '[0-9]+', 1, 2) AS DECIMAL(4,0)) END AS PART2
FROM N;

-- Long layout counts: readable timestamps, offsets, readings more often than once a minute, repeated minutes,
-- the usual step between readings of one monitor, and the date range.
CREATE OR REPLACE TABLE UPLOAD_LONG_STATS AS
WITH G AS (
    SELECT LOC, TS, MINUTES_BETWEEN(TS, LAG(TS) OVER (PARTITION BY LOC ORDER BY TS)) AS GAP
    FROM UPLOAD_LONG_PARSED WHERE TS IS NOT NULL
), GM AS (
    SELECT GAP, COUNT(*) AS N FROM G WHERE GAP > 0 GROUP BY GAP
), DUP AS (
    SELECT LOC, TS, COUNT(*) AS N FROM UPLOAD_LONG_PARSED WHERE TS IS NOT NULL GROUP BY LOC, TS HAVING COUNT(*) > 1
)
SELECT (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED)                                              AS N_ROWS,
       (SELECT COUNT(DISTINCT LOC) FROM UPLOAD_LONG_PARSED)                                   AS N_MONITORS,
       (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED WHERE LOC IS NULL)                            AS N_NO_NAME,
       (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED WHERE LENGTH(LOC) > 300)                      AS N_LONG_NAME,
       (SELECT COUNT(TS) FROM UPLOAD_LONG_PARSED)                                             AS N_TS_OK,
       (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED WHERE HAS_OFFSET)                             AS N_OFFSET,
       (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED WHERE IS_IST)                                 AS N_IST_OFFSET,
       (SELECT MIN(TS_TEXT) FROM UPLOAD_LONG_PARSED WHERE HAS_OFFSET)                         AS OFFSET_EXAMPLE,
       (SELECT MIN(TS_TEXT) FROM UPLOAD_LONG_PARSED WHERE TS IS NULL AND NOT HAS_OFFSET)      AS TS_BAD_EXAMPLE,
       (SELECT MIN(TS_TEXT) FROM UPLOAD_LONG_PARSED WHERE TS IS NOT NULL)                     AS TS_EXAMPLE,
       (SELECT COUNT(*) FROM UPLOAD_LONG_PARSED
         WHERE HAS_FRACTION OR (TS IS NOT NULL AND SECOND(TS) <> 0))                         AS N_SUBMINUTE,
       (SELECT COALESCE(SUM(N - 1), 0) FROM DUP)                                              AS N_DUPLICATE,
       (SELECT COUNT(*) FROM G WHERE GAP > 0)                                                 AS N_GAPS,
       (SELECT COUNT(*) FROM G WHERE GAP = 1)                                                 AS N_GAP_1,
       (SELECT GAP FROM GM ORDER BY N DESC, GAP LIMIT 1)                                      AS USUAL_GAP,
       (SELECT MAX(PART1) FROM UPLOAD_LONG_PARSED)                                            AS PART1_MAX,
       (SELECT MAX(PART2) FROM UPLOAD_LONG_PARSED)                                            AS PART2_MAX,
       (SELECT CAST(MIN(TS) AS DATE) FROM UPLOAD_LONG_PARSED)                                 AS FIRST_DAY,
       (SELECT CAST(MAX(TS) AS DATE) FROM UPLOAD_LONG_PARSED)                                 AS LAST_DAY
FROM DUAL;

-- Reading values (both layouts): are they numbers, between 0 and 500 V, and is the typical reading that of a
-- 230 V supply? A file read at 110-120 V would otherwise show nearly every minute as "no supply" (<= 130 V).
-- The typical reading is the median of the readings above 130 V (the Prayas "no supply" limit): a home that is
-- without supply for much of the time, or a monitor that sags to a floor of about 100 V, still has a typical
-- supply voltage and must not be refused for its outages. Large files are sampled (every 7th line); the
-- counts are only used to accept, warn about or refuse the file.
CREATE OR REPLACE TABLE UPLOAD_VALUE_SAMPLE AS
WITH K AS (
    SELECT CASE WHEN (SELECT COUNT(*) FROM UPLOAD_WIDE) + (SELECT COUNT(*) FROM UPLOAD_LONG) > 200000
                THEN 7 ELSE 1 END AS STEP
    FROM DUAL
), MINUTES AS (
    SELECT CAST(LEVEL - 1 AS DECIMAL(2,0)) AS MI FROM DUAL CONNECT BY LEVEL <= 60
), WC AS (
    SELECT TRIM(w.LOCATION_NAME) AS LOC, TRIM(CASE m.MI
                WHEN 0 THEN w.M00 WHEN 1 THEN w.M01 WHEN 2 THEN w.M02 WHEN 3 THEN w.M03 WHEN 4 THEN w.M04
                WHEN 5 THEN w.M05 WHEN 6 THEN w.M06 WHEN 7 THEN w.M07 WHEN 8 THEN w.M08 WHEN 9 THEN w.M09
                WHEN 10 THEN w.M10 WHEN 11 THEN w.M11 WHEN 12 THEN w.M12 WHEN 13 THEN w.M13 WHEN 14 THEN w.M14
                WHEN 15 THEN w.M15 WHEN 16 THEN w.M16 WHEN 17 THEN w.M17 WHEN 18 THEN w.M18 WHEN 19 THEN w.M19
                WHEN 20 THEN w.M20 WHEN 21 THEN w.M21 WHEN 22 THEN w.M22 WHEN 23 THEN w.M23 WHEN 24 THEN w.M24
                WHEN 25 THEN w.M25 WHEN 26 THEN w.M26 WHEN 27 THEN w.M27 WHEN 28 THEN w.M28 WHEN 29 THEN w.M29
                WHEN 30 THEN w.M30 WHEN 31 THEN w.M31 WHEN 32 THEN w.M32 WHEN 33 THEN w.M33 WHEN 34 THEN w.M34
                WHEN 35 THEN w.M35 WHEN 36 THEN w.M36 WHEN 37 THEN w.M37 WHEN 38 THEN w.M38 WHEN 39 THEN w.M39
                WHEN 40 THEN w.M40 WHEN 41 THEN w.M41 WHEN 42 THEN w.M42 WHEN 43 THEN w.M43 WHEN 44 THEN w.M44
                WHEN 45 THEN w.M45 WHEN 46 THEN w.M46 WHEN 47 THEN w.M47 WHEN 48 THEN w.M48 WHEN 49 THEN w.M49
                WHEN 50 THEN w.M50 WHEN 51 THEN w.M51 WHEN 52 THEN w.M52 WHEN 53 THEN w.M53 WHEN 54 THEN w.M54
                WHEN 55 THEN w.M55 WHEN 56 THEN w.M56 WHEN 57 THEN w.M57 WHEN 58 THEN w.M58 WHEN 59 THEN w.M59
           END) AS V
    FROM UPLOAD_WIDE_CANON w CROSS JOIN MINUTES m CROSS JOIN K
    WHERE MOD(w.LINE_NO, K.STEP) = 0
), LC AS (
    SELECT p.LOC, p.V FROM UPLOAD_LONG_PARSED p CROSS JOIN K WHERE MOD(p.LINE_NO, K.STEP) = 0
)
SELECT LOC, V, CASE WHEN IS_NUMBER(V) THEN CAST(V AS DOUBLE) END AS VN
FROM (SELECT LOC, V FROM WC UNION ALL SELECT LOC, V FROM LC) A
WHERE V IS NOT NULL;

CREATE OR REPLACE TABLE UPLOAD_VALUE_STATS AS
SELECT COUNT(*)                                                 AS N_VALUES,
       COUNT(VN)                                                AS N_NUMERIC,
       SUM(CASE WHEN VN BETWEEN 0 AND 500 THEN 1 ELSE 0 END)    AS N_0_500,
       SUM(CASE WHEN VN > 130 THEN 1 ELSE 0 END)                AS N_ABOVE_130,
       SUM(CASE WHEN VN > 500 THEN 1 ELSE 0 END)                AS N_ABOVE_500,
       SUM(CASE WHEN VN = 0 THEN 1 ELSE 0 END)                  AS N_ZERO,
       MEDIAN(CASE WHEN VN > 130 THEN VN END)                   AS MEDIAN_ABOVE_130,
       MIN(VN)                                                  AS MIN_VALUE,
       MAX(VN)                                                  AS MAX_VALUE
FROM UPLOAD_VALUE_SAMPLE;

-- The same for each monitor, to warn about one recorder that is far from a 230 V supply among many that are not.
CREATE OR REPLACE TABLE UPLOAD_MONITOR_VALUES AS
SELECT LOC, COUNT(VN) AS N_NUMERIC, SUM(CASE WHEN VN > 130 THEN 1 ELSE 0 END) AS N_ABOVE_130,
       MEDIAN(CASE WHEN VN > 130 THEN VN END) AS MEDIAN_ABOVE_130
FROM UPLOAD_VALUE_SAMPLE
GROUP BY LOC;

-- One row per monitor named in the readings, and whether district and state are known for it: from the location
-- file (matched as in step 030: exact name, else the normalised name if it identifies one location) or typed on
-- the upload page.
CREATE OR REPLACE TABLE UPLOAD_MONITOR AS
WITH M AS (
    SELECT TRIM(LOCATION_NAME) AS LOC, COUNT(*) AS N_ROWS FROM UPLOAD_WIDE GROUP BY TRIM(LOCATION_NAME)
    UNION ALL
    SELECT LOC, COUNT(*) FROM UPLOAD_LONG_PARSED GROUP BY LOC
), L AS (
    SELECT TRIM(LOCATION_NAME) AS NAME, TRIM(DISTRICT) AS DISTRICT, TRIM(STATE_NAME) AS STATE_NAME FROM RAW_LOCATION
    UNION ALL
    SELECT TRIM(LOCATION_NAME), TRIM(DISTRICT), TRIM(STATE_NAME) FROM UPLOAD_LOCATION_INPUT
), LK AS (
    SELECT L.*,
           TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(NAME), '[offline]', ''), '\s*-\s*', '-'), '\s+', ' '),
                ' -') AS MATCH_KEY
    FROM L
), LU AS (
    SELECT LK.*, COUNT(*) OVER (PARTITION BY MATCH_KEY) AS KEY_COUNT FROM LK
), MK AS (
    SELECT M.*,
           TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(LOC), '[offline]', ''), '\s*-\s*', '-'), '\s+', ' '),
                ' -') AS MATCH_KEY
    FROM M
)
SELECT MK.LOC AS LOCATION_NAME, MK.N_ROWS,
       COALESCE(e.DISTRICT, k.DISTRICT)   AS DISTRICT,
       COALESCE(e.STATE_NAME, k.STATE_NAME) AS STATE_NAME,
       CASE WHEN e.NAME IS NOT NULL OR k.NAME IS NOT NULL THEN TRUE ELSE FALSE END AS HAS_LOCATION
FROM MK
LEFT JOIN (SELECT NAME, MAX(DISTRICT) AS DISTRICT, MAX(STATE_NAME) AS STATE_NAME FROM L GROUP BY NAME) e
       ON e.NAME = MK.LOC
LEFT JOIN (SELECT MATCH_KEY, MAX(NAME) AS NAME, MAX(DISTRICT) AS DISTRICT, MAX(STATE_NAME) AS STATE_NAME
           FROM LU WHERE KEY_COUNT = 1 GROUP BY MATCH_KEY) k
       ON k.MATCH_KEY = MK.MATCH_KEY AND e.NAME IS NULL;
