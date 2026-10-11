-- 070_uncertain_claims.sql
-- R-15: "possibly-outage" NO_DATA minutes. A NO_DATA run [s, e] next to an OUTAGE run may have been
-- outage for up to CAP minutes from that side. The left claim is [s, s+cap-1], the right claim is
-- [e-cap+1, e], and their union is stored (one interval when they touch or overlap, else two).
-- Window-boundary gaps do not exist as NO_DATA segments, so they never claim anything.

CREATE OR REPLACE TABLE UNCERTAIN_CLAIM AS
WITH P AS (
    SELECT MAX(CASE WHEN NAME = 'events.max_uncertain_extension_minutes' THEN NUM_VALUE END) AS CAP
    FROM PARAMS
), S AS (
    SELECT s.LOCATION_ID, s.SEG_NO, s.SUPPLY_STATE, s.START_TS, s.END_TS, s.MINUTES,
           LAG(s.SUPPLY_STATE)  OVER (PARTITION BY s.LOCATION_ID ORDER BY s.SEG_NO) AS PREV_STATE,
           LEAD(s.SUPPLY_STATE) OVER (PARTITION BY s.LOCATION_ID ORDER BY s.SEG_NO) AS NEXT_STATE
    FROM SEGMENT s
), N AS (
    SELECT S.LOCATION_ID, S.SEG_NO, S.START_TS, S.END_TS, S.MINUTES,
           CASE WHEN PREV_STATE = 'OUTAGE' THEN LEAST(MINUTES, P.CAP) ELSE 0 END AS L_LEN,
           CASE WHEN NEXT_STATE = 'OUTAGE' THEN LEAST(MINUTES, P.CAP) ELSE 0 END AS R_LEN
    FROM S CROSS JOIN P
    WHERE S.SUPPLY_STATE = 'NO_DATA'
)
SELECT LOCATION_ID, SEG_NO, START_TS AS CLAIM_START, END_TS AS CLAIM_END, MINUTES AS CLAIM_MINUTES,
       'both' AS SIDE
FROM N
WHERE L_LEN > 0 AND R_LEN > 0 AND L_LEN + R_LEN >= MINUTES
UNION ALL
SELECT LOCATION_ID, SEG_NO, START_TS, ADD_MINUTES(START_TS, L_LEN - 1), L_LEN, 'after_outage'
FROM N
WHERE L_LEN > 0 AND NOT (R_LEN > 0 AND L_LEN + R_LEN >= MINUTES)
UNION ALL
SELECT LOCATION_ID, SEG_NO, ADD_MINUTES(END_TS, -(R_LEN - 1)), END_TS, R_LEN, 'before_outage'
FROM N
WHERE R_LEN > 0 AND NOT (L_LEN > 0 AND L_LEN + R_LEN >= MINUTES);
