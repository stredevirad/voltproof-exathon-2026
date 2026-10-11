-- 040_clean.sql
-- R-3 duplicates and conflicts, R-4 monitoring window.
-- A (location, minute) seen more than once with ONE distinct value is kept once (duplicates counted).
-- With several distinct values it is a conflict: no clean reading, so the minute becomes NO_DATA.
--
-- Scale note (D-028): a repeated minute can only come from a repeated (location, hour) raw row, because each
-- raw row covers the 60 minutes of one hour. So repeats are found on HOUR_ROW (~60x smaller). Minutes of
-- non-repeated hours pass straight through, and only repeated hours are grouped per minute. Same R-3
-- semantics as grouping all minutes (checked by fixtures F08 and the oracle), without a 90M-group
-- aggregation that spilled to disk on the full UP load.

CREATE OR REPLACE TABLE REPEATED_HOUR AS
SELECT LOCATION_ID, HOUR_TS, COUNT(*) AS N_ROWS, COUNT(DISTINCT FILE_ID) AS N_FILES
FROM HOUR_ROW
GROUP BY LOCATION_ID, HOUR_TS
HAVING COUNT(*) > 1;

-- minutes that belong to repeated hours (small): grouped per minute
CREATE OR REPLACE TABLE REPEATED_MINUTE AS
SELECT r.LOCATION_ID,
       r.TS,
       COUNT(*)                                                   AS N_READINGS,
       COUNT(DISTINCT r.VOLTAGE)                                  AS N_DISTINCT,
       MIN(r.VOLTAGE)                                             AS MIN_VOLTAGE,
       MAX(r.VOLTAGE)                                             AS MAX_VOLTAGE,
       COUNT(DISTINCT r.FILE_ID)                                  AS SOURCE_FILES,
       MIN(r.FILE_ID * 1000000000000 + r.LINE_NO)                 AS FIRST_SOURCE
FROM MINUTE_READING r
JOIN REPEATED_HOUR h ON h.LOCATION_ID = r.LOCATION_ID AND h.HOUR_TS = ADD_MINUTES(r.TS, -r.MINUTE_IDX)
GROUP BY r.LOCATION_ID, r.TS;

CREATE OR REPLACE TABLE READING_CLEAN AS
SELECT r.LOCATION_ID, r.TS, r.VOLTAGE,
       CAST(0 AS DECIMAL(18,0)) AS DUPLICATE_COUNT,
       CAST(1 AS DECIMAL(18,0)) AS SOURCE_FILES,
       r.FILE_ID, r.LINE_NO
FROM MINUTE_READING r
WHERE NOT EXISTS (SELECT 1 FROM REPEATED_HOUR h
                  WHERE h.LOCATION_ID = r.LOCATION_ID AND h.HOUR_TS = ADD_MINUTES(r.TS, -r.MINUTE_IDX))
UNION ALL
SELECT LOCATION_ID, TS, MIN_VOLTAGE,
       CAST(N_READINGS - 1 AS DECIMAL(18,0)),
       CAST(SOURCE_FILES AS DECIMAL(18,0)),
       CAST(FLOOR(FIRST_SOURCE / 1000000000000) AS DECIMAL(9,0)),
       CAST(MOD(FIRST_SOURCE, 1000000000000) AS DECIMAL(12,0))
FROM REPEATED_MINUTE
WHERE N_DISTINCT = 1;

CREATE OR REPLACE TABLE READING_CONFLICT AS
SELECT LOCATION_ID, TS, N_READINGS, N_DISTINCT, MIN_VOLTAGE, MAX_VOLTAGE, SOURCE_FILES
FROM REPEATED_MINUTE
WHERE N_DISTINCT > 1;

-- R-4: first to last minute with a valid, unique reading.
CREATE OR REPLACE TABLE MONITOR_WINDOW AS
SELECT LOCATION_ID, MIN(TS) AS FIRST_TS, MAX(TS) AS LAST_TS
FROM READING_CLEAN
GROUP BY LOCATION_ID;
