-- 020_location.sql
-- LOCATION: one row per monitored location from the ESMI location file (surrogate id, cleaned
-- display name, documented dates). The source name is kept verbatim for joins and provenance.

CREATE OR REPLACE TABLE LOCATION AS
WITH L AS (
    SELECT r.*,
           -- matching key (D-029): lower case, without the "[Offline]" status marker, single spaces, no spaces
           -- around hyphens. Readings files sometimes add "[Offline]" or extra spaces to the same location's name.
           TRIM(REGEXP_REPLACE(REGEXP_REPLACE(REPLACE(LOWER(TRIM(LOCATION_NAME)), '[offline]', ''),
                                              '\s*-\s*', '-'), '\s+', ' '), ' -')   AS MATCH_KEY
    FROM RAW_LOCATION r
)
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY TRIM(LOCATION_NAME)) AS DECIMAL(9,0))        AS LOCATION_ID,
    TRIM(LOCATION_NAME)                                                            AS SOURCE_NAME,
    MATCH_KEY,
    CASE WHEN COUNT(*) OVER (PARTITION BY MATCH_KEY) = 1 THEN TRUE ELSE FALSE END  AS MATCH_KEY_UNIQUE,
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
FROM L;
