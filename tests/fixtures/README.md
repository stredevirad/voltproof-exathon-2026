# Synthetic test fixtures (hand-written)

**Synthetic data, for tests only.** No row here comes from ESMI or any real monitor.

Each `Fxx_*.yaml` file defines:
- `rules`: the METHODOLOGY rule IDs the fixture exercises;
- `params`: overrides of `config/method.yaml` for this fixture (flattened names, e.g.
  `events.gap_bridge_max_minutes`);
- `locations`: rows of a fixture location file (same columns as the ESMI location file);
- `hours`: wide raw rows in the real ESMI layout (`Location name, Date (DD-MM-YYYY), Hour, Min 0..Min 59`).
  `values` is a compact run notation expanded to exactly 60 cells:
  - `230*5` means five cells of `230`;
  - `_*3` means three **blank** cells (no reading);
  - any other token is written verbatim, e.g. `abc` for a non-numeric cell;
- `expected`: results **derived by hand from the rules**, each with a one-line `why`. They are not
  produced by running our code.

`tests/fixtures/render.py` expands the YAML into `rendered/<fixture>/readings.csv` and
`rendered/<fixture>/locations.csv` (byte layout of the real files: header row, CRLF). Those CSVs are
committed so they can be inspected. `tests/integration/test_fixtures.py` loads them through the
real pipeline (`load_raw` → SQL 020…090) into the schema `VP_TEST` and compares every expected value.
Fields not listed under `expected` are not asserted by that fixture.
