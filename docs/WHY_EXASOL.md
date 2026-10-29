# Why Exasol: what it does for VoltProof (measured)

VoltProof's analysis is **versioned SQL that runs inside Exasol Personal**: ingestion, unpivot, cleaning,
run detection, events, aggregates, data quality and coincidence analysis. Python only orchestrates, loads
the files, serves the app and hosts the independent test oracle. Numbers below come from
[BENCHMARKS.md](BENCHMARKS.md) (recorded runs, medians of warm runs on the build laptop) and the
[verification log](VERIFICATION_LOG.md).

## 1. Native IMPORT, with every line still traceable

- **What it does.** `IMPORT … FROM CSV` loads the raw 63-column hourly rows unchanged over Exasol's HTTP
  transport (`pipeline/load_raw.py`, pyexasol `import_from_callback`). Each line arrives prefixed with its
  file id and physical line number, which is how a report later cites the exact source line.
- **Measured:** all 11 Uttar Pradesh files (7,367,581 raw rows) in **30.3 s** (warm median; 35.1 s cold). The
  first sample load ran at about 440,000 rows/s (VERIFICATION_LOG G2a).

## 2. Unpivot in the database, not in Python

- **What it does.** Each hourly row holds 60 minute values in columns. `sql/030_unpivot.sql` joins the rows
  with a 60-row generator (`CONNECT BY LEVEL <= 60`) and picks the column per minute.
- **Measured:** **11.0 s** for 102,927,720 minute rows, plus 5.4 s to type and validate them.
- **Why it matters.** Malformed rows and values are quarantined with reason codes in the same SQL, so
  nothing is dropped silently.

## 3. Window functions over 100 million rows: gaps-and-islands

- **What it does.** Outages are runs of consecutive minutes in one voltage class. `sql/050_segments.sql`
  finds every run with a single window function: `minute number − ROW_NUMBER() OVER (PARTITION BY
  location, state ORDER BY ts)` is constant along a run.
- **Measured:** **35.6 s** over 102.8 million readings (temporary-memory peak 6.2 GiB).
- **The earlier formulation, from the audit log:** LAG plus a running SUM took **665 s** and needed 7.4 GiB
  of temporary memory, because it sorted the data twice (DECISIONS D-028).
- **Events.** `sql/060_events.sql` then uses LAG/LEAD over segments to give each outage its edge
  certainty and duration bounds, in 2.7 s for 408,223 events.

## 4. Band joins across monitors, as equality joins

- **What it does.** A potential shared supply event needs every pair of interruptions in a district whose
  starts are at most 2 minutes apart. That is a band join. `sql/100_coincidence.sql` turns it into two
  equality joins on a time bucket (same bucket, next bucket), which Exasol executes as hash joins.
- **Measured:** **0.4 s** for 184,299 coincident pairs. The chance baseline (20 whole-day shifts of
  every monitor) takes **3.9 s** for its four statements.
- **The earlier non-equality band join, from the audit log:** 348 s on the 2018 June–August sample alone
  (D-021). A cross-join variant was cancelled after 613 s.

## 5. Provenance from the audit log

- **Statement ids.** Every SQL statement runs in its own step transaction, and the runner records Exasol's
  session id and statement id (`CURRENT_STATEMENT + 1` in non-autocommit mode, D-017).
- **Check against the audit log.** `pipeline/check_provenance.py` compares each recorded statement with
  `EXA_DBA_AUDIT_SQL` by the SHA-256 of its exact SQL text. Every benchmark build matched all of them
  (all 6 recorded runs, 3 cold and 3 warm: 0 different, 0 missing).
- **In reports.** An evidence report lists the statement ids, so a reviewer can find the SQL that produced
  each table in the database's own log.
- **Benchmarks.** They use the same audit statistics: duration, CPU and temporary-memory peak per statement
  ([BENCHMARKS.md](BENCHMARKS.md)).

## 6. One local database that a judge can start

- **Install.** Exasol Personal installed in about 2 minutes through the launcher (VERIFICATION_LOG X19). It
  runs as a single node in a Podman machine on WSL 2, with 8.9 GiB of DB RAM on a 15.6 GB laptop (X29).
- **Storage.** The data volume is bind-mounted on the repository drive, not C: (X21, X22).
- **The same SQL on Exasol's own image in CI.** Every push starts Exasol's `exasol/nano` container on GitHub
  Actions, builds the SYNTHETIC set with the same steps, checks that the SQL equals the oracle on the fixtures and
  the synthetic set, and checks provenance against the audit log ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

## What we did not use, and what we did not claim

- **UDFs: available, not used on purpose.** A local Exasol Personal deployment runs Python 3, Java and R UDFs
  once an official script-language container is installed, for example `exasol slc install python3` (launcher
  2.2 and later; [Exasol community, 7 Aug 2026](https://community.exasol.com/t/exasol-personal-2-2-is-here/303)).
  Our launcher, 2.3.0, lists those three containers and also offers a `rust` alias for the exasol-labs Rust
  container. Lua scripts and Lua UDFs need no container at all (VERIFICATION_LOG X10).
- **Why plain SQL.** We kept the method in plain SQL on purpose: each rule is readable in one SQL file, and every
  result comes from SQL statements that Exasol's audit log records and `check_provenance` matches (§5). Python
  stays outside the database, as the orchestrator and the independent oracle.
- **No speed comparison with other engines.** We did not benchmark DuckDB, Excel or anything else on the
  same data, so we make no "faster than" claim.
- **Costs on this laptop, recorded honestly:**
  - The first growth of the data volume over the Windows-to-WSL bind mount is slow (434 s for a write
    that later took 21 s; X31).
  - A full build leaves little free host RAM (lowest 1.23 GiB in the recorded runs, with other memory-heavy applications closed. With them open, two runs fell below our 0.4 GiB free-RAM guard and were stopped; BENCHMARKS.md).
