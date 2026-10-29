-- Ask VoltProof: documented, read-only views for a database user that may only read results (pipeline/ask.py).
-- {{SOURCE}} is the analysed schema (VOLTPROOF for the Prayas data), {{ASK}} the schema that holds only these views,
-- {{ATTRIBUTION}} the data attribution for that schema. The views run with their owner's rights, so the reader
-- needs SELECT on {{ASK}} only and never sees a table. Exasol takes comments on views and view columns only in
-- CREATE VIEW, so they are written inline. Nothing here changes a result: every view selects existing columns.

CREATE OR REPLACE VIEW {{ASK}}.ABOUT_THIS_DATA (
    TOPIC COMMENT IS 'What the note is about',
    NOTE COMMENT IS 'How to read the results; quote these rules when describing them'
) AS
SELECT 'source', '{{ATTRIBUTION}}' FROM DUAL
UNION ALL SELECT 'missing data', 'Missing readings are never counted as an outage. Durations next to a gap are bounds: MIN_DURATION and OUTAGE_MIN_LOWER are lower bounds; the headline is the lower bound.' FROM DUAL
UNION ALL SELECT 'voltage classes', 'Prayas classes: outage (no supply) at or below 130 V; low 131-204 V; normal 205-270 V; high at or above 271 V.' FROM DUAL
UNION ALL SELECT 'comparable month', 'A month is comparable when more than 90 percent of its minutes were read (Prayas Uttar Pradesh method). Compare only comparable months.' FROM DUAL
UNION ALL SELECT '2019', 'January-June 2019 outage figures are lower bounds (most all-0 V hours are missing from that file); July-December 2019 is excluded. Headline figures use 2016-2018.' FROM DUAL
UNION ALL SELECT 'shared events', 'A potential shared supply event is two or more monitors in one district whose interruptions started within 2 minutes of each other and overlapped. Coincidence is not cause: it names no fault and no common cause.' FROM DUAL
UNION ALL SELECT 'claims', 'VoltProof states what the monitors recorded. It does not determine a cause, a breach of any standard, or any remedy; a record may warrant review through the consumer grievance process.' FROM DUAL
UNION ALL SELECT 'time', 'Timestamps are India Standard Time wall-clock minutes as recorded by each monitor.' FROM DUAL
COMMENT IS 'Read first: source, attribution and the rules for reading every other view in this schema';

CREATE OR REPLACE VIEW {{ASK}}.LOCATION_MONTH (
    LOCATION_ID COMMENT IS 'Monitor id',
    MONITOR COMMENT IS 'Monitor name as published',
    DISTRICT COMMENT IS 'District (administrative; no coordinates exist in the source)',
    STATE_NAME COMMENT IS 'State',
    CATEGORY COMMENT IS 'Category as published (e.g. Rural, Megacity)',
    MONTH_KEY COMMENT IS 'Month, YYYY-MM',
    IS_COMPARABLE COMMENT IS 'TRUE when more than 90 percent of the month was read; compare only these months',
    COVERAGE_WINDOW COMMENT IS 'Share of the monitored minutes that have a reading (0-1)',
    OUTAGE_MIN_LOWER COMMENT IS 'Outage minutes, lower bound (measured minutes only)',
    OUTAGE_MIN_UPPER COMMENT IS 'Outage minutes, upper bound (if every unobserved minute next to an outage were an outage)',
    EVENING_OUTAGE_LOWER COMMENT IS 'Outage minutes between 17:00 and 23:00, lower bound',
    INTERRUPTIONS COMMENT IS 'Number of interruptions (outage events at least as long as the threshold)',
    LONGEST_INTERRUPTION COMMENT IS 'Longest interruption in minutes (lower bound)',
    LOW_MINUTES COMMENT IS 'Minutes with low voltage (131-204 V)',
    HIGH_MINUTES COMMENT IS 'Minutes with high voltage (271 V and above)',
    OBSERVED_MINUTES COMMENT IS 'Minutes with a reading',
    EXPECTED_MINUTES COMMENT IS 'Minutes in the monitoring window of this month'
) AS
SELECT m.LOCATION_ID, l.DISPLAY_NAME, l.DISTRICT, l.STATE_NAME, l.SOURCE_CATEGORY, m.MONTH_KEY, m.IS_COMPARABLE,
       m.COVERAGE_WINDOW, m.OUTAGE_MIN_LOWER, m.OUTAGE_MIN_UPPER, m.EVENING_OUTAGE_LOWER, m.INTERRUPTIONS,
       m.LONGEST_INTERRUPTION, m.LOW_MINUTES, m.HIGH_MINUTES, m.OBSERVED_MINUTES, m.EXPECTED_MINUTES
