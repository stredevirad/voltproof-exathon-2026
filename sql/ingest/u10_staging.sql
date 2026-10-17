-- u10_staging.sql (uploads only; never run on VOLTPROOF or VOLTPROOF_DEMO)
-- Staging tables for an uploaded file, inside the upload's own schema VP_USER_<id>. Every line of the file is
-- kept as delivered (text only, no parsing), with its file id and physical line number, so each reading can be
-- traced back to the user's file. u30_canonical.sql turns these rows into the standard raw tables (RAW_HOURLY,
-- RAW_LOCATION); the analytical steps 020-100 then run unchanged.

-- ESMI wide layout: Location name, Date, Hour, Min 0 ... Min 59 (same columns as RAW_HOURLY, wider text).
CREATE TABLE IF NOT EXISTS UPLOAD_WIDE (
    FILE_ID        DECIMAL(9,0)   NOT NULL,
    LINE_NO        DECIMAL(12,0)  NOT NULL,
    LOCATION_NAME  VARCHAR(2000),
    DATE_STR       VARCHAR(2000),
    HOUR_STR       VARCHAR(2000),
    M00 VARCHAR(2000), M01 VARCHAR(2000), M02 VARCHAR(2000), M03 VARCHAR(2000), M04 VARCHAR(2000),
    M05 VARCHAR(2000), M06 VARCHAR(2000), M07 VARCHAR(2000), M08 VARCHAR(2000), M09 VARCHAR(2000),
    M10 VARCHAR(2000), M11 VARCHAR(2000), M12 VARCHAR(2000), M13 VARCHAR(2000), M14 VARCHAR(2000),
    M15 VARCHAR(2000), M16 VARCHAR(2000), M17 VARCHAR(2000), M18 VARCHAR(2000), M19 VARCHAR(2000),
    M20 VARCHAR(2000), M21 VARCHAR(2000), M22 VARCHAR(2000), M23 VARCHAR(2000), M24 VARCHAR(2000),
    M25 VARCHAR(2000), M26 VARCHAR(2000), M27 VARCHAR(2000), M28 VARCHAR(2000), M29 VARCHAR(2000),
    M30 VARCHAR(2000), M31 VARCHAR(2000), M32 VARCHAR(2000), M33 VARCHAR(2000), M34 VARCHAR(2000),
    M35 VARCHAR(2000), M36 VARCHAR(2000), M37 VARCHAR(2000), M38 VARCHAR(2000), M39 VARCHAR(2000),
    M40 VARCHAR(2000), M41 VARCHAR(2000), M42 VARCHAR(2000), M43 VARCHAR(2000), M44 VARCHAR(2000),
    M45 VARCHAR(2000), M46 VARCHAR(2000), M47 VARCHAR(2000), M48 VARCHAR(2000), M49 VARCHAR(2000),
    M50 VARCHAR(2000), M51 VARCHAR(2000), M52 VARCHAR(2000), M53 VARCHAR(2000), M54 VARCHAR(2000),
    M55 VARCHAR(2000), M56 VARCHAR(2000), M57 VARCHAR(2000), M58 VARCHAR(2000), M59 VARCHAR(2000)
);

-- Long layout: one reading per line. Only the three columns the user picked are imported; LOCATION_NAME is empty
-- when the file holds one monitor (its name is then the upload parameter upload.single_monitor_name).
CREATE TABLE IF NOT EXISTS UPLOAD_LONG (
    FILE_ID        DECIMAL(9,0)   NOT NULL,
    LINE_NO        DECIMAL(12,0)  NOT NULL,
    LOCATION_NAME  VARCHAR(2000),
    TS_STR         VARCHAR(2000),
    VALUE_STR      VARCHAR(2000)
);

-- District and state typed for each monitor on the upload page (when no location file is supplied).
CREATE TABLE IF NOT EXISTS UPLOAD_LOCATION_INPUT (
    LINE_NO        DECIMAL(12,0)  NOT NULL,
    LOCATION_NAME  VARCHAR(2000),
    DISTRICT       VARCHAR(2000),
    STATE_NAME     VARCHAR(2000)
);
