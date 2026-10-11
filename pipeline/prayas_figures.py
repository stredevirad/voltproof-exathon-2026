"""Read Prayas's published UP figures (docs/VALIDATION.md §3) and put VoltProof's numbers beside them.

Prayas, "ESMI in Uttar Pradesh" (7 Aug 2019) publishes its time-of-day outage as a heatmap (Figure 8: hours of
outage within each 6-hour slot, colour scale 0-5 h, one column per month). This script downloads that figure from
energy.prayaspune.org into .cache/prayas/ (never committed; the figure is Prayas's), reads each cell's colour in
Chromium, maps it to hours by nearest colour on the figure's own legend bar, and averages the month columns.
The result is an estimate read off a chart (about ±0.1 h per slot), labelled as such wherever it is quoted.

Then it computes the same quantity from Exasol (VALIDATION_LM, built by sql/110): measured OUTAGE minutes as a
share of measured minutes in each slot, times 6 h, over comparable location-months 2016-2019.

Usage: .venv\\Scripts\\python.exe -m pipeline.prayas_figures
"""

from __future__ import annotations

import base64
import urllib.request
from pathlib import Path

from pipeline.db import DEFAULT_SCHEMA, connect

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / ".cache" / "prayas"
FIG8 = "https://energy.prayaspune.org/images/ESMI-blog/4-Uttar-Pradesh/4_UP_8_Outage_ToD.png"

# Pixel geometry of Figure 8 (1200 x 600 px as published): legend bar and the 4 x 3 grid of month strips.
LEGEND_Y, LEGEND_X = 527, (600, 1168)
SLOTS = {"morning (5-11)": (100, 185), "afternoon (11-17)": (200, 288), "evening (17-23)": (302, 390),
         "night (23-5)": (405, 492)}
# x-ranges between the black separator lines (316-317, 606-609, 898-901, 1184-1186 px)
BLOCKS = {"megacity": (318, 605), "other municipal": (610, 897), "rural": (902, 1183)}

_JS = """async ([uri, ly, lx, slots, blocks]) => {
  const im = new Image(); im.src = uri; await im.decode();
  const cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height;
  const cx = cv.getContext('2d'); cx.drawImage(im, 0, 0);
  const px = (x, y) => Array.from(cx.getImageData(x, y, 1, 1).data.slice(0, 3));
  const legend = []; for (let x = lx[0]; x <= lx[1]; x++) legend.push([x, px(x, ly)]);
  const cells = {};
  for (const [s, [y0, y1]] of Object.entries(slots)) for (const [b, [x0, x1]] of Object.entries(blocks)) {
    const cols = [];
    for (let x = x0; x <= x1; x++) cols.push([y0 + 20, (y0 + y1) >> 1, y1 - 20].map((y) => px(x, y)));
    cells[b + '|' + s] = cols;
  }
  return {size: [im.width, im.height], legend, cells};
}"""


def figure8_estimate() -> dict[tuple[str, str], float]:
    """Mean hours of outage per 6-hour slot by category, read off Prayas's Figure 8 (estimate)."""
    from playwright.sync_api import sync_playwright

    CACHE.mkdir(parents=True, exist_ok=True)
    png = CACHE / "4_UP_8_Outage_ToD.png"
    if not png.exists():
        urllib.request.urlretrieve(FIG8, png)
    uri = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        d = browser.new_page().evaluate(_JS, [uri, LEGEND_Y, list(LEGEND_X), SLOTS, BLOCKS])
        browser.close()
    if d["size"] != [1200, 600]:
        raise SystemExit(f"Figure 8 is {d['size']}, expected 1200x600; the pixel geometry needs re-checking")
    # legend: keep the grey gradient only (drop white margins and the tinted anti-aliased edge pixels)
    legend = [(x, c) for x, c in d["legend"] if sum(c) < 3 * 245 and abs(c[0] - c[2]) < 30 and abs(c[0] - c[1]) < 15]
    x0, x1 = legend[0][0], legend[-1][0]

    def hours(rgb):
        x = min(legend, key=lambda s: sum((a - b) ** 2 for a, b in zip(s[1], rgb)))[0]
        return 5 * (x - x0) / (x1 - x0)

    out = {}
    for key, cols in d["cells"].items():
        block, slot = key.split("|")
        per_col = [sum(hours(c) for c in col) / len(col) for col in cols]
        out[(block, slot)] = sum(per_col) / len(per_col)
    return out