FROM {{SOURCE}}.MONTHLY m JOIN {{SOURCE}}.LOCATION l ON l.LOCATION_ID = m.LOCATION_ID
COMMENT IS 'One row per monitor and month: outage minutes as lower and upper bounds, interruptions, coverage';

CREATE OR REPLACE VIEW {{ASK}}.OUTAGE_EVENT (
    EVENT_KEY COMMENT IS 'Event id as shown in the app and reports',
    LOCATION_ID COMMENT IS 'Monitor id',
    MONITOR COMMENT IS 'Monitor name as published',
    DISTRICT COMMENT IS 'District',
    START_TS COMMENT IS 'First outage minute (measured), India Standard Time',
    END_TS COMMENT IS 'Last outage minute (measured), India Standard Time',
    MIN_DURATION COMMENT IS 'Duration in minutes, lower bound (measured)',
    MAX_DURATION COMMENT IS 'Possible duration in minutes, upper bound (when a gap borders the event)',
    START_CERTAINTY COMMENT IS 'exact, bounded (a gap borders the start) or censored (at the edge of the data)',
    END_CERTAINTY COMMENT IS 'exact, bounded or censored, as for the start',
    IS_INTERRUPTION COMMENT IS 'TRUE when the event is long enough to count as an interruption',
    ZERO_MINUTES COMMENT IS 'Minutes reading exactly 0 V'
) AS
SELECT e.EVENT_KEY, e.LOCATION_ID, l.DISPLAY_NAME, l.DISTRICT, e.START_TS, e.END_TS, e.MIN_DURATION, e.MAX_DURATION,
       e.START_CERTAINTY, e.END_CERTAINTY, e.IS_INTERRUPTION, e.ZERO_MINUTES
FROM {{SOURCE}}.EVENT e JOIN {{SOURCE}}.LOCATION l ON l.LOCATION_ID = e.LOCATION_ID
COMMENT IS 'One row per outage event (consecutive minutes at or below 130 V); missing minutes are never counted';

CREATE OR REPLACE VIEW {{ASK}}.POTENTIAL_SHARED_SUPPLY_EVENT (
    GROUP_KEY COMMENT IS 'Group id as shown in the app',
    DISTRICT COMMENT IS 'District (the grouping is administrative, not geographic)',
    START_TS COMMENT IS 'Earliest start of the grouped interruptions, India Standard Time',
    END_TS COMMENT IS 'Latest end of the grouped interruptions, India Standard Time',
    N_LOCATIONS COMMENT IS 'Number of monitors that lost supply within 2 minutes of each other',
    N_PAIRS COMMENT IS 'Number of coincident pairs in the group',
    MONITORS COMMENT IS 'Monitor names in the group, comma-separated'
) AS
SELECT g.GROUP_KEY, g.DISTRICT, g.START_TS, g.END_TS, g.N_LOCATIONS, g.N_PAIRS, mm.MONITORS
FROM {{SOURCE}}.POTENTIAL_SHARED_EVENT g
LEFT JOIN (SELECT m.GROUP_ID, GROUP_CONCAT(DISTINCT l.DISPLAY_NAME ORDER BY l.DISPLAY_NAME SEPARATOR ', ') AS MONITORS
           FROM {{SOURCE}}.POTENTIAL_SHARED_MEMBER m JOIN {{SOURCE}}.LOCATION l ON l.LOCATION_ID = m.LOCATION_ID
           GROUP BY m.GROUP_ID) mm ON mm.GROUP_ID = g.GROUP_ID
COMMENT IS 'Potential shared supply events: interruptions at two or more monitors of a district starting within 2 minutes; coincidence is not cause';

CREATE OR REPLACE VIEW {{ASK}}.DAILY_OUTAGE (
    LOCATION_ID COMMENT IS 'Monitor id',
    MONITOR COMMENT IS 'Monitor name as published',
    DISTRICT COMMENT IS 'District',
    CAL_DAY COMMENT IS 'Calendar day (India Standard Time)',
    OUTAGE_MIN_LOWER COMMENT IS 'Outage minutes that day, lower bound',
    OUTAGE_MIN_UPPER COMMENT IS 'Outage minutes that day, upper bound',
    EVENING_OUTAGE_LOWER COMMENT IS 'Outage minutes between 17:00 and 23:00, lower bound',
    INTERRUPTIONS COMMENT IS 'Interruptions starting that day',
    LONGEST_INTERRUPTION COMMENT IS 'Longest interruption that day in minutes (lower bound)',
    OBSERVED_MINUTES COMMENT IS 'Minutes with a reading',
    EXPECTED_MINUTES COMMENT IS 'Minutes in the monitoring window that day'
) AS
SELECT d.LOCATION_ID, l.DISPLAY_NAME, l.DISTRICT, d.CAL_DAY, d.OUTAGE_MIN_LOWER, d.OUTAGE_MIN_UPPER,
       d.EVENING_OUTAGE_LOWER, d.INTERRUPTIONS, d.LONGEST_INTERRUPTION, d.OBSERVED_MINUTES, d.EXPECTED_MINUTES
