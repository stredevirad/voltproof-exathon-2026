-- 020_location.sql
-- LOCATION: one row per monitored location from the ESMI location file (surrogate id, cleaned
-- display name, documented dates). The source name is kept verbatim for joins and provenance.

CREATE OR REPLACE TABLE LOCATION AS
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY TRIM(LOCATION_NAME)) AS DECIMAL(9,0))        AS LOCATION_ID,
    TRIM(LOCATION_NAME)                                                            AS SOURCE_NAME,
    TRIM(REPLACE(TRIM(LOCATION_NAME), '[Offline]', ''))                            AS DISPLAY_NAME,
    CASE WHEN INSTR(LOCATION_NAME, '[Offline]') > 0 THEN TRUE ELSE FALSE END       AS IS_OFFLINE,
    TRIM(DISTRICT)                                                                 AS DISTRICT,
    TRIM(STATE_NAME)                                                               AS STATE_NAME,
    TRIM(CATEGORY)                                                                 AS SOURCE_CATEGORY,
    TRIM(CONNECTION_TYPE)                                                          AS CONNECTION_TYPE,
    CASE WHEN IS_DATE(TRIM(FROM_DATE_STR), 'DD-MM-YYYY')
         THEN TO_DATE(TRIM(FROM_DATE_STR), 'DD-MM-YYYY') END                       AS DOC_FROM_DATE,
    CASE WHEN IS_DATE(TRIM(TO_DATE_STR), 'DD-MM-YYYY')
         THEN TO_DATE(TRIM(TO_DATE_STR), 'DD-MM-YYYY') END                         AS DOC_TO_DATE,
    FILE_ID                                                                        AS SOURCE_FILE_ID,
    LINE_NO                                                                        AS SOURCE_LINE_NO
FROM RAW_LOCATION;