def voltproof_by_slot() -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    """(pooled over all location-months, equal weight per calendar month like Figure 8's month columns)."""
    names = list(SLOTS)
    with connect(schema=DEFAULT_SCHEMA) as c:
        rows = c.execute("""
            SELECT v.PRAYAS_CATEGORY, v.MONTH_START,
                   CASE WHEN HOUR(rs.TS) BETWEEN 5 AND 10 THEN 0 WHEN HOUR(rs.TS) BETWEEN 11 AND 16 THEN 1
                        WHEN HOUR(rs.TS) BETWEEN 17 AND 22 THEN 2 ELSE 3 END AS SLOT,
                   SUM(CASE WHEN rs.SUPPLY_STATE = 'OUTAGE' THEN 1 ELSE 0 END) AS OUT_MIN, COUNT(*) AS READ_MIN
            FROM READING_STATE rs
            JOIN VALIDATION_LM v ON v.LOCATION_ID = rs.LOCATION_ID AND v.MONTH_START = CAST(TRUNC(rs.TS, 'MM') AS DATE)
            GROUP BY 1, 2, 3""").fetchall()
    tot: dict[tuple[str, str], list[float]] = {}
    per_month: dict[tuple[str, str], list[float]] = {}
    for cat, _, slot, out_min, read_min in rows:
        key = (cat, names[int(slot)])
        t = tot.setdefault(key, [0.0, 0.0])
        t[0], t[1] = t[0] + float(out_min), t[1] + float(read_min)
        per_month.setdefault(key, []).append(6 * float(out_min) / float(read_min))
    pooled = {k: 6 * o / n for k, (o, n) in tot.items()}
    monthly = {k: sum(v) / len(v) for k, v in per_month.items()}
    return pooled, monthly


# Single-monitor supply profiles (Figures 10, 11, 12, 14): one stacked bar per month, hours/day by voltage class,
# stacked to 24 h (no-data included). Each bar's class shares are read by counting pixels of each legend colour
# down the bar's centre column, so the bar's own height is the 24 h scale. Months Prayas omits are not shown.
_BASE = "https://energy.prayaspune.org/images/ESMI-blog/4-Uttar-Pradesh/"
PROFILES = {
    # figure: (file, our LOCATION_ID, panel y-range, months in bar order)
    "Fig 10 Sikanderabad, Sitapur": ("4_UP_10_Supply_Profile_SIkanderabad.png", 459, (20, 272),
                                     ["2017-12"] + [f"2018-{m:02d}" for m in range(1, 8)]),
    "Fig 12 Baraulia, Barabanki": ("4_UP_12_Supply_Profile_Baraulia.png", 58, (30, 458),
                                   [f"2018-{m:02d}" for m in range(1, 9)]),
    "Fig 11 Biswan, Sitapur": ("4_UP_11_Biswan.png", 90, (440, 702),
                               [f"2018-{m:02d}" for m in (3, 4, 5, 6, 7, 8, 10, 11, 12)]
                               + [f"2019-{m:02d}" for m in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11)]),
    "Fig 14 Huzurpur road, Kaisarganj": ("4_UP_14_Huzurpur_road_Kaisarganj.png", 182, (455, 702),
                                         [f"2018-{m:02d}" for m in range(4, 13)]
                                         + [f"2019-{m:02d}" for m in (1, 2, 3, 4, 6)]),
}
CLASSES = ["normal", "low", "high", "no supply", "no data"]

_JS_BARS = """async ([uri, py, legendY]) => {
  const im = new Image(); im.src = uri; await im.decode();
  const cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height;
  const cx = cv.getContext('2d'); cx.drawImage(im, 0, 0);
  const d = cx.getImageData(0, 0, im.width, im.height).data;
  const px = (x, y) => { const i = 4 * (y * im.width + x); return [d[i], d[i + 1], d[i + 2]]; };
  const coloured = (c) => c[0] + c[1] + c[2] < 735 && (Math.max(...c) - Math.min(...c) > 12 || (c[0] > 190 && c[0] < 235));
  const runs = (y, minW) => { const out = []; let cur = null;
    for (let x = 0; x < im.width; x++) if (coloured(px(x, y))) {
      if (cur && x === cur[1] + 1) cur[1] = x; else { cur = [x, x]; out.push(cur); } }
    return out.filter((r) => r[1] - r[0] >= minW); };
  const legend = runs(legendY, 8).map((r) => px((r[0] + r[1]) >> 1, legendY));
  const mid = (py[0] + py[1]) >> 1;
  const bars = runs(mid, 30).map((r) => { const x = (r[0] + r[1] + 4) >> 1, col = [];
    for (let y = py[0]; y <= py[1]; y++) col.push(px(x, y)); return col; });
  return {legend, bars};
}"""