FROM {{SOURCE}}.DAILY d JOIN {{SOURCE}}.LOCATION l ON l.LOCATION_ID = d.LOCATION_ID
COMMENT IS 'One row per monitor and calendar day in its monitoring window: outage minutes as lower and upper bounds';

CREATE OR REPLACE VIEW {{ASK}}.DATA_QUALITY (
    LOCATION_ID COMMENT IS 'Monitor id',
    MONITOR COMMENT IS 'Monitor name as published',
    DISTRICT COMMENT IS 'District',
    CATEGORY COMMENT IS 'Category as published',
    FIRST_TS COMMENT IS 'First reading',
    LAST_TS COMMENT IS 'Last reading',
    COVERAGE_WINDOW COMMENT IS 'Share of the monitoring window with a reading (0-1)',
    GAP_COUNT COMMENT IS 'Number of gaps (runs of missing minutes)',
    GAP_MINUTES COMMENT IS 'Missing minutes in the window (never counted as outage)',
    LONGEST_GAP_MINUTES COMMENT IS 'Longest gap in minutes',
    DUPLICATE_READINGS COMMENT IS 'Repeated readings removed',
    CONFLICT_MINUTES COMMENT IS 'Minutes with conflicting readings',
    QUARANTINED_VALUES COMMENT IS 'Values set aside with a reason code',
    MONTHS_IN_WINDOW COMMENT IS 'Months in the monitoring window',
    COMPARABLE_MONTHS COMMENT IS 'Months with more than 90 percent coverage'
) AS
SELECT LOCATION_ID, DISPLAY_NAME, DISTRICT, SOURCE_CATEGORY, FIRST_TS, LAST_TS, COVERAGE_WINDOW, GAP_COUNT,
       GAP_MINUTES, LONGEST_GAP_MINUTES, DUPLICATE_READINGS, CONFLICT_MINUTES, QUARANTINED_VALUES, MONTHS_IN_WINDOW,
       COMPARABLE_MONTHS
FROM {{SOURCE}}.QUALITY_LOCATION
COMMENT IS 'Data quality per monitor: coverage, gaps, duplicates, conflicts and quarantined values';

CREATE OR REPLACE VIEW {{ASK}}.PROVENANCE (
    STEP COMMENT IS 'SQL file in sql/ that produced the results',
    STMT_INDEX COMMENT IS 'Statement number within the file',
    SQL_FILE_SHA256 COMMENT IS 'SHA-256 of the SQL file',
    STMT_SHA256 COMMENT IS 'SHA-256 of the exact statement text sent to Exasol',
    EXA_SESSION_ID COMMENT IS 'Exasol session id; with EXA_STMT_ID it finds the statement in the audit log',
    EXA_STMT_ID COMMENT IS 'Exasol statement id',
    FINISHED_AT COMMENT IS 'When the statement finished',
    EXA_DURATION_S COMMENT IS 'Duration in seconds, measured by Exasol (audit log DURATION)',
    EXA_TEMP_DB_RAM_PEAK_MIB COMMENT IS 'Temporary memory peak in MiB, measured by Exasol (audit log TEMP_DB_RAM_PEAK)'
) AS
SELECT r.STEP, r.STMT_INDEX, r.SQL_FILE_SHA256, r.STMT_SHA256, r.EXA_SESSION_ID, r.EXA_STMT_ID, r.FINISHED_AT,
       s.EXA_DURATION_S, s.EXA_TEMP_DB_RAM_PEAK_MIB
FROM {{SOURCE}}.RUN_LOG r
LEFT JOIN {{SOURCE}}.RUN_STATS s ON s.EXA_SESSION_ID = r.EXA_SESSION_ID AND s.EXA_STMT_ID = r.EXA_STMT_ID
WHERE r.RUN_ID = (SELECT MAX(x.RUN_ID) FROM {{SOURCE}}.RUN_LOG x WHERE x.STEP = r.STEP)
COMMENT IS 'The SQL statements behind the current results (latest run of each step), with Exasol-measured time and memory';
