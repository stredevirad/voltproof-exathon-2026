-- 010_raw_tables.sql
-- Raw layer: files exactly as delivered, loaded as text (no parsing yet), plus provenance tables.
-- Runs inside the target schema (the runner issues OPEN SCHEMA first).

CREATE TABLE IF NOT EXISTS SOURCE_FILE (
    FILE_ID        DECIMAL(9,0)   NOT NULL,
    FILE_NAME      VARCHAR(300)   NOT NULL,
    FILE_KIND      VARCHAR(20)    NOT NULL,      -- 'locations' | 'readings'
    BYTES          DECIMAL(18,0),
    MD5            CHAR(32),
    SHA256         CHAR(64),
    ROWS_EXPECTED  DECIMAL(18,0),               -- data rows (excluding header) counted before import
    ROWS_LOADED    DECIMAL(18,0),
    LOADED_AT      TIMESTAMP,
    LOAD_SECONDS   DECIMAL(12,3),
    PRIMARY KEY (FILE_ID) DISABLE
);

-- One row per source line of an ESMI readings file. LINE_NO is the physical line number in the file
-- (header = line 1), so every minute value can be traced back to file + line + column.
CREATE TABLE IF NOT EXISTS RAW_HOURLY (
    FILE_ID        DECIMAL(9,0)   NOT NULL,
    LINE_NO        DECIMAL(12,0)  NOT NULL,
    LOCATION_NAME  VARCHAR(300),
    DATE_STR       VARCHAR(40),
    HOUR_STR       VARCHAR(40),
    M00 VARCHAR(40), M01 VARCHAR(40), M02 VARCHAR(40), M03 VARCHAR(40), M04 VARCHAR(40),
    M05 VARCHAR(40), M06 VARCHAR(40), M07 VARCHAR(40), M08 VARCHAR(40), M09 VARCHAR(40),
    M10 VARCHAR(40), M11 VARCHAR(40), M12 VARCHAR(40), M13 VARCHAR(40), M14 VARCHAR(40),
    M15 VARCHAR(40), M16 VARCHAR(40), M17 VARCHAR(40), M18 VARCHAR(40), M19 VARCHAR(40),
    M20 VARCHAR(40), M21 VARCHAR(40), M22 VARCHAR(40), M23 VARCHAR(40), M24 VARCHAR(40),
    M25 VARCHAR(40), M26 VARCHAR(40), M27 VARCHAR(40), M28 VARCHAR(40), M29 VARCHAR(40),
    M30 VARCHAR(40), M31 VARCHAR(40), M32 VARCHAR(40), M33 VARCHAR(40), M34 VARCHAR(40),
    M35 VARCHAR(40), M36 VARCHAR(40), M37 VARCHAR(40), M38 VARCHAR(40), M39 VARCHAR(40),
    M40 VARCHAR(40), M41 VARCHAR(40), M42 VARCHAR(40), M43 VARCHAR(40), M44 VARCHAR(40),
    M45 VARCHAR(40), M46 VARCHAR(40), M47 VARCHAR(40), M48 VARCHAR(40), M49 VARCHAR(40),
    M50 VARCHAR(40), M51 VARCHAR(40), M52 VARCHAR(40), M53 VARCHAR(40), M54 VARCHAR(40),
    M55 VARCHAR(40), M56 VARCHAR(40), M57 VARCHAR(40), M58 VARCHAR(40), M59 VARCHAR(40)
);

CREATE TABLE IF NOT EXISTS RAW_LOCATION (
    FILE_ID          DECIMAL(9,0)  NOT NULL,
    LINE_NO          DECIMAL(12,0) NOT NULL,
    LOCATION_NAME    VARCHAR(300),
    FROM_DATE_STR    VARCHAR(40),
    TO_DATE_STR      VARCHAR(40),
    DISTRICT         VARCHAR(200),
    STATE_NAME       VARCHAR(200),             -- STATE is a reserved word in Exasol
    CATEGORY         VARCHAR(200),
    CONNECTION_TYPE  VARCHAR(200)
);

-- Declared coverage of each source file (config/source_files.yaml; empty for synthetic fixtures unless
-- a fixture declares one) and files excluded from the analysis with a documented reason.
CREATE TABLE IF NOT EXISTS SOURCE_FILE_DECLARED (
    FILE_ID         DECIMAL(9,0)  NOT NULL,
    PERIOD_FROM     DATE,
    PERIOD_TO       DATE,
    EXCLUDE_REASON  VARCHAR(2000),
    PRIMARY KEY (FILE_ID) DISABLE
);

-- Method parameters, loaded from config/method.yaml by the runner before each pipeline run.
CREATE TABLE IF NOT EXISTS PARAMS (
    NAME       VARCHAR(200)  NOT NULL,
    NUM_VALUE  DOUBLE,
    STR_VALUE  VARCHAR(2000),
    PRIMARY KEY (NAME) DISABLE
);

-- Provenance backbone: one row per executed SQL statement of the pipeline.
CREATE TABLE IF NOT EXISTS RUN_LOG (
    RUN_ID              VARCHAR(40)   NOT NULL,
    STEP                VARCHAR(200)  NOT NULL,
    STMT_INDEX          DECIMAL(6,0)  NOT NULL,
    SQL_FILE_SHA256     CHAR(64),
    STMT_SHA256         CHAR(64),
    PARAMS_SHA256       CHAR(64),
    STARTED_AT          TIMESTAMP,
    FINISHED_AT         TIMESTAMP,
    WALL_SECONDS        DECIMAL(12,3),
    ROWS_AFFECTED       DECIMAL(18,0),
    EXA_SESSION_ID      DECIMAL(20,0),
    EXA_STMT_ID         DECIMAL(9,0),
    APP_GIT_COMMIT      VARCHAR(40),
    DATA_MANIFEST_SHA256 CHAR(64)
);