def profiles_from_figures() -> dict[str, list[dict[str, float]]]:
    from playwright.sync_api import sync_playwright

    CACHE.mkdir(parents=True, exist_ok=True)
    legend_y = {"4_UP_10_Supply_Profile_SIkanderabad.png": 330, "4_UP_12_Supply_Profile_Baraulia.png": 517}
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for fig, (fname, _, py, months) in PROFILES.items():
            png = CACHE / fname
            if not png.exists():
                urllib.request.urlretrieve(_BASE + fname, png)
            uri = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
            d = page.evaluate(_JS_BARS, [uri, list(py), legend_y.get(fname, 777)])
            if len(d["legend"]) != 5 or len(d["bars"]) != len(months):
                raise SystemExit(f"{fig}: found {len(d['legend'])} legend swatches and {len(d['bars'])} bars, "
                                 f"expected 5 and {len(months)}; the pixel geometry needs re-checking")
            rows = []
            for col in d["bars"]:
                counts = dict.fromkeys(CLASSES, 0)
                for c in col:
                    dist, k = min((sum((a - b) ** 2 for a, b in zip(c, ref)), k) for k, ref in zip(CLASSES, d["legend"]))
                    if dist < 400:  # within ~20 RGB units of a legend colour; skips white, gridlines, text
                        counts[k] += 1
                total = sum(counts.values())
                rows.append({k: 24 * v / total for k, v in counts.items()})
            out[fig] = rows
        browser.close()
    return out


def profiles_from_exasol() -> dict[str, dict[str, dict[str, float]]]:
    """Hours/day by class per calendar month, straight from READING_STATE (no-data = calendar minutes not read)."""
    ids = ", ".join(str(v[1]) for v in PROFILES.values())
    with connect(schema=DEFAULT_SCHEMA) as c:
        rows = c.execute(f"""
            SELECT LOCATION_ID, TO_CHAR(TRUNC(TS, 'MM'), 'YYYY-MM') AS M,
                   DAYS_BETWEEN(ADD_MONTHS(CAST(TRUNC(TS, 'MM') AS DATE), 1), CAST(TRUNC(TS, 'MM') AS DATE)) AS NDAYS,
                   SUM(CASE WHEN SUPPLY_STATE = 'NORMAL' THEN 1 ELSE 0 END), SUM(CASE WHEN SUPPLY_STATE = 'LOW' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN SUPPLY_STATE = 'HIGH' THEN 1 ELSE 0 END), SUM(CASE WHEN SUPPLY_STATE = 'OUTAGE' THEN 1 ELSE 0 END)
            FROM READING_STATE WHERE LOCATION_ID IN ({ids}) GROUP BY 1, 2, 3""").fetchall()
    out: dict[str, dict[str, dict[str, float]]] = {}
    for lid, m, ndays, *mins in rows:
        h = [float(v) / 60 / float(ndays) for v in mins]
        out.setdefault(str(lid), {})[m] = dict(zip(CLASSES, h + [24 - sum(h)]))
    return out


def compare_profiles() -> None:
    fig, ours = profiles_from_figures(), profiles_from_exasol()
    print("\nSingle-monitor supply profiles, hours/day: Prayas figure (read from pixels) vs VoltProof")
    # 2019 is reported separately: the 2019 Jan-Jun file omits most all-0 V hours (docs/VALIDATION.md §3.4)
    worst = {"2017-2018": dict.fromkeys(CLASSES, 0.0), "2019": dict.fromkeys(CLASSES, 0.0)}
    n = dict.fromkeys(worst, 0)
    for name, (_, lid, _, months) in PROFILES.items():
        print(f"\n{name} (our location {lid})")
        print(f"  {'month':8s}" + "".join(f"{k:>18s}" for k in CLASSES))
        for m, f in zip(months, fig[name]):
            o = ours.get(str(lid), {}).get(m)
            if o is None:
                print(f"  {m:8s}" + "".join(f"{f[k]:8.1f}  {'(none)':>8s}" for k in CLASSES))
                continue
            period = "2019" if m.startswith("2019") else "2017-2018"
            n[period] += 1
            for k in CLASSES:
                worst[period][k] = max(worst[period][k], abs(f[k] - o[k]))
            print(f"  {m:8s}" + "".join(f"{f[k]:8.1f} vs {o[k]:5.1f}" for k in CLASSES))
    for period, w in worst.items():
        print(f"\nlargest absolute difference, {period} ({n[period]} monitor-months, h/day): "
              + ", ".join(f"{k} {v:.1f}" for k, v in w.items()))


def main() -> None:
    fig, (pooled, monthly) = figure8_estimate(), voltproof_by_slot()
    print("Hours of outage per 6-h slot. Prayas Figure 8 read from its colour scale (estimate, month columns averaged);")
    print("VoltProof equal weight per month (like-for-like) and pooled over location-months.")
    print(f"{'category':16s} {'slot':18s} {'Prayas Fig.8':>13s} {'VP monthly':>11s} {'VP pooled':>10s}")
    for block in BLOCKS:
        tf = tm = tp = 0.0
        for slot in SLOTS:
            f, m, p = fig[(block, slot)], monthly[(block, slot)], pooled[(block, slot)]
            tf, tm, tp = tf + f, tm + m, tp + p
            print(f"{block:16s} {slot:18s} {f:13.2f} {m:11.2f} {p:10.2f}")
        print(f"{block:16s} {'per day (min)':18s} {60 * tf:13.0f} {60 * tm:11.0f} {60 * tp:10.0f}")
    compare_profiles()


if __name__ == "__main__":
    main()
