-- 040_clean.sql
-- R-3 duplicates and conflicts, R-4 monitoring window.
-- A (location, minute) seen more than once with ONE distinct value is kept once (duplicates counted).
-- With several distinct values it is a conflict: no clean reading, so the minute becomes NO_DATA.

CREATE OR REPLACE TABLE READING_CLEAN AS
SELECT LOCATION_ID,
       TS,
       MIN(VOLTAGE)                                              AS VOLTAGE,
       COUNT(*) - 1                                              AS DUPLICATE_COUNT,
       COUNT(DISTINCT FILE_ID)                                   AS SOURCE_FILES,
       -- provenance: the first source occurrence (lowest file id, then lowest line number)
       CAST(FLOOR(MIN(FILE_ID * 1000000000000 + LINE_NO) / 1000000000000) AS DECIMAL(9,0))  AS FILE_ID,
       CAST(MOD(MIN(FILE_ID * 1000000000000 + LINE_NO), 1000000000000) AS DECIMAL(12,0))     AS LINE_NO
FROM MINUTE_READING
GROUP BY LOCATION_ID, TS
HAVING COUNT(DISTINCT VOLTAGE) = 1;

CREATE OR REPLACE TABLE READING_CONFLICT AS
SELECT LOCATION_ID,
       TS,
       COUNT(*)                 AS N_READINGS,
       COUNT(DISTINCT VOLTAGE)  AS N_DISTINCT,
       MIN(VOLTAGE)             AS MIN_VOLTAGE,
       MAX(VOLTAGE)             AS MAX_VOLTAGE,
       COUNT(DISTINCT FILE_ID)  AS SOURCE_FILES
FROM MINUTE_READING
GROUP BY LOCATION_ID, TS
HAVING COUNT(DISTINCT VOLTAGE) > 1;

-- R-4: first to last minute with a valid, unique reading.
CREATE OR REPLACE TABLE MONITOR_WINDOW AS
SELECT LOCATION_ID, MIN(TS) AS FIRST_TS, MAX(TS) AS LAST_TS
FROM READING_CLEAN
GROUP BY LOCATION_ID;
