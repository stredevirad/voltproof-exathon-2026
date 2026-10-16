import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, withDs, fmtHours, fmtMin, fmtP, fmtPct, fmtTs, fmtWindow, type Ev } from "../api";
import { esc, C, EChart, hatch } from "../charts";
import { Certainty, DataWarning, ErrorBox, Kpi, Skeleton, rowClick, useApi } from "../ui";

const PIECES = [
  { value: 0, label: "no outage", color: C.ramp[0] },
  { gt: 0, lt: 60, label: "< 1 h", color: C.ramp[1] },
  { gte: 60, lt: 240, label: "1–4 h", color: C.ramp[2] },
  { gte: 240, lt: 480, label: "4–8 h", color: C.ramp[3] },
  { gte: 480, lt: 720, label: "8–12 h", color: C.ramp[4] },
  { gte: 720, label: "≥ 12 h", color: C.ramp[5] },
];
const FULL_DAY = 1296; // 90% of 1,440 minutes

export default function LocationMonth() {
  const { id, month } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const locationId = Number(id);
  const { data, error, loading } = useApi(() => api.month(locationId, month!), [locationId, month]);
  const [sort, setSort] = useState<{ key: keyof Ev; dir: 1 | -1 }>({ key: "start_ts", dir: 1 });
  const [report, setReport] = useState<{ pdf_url: string; html_url: string; json_url: string; report_id: string;
                                        generated_at_ist: string; reused: boolean } | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportErr, setReportErr] = useState<Error | null>(null);
  const [showTable, setShowTable] = useState(false);
  const isDemo = sp.get("demo") === "1";
  const demo = useApi(() => (isDemo ? api.demo() : Promise.resolve(null)), [isDemo]);  // its window names the period

  const option = useMemo(() => {
    if (!data) return null;
    const full = data.days.filter((d) => d.observed_minutes >= FULL_DAY);
    const partial = data.days.filter((d) => d.observed_minutes < FULL_DAY);
    const byDay = Object.fromEntries(data.days.map((d) => [d.cal_day, d]));
    return {
      animation: false,
      tooltip: {
        formatter: (p: any) => {
          const d = byDay[p.value[0]];
          if (!d) return esc(p.value[0]);
          const cov = (100 * d.observed_minutes / 1440).toFixed(0);
          return `<b>${esc(d.cal_day)}</b><br/>Outage: at least ${fmtMin(d.outage_min_lower)}` +
            (d.outage_min_upper > d.outage_min_lower ? ` (up to ${fmtMin(d.outage_min_upper)})` : "") +
            `<br/>Interruptions: ${d.interruptions}<br/>Read: ${cov}% of the day` +
            (d.observed_minutes < FULL_DAY ? "<br/><i>No reading for part of the day, not counted as outage</i>" : "");
        },
      },
      // the legend is drawn as page text below the title (it wraps on a phone); the map itself stays in the chart
      visualMap: { type: "piecewise", seriesIndex: 0, show: false, pieces: PIECES },
      calendar: { top: 16, left: 44, right: 10, cellSize: ["auto", 44], range: month, orient: "horizontal",
                  yearLabel: { show: false }, monthLabel: { show: false }, dayLabel: { firstDay: 1, color: C.ink2, nameMap: "EN" },
                  splitLine: { show: false }, itemStyle: { borderColor: C.surface, borderWidth: 2, color: C.surface } },
      series: [
        // cell text is dark on the light ramp steps and white on the darkest one (12 h or more), for contrast
        { type: "heatmap", coordinateSystem: "calendar",
          data: full.map((d) => (d.outage_min_lower >= 720
            ? { value: [d.cal_day, d.outage_min_lower], label: { color: C.cellInkDark } }
            : { value: [d.cal_day, d.outage_min_lower] })),
          label: { show: true, color: C.cellInk, fontSize: 11,
                   formatter: (p: any) => `${p.value[0].slice(8)}\n${p.value[1] ? fmtHours(p.value[1]) + " h" : "–"}` } },
        { type: "heatmap", coordinateSystem: "calendar", data: partial.map((d) => [d.cal_day, d.outage_min_lower]),
          itemStyle: { color: hatch() },
          label: { show: true, color: C.cellInk2, fontSize: 10, formatter: (p: any) => `${p.value[0].slice(8)}\nlow data` } },
      ],
    };
  }, [data, month]);

  const onDayClick = useCallback((p: any) => {
    if (p?.value?.[0]) nav(withDs(`/location/${locationId}/day/${p.value[0]}`));
  }, [nav, locationId]);

  const events = useMemo(() => {
    if (!data) return [];
    return [...data.events].sort((a, b) => {
      const x = a[sort.key] as any, y = b[sort.key] as any;
      return (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
    });
  }, [data, sort]);

  async function makeReport() {
    setReportBusy(true); setReportErr(null);
    try { setReport(await api.report(locationId, month!)); } catch (e) { setReportErr(e as Error); } finally { setReportBusy(false); }
  }

  if (loading && !data) return <Skeleton height={420} label="the month" />;
  if (error) return <ErrorBox error={error} what="this location-month" />;
  if (!data) return null;
  const m = data.month;
  const loc = data.location;
  const sortBtn = (key: keyof Ev, label: string) => (
    <button className="sort" onClick={() => setSort({ key, dir: sort.key === key ? (-sort.dir as 1 | -1) : 1 })}
            aria-label={`Sort by ${label}`}>{label}{sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</button>
  );

  return (
    <div style={{ opacity: loading ? 0.6 : 1 }}>
      {isDemo && demo.data && (
        <div className="note" data-testid="demo-banner" style={{ marginTop: 12 }}>
          <strong>Guided demo.</strong> This location-month was chosen by a fixed rule: the evening potential shared
          supply event with the most monitors in {fmtWindow(demo.data.window_from, demo.data.window_to_exclusive)}, at a
          monitor whose month is comparable. It is one example. Next: <Link to={withDs(`/location/${locationId}/day/${sp.get("day")}?event=${sp.get("event")}`)} data-testid="demo-next-day">open {sp.get("day")}</Link>.
        </div>
      )}
      <p className="small muted" style={{ marginBottom: 0 }}><Link to={withDs("/")}>Start</Link> / {loc.state_name} / {loc.district}</p>
      <h1 data-testid="location-title">{loc.display_name} · {month}</h1>
      <DataWarning text={data.data_warning} />
      <div className="row small muted" style={{ alignItems: "center" }}>
        <span>{loc.source_category} · {loc.connection_type} connection</span>
        {m.is_comparable
          ? <span className="badge ok" data-testid="quality-badge">comparable month: {fmtPct(m.coverage_calendar)} of minutes read</span>
          : <span className="badge warn" data-testid="quality-badge">low coverage: {fmtPct(m.coverage_calendar)} of minutes read, not used for comparisons</span>}
      </div>

      <h2>This month in numbers</h2>
      <div className="kpis">
        <Kpi testId="kpi-outage" lead label="Outage time (at least)" value={`${fmtHours(m.outage_min_lower)} h`}
             sub={m.outage_min_upper > m.outage_min_lower
               ? `up to ${fmtHours(m.outage_min_upper)} h if every minute with no reading next to an outage was also an outage`
               : "no outage borders a minute with no reading"}
             plain="Time when the voltage read 130 V or less, which Prayas counts as no supply. Only minutes with a reading count, so this is a minimum." />
        <Kpi testId="kpi-interruptions" label="Interruptions" value={m.interruptions} sub="counted on the day they start"
             plain="Separate power cuts: each run of minutes with no supply counts once." />
        <Kpi testId="kpi-longest" label="Longest interruption" value={fmtMin(m.longest_interruption)} sub="measured minutes"
             plain="The longest single run of minutes with no supply." />
        <Kpi testId="kpi-low" label="Low voltage" value={`${fmtHours(m.low_minutes)} h`} sub={`131–204 V; high voltage ${fmtHours(m.high_minutes)} h`}
             plain="Time when the voltage read 131–204 V, below the normal range (205–270 V)." />
        <Kpi testId="kpi-coverage" label="Minutes read" value={fmtPct(m.coverage_calendar)} sub={`${m.observed_minutes.toLocaleString("en-IN")} of ${m.calendar_minutes.toLocaleString("en-IN")}`}
             plain="Share of the month's minutes with a reading. Above 90% makes the month comparable." />
      </div>
      <p className="small muted" style={{ marginBottom: 0 }}>
        {m.outage_zero_minutes.toLocaleString("en-IN")} of the outage minutes read exactly 0 V; the rest read 1–130 V.</p>
      <p className="small muted" style={{ marginTop: 0 }}>Evening (17:00–23:00) outage: at least {fmtMin(m.evening_outage_lower)}.</p>

      <div className="grid-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Outage per day (lower bound) <span className="small muted">— select a day to see its minutes</span></h3>
          <div className="chips small" aria-label="Legend: outage hours per day" data-testid="calendar-legend">
            {PIECES.map((p) => <span key={p.label} className="state"><span className="swatch" style={{ background: p.color }} />{p.label}</span>)}
          </div>
          <p className="small muted" style={{ margin: "0 0 4px" }} data-testid="calendar-key">Each square: the day of the month, then its outage hours (at least).</p>
          {option && <EChart option={option} height={16 + 7 * 44 + 14} onClick={onDayClick} testId="calendar"
                             ariaLabel={`Calendar of daily outage minutes for ${loc.display_name} in ${month}. The same values are in the table below.`} />}
          <p className="small muted"><span className="swatch nodata" /> Hatched: less than 90% of the day was read. Missing readings are never counted as outage.</p>
          <button onClick={() => setShowTable(!showTable)} aria-expanded={showTable}>{showTable ? "Hide" : "Show"} daily table</button>
          {showTable && (
            <div className="scroll" style={{ marginTop: 8 }}>
              <table className="data" data-testid="daily-table">
                <thead><tr><th className="l">Day</th><th>Interruptions</th><th>Outage min (lower–upper)</th><th>Low-V min</th><th>High-V min</th><th>Read</th></tr></thead>
                <tbody>{data.days.map((d) => (
                  <tr key={d.cal_day}><td className="l"><Link to={withDs(`/location/${locationId}/day/${d.cal_day}`)}>{d.cal_day}</Link></td>
                    <td>{d.interruptions}</td><td>{d.outage_min_lower}–{d.outage_min_upper}</td><td>{d.low_minutes}</td><td>{d.high_minutes}</td>
                    <td>{((100 * d.observed_minutes) / 1440).toFixed(0)}%</td></tr>))}</tbody>
              </table>
            </div>
          )}
        </div>
        <div className="card feature">
          <h3 style={{ marginTop: 0 }}>Evidence report</h3>
          <p className="small muted">A PDF with the calendar, every event with its certainty, potential shared supply events,
            data quality, methodology and a reproducibility appendix (file checksums, SQL hashes, Exasol statement ids).</p>
          <button className="primary" onClick={makeReport} disabled={reportBusy} data-testid="generate-report">
            {reportBusy ? "Generating…" : "Generate evidence report"}
          </button>
          {reportErr && <div style={{ marginTop: 8 }}><ErrorBox error={reportErr} what="the report" /></div>}
          {report && (
            <p data-testid="report-links">Report <span className="mono">{report.report_id}</span>:{" "}
              <a href={report.pdf_url} download data-testid="report-pdf">PDF</a> · <a href={report.html_url} target="_blank" rel="noreferrer">HTML</a> ·{" "}
              <a href={report.json_url} target="_blank" rel="noreferrer">numbers (JSON)</a>
              <br /><span className="small muted" data-testid="report-generated">Generated {report.generated_at_ist}{report.reused ? " (rendered earlier; same data and code since)" : ""}.</span></p>
          )}
          <h3>Chance comparison for {loc.district}</h3>
          {data.baseline && <p className="small muted" data-testid="baseline-gloss">How often power cuts at different monitors in
            this district started together, compared with how often chance alone would give.</p>}
          {data.baseline ? (
            <p className="small" data-testid="baseline">
              In {data.baseline.month_key}, monitors in this district had <b>{data.baseline.observed_pairs.toLocaleString("en-IN")}</b> coincident
              interruption pairs (starts ≤ 2 min apart). With the monitors' days shifted against each other by whole days (time of day kept; {data.baseline.n_shifts} fixed shifts), about <b>{data.baseline.expected_pairs.toFixed(1)}</b>{" "}
              would be expected; {fmtP(data.baseline.p_value, data.baseline.n_shifts)}. Comparable months only.
            </p>
          ) : <p className="small muted">No chance comparison for this district-month (fewer than two monitors with a comparable month).</p>}
        </div>
      </div>

      <h2>Outage events ({data.events.length})</h2>
      {data.events.length === 0 ? <p className="muted">No outage was recorded in this month.</p> : (
        <div className="card scroll" style={{ maxHeight: 480 }}>
          <table className="data" data-testid="event-table">
            <thead><tr>
              <th className="l">{sortBtn("start_ts", "Start")}</th><th className="l">End</th>
              <th>{sortBtn("min_duration", "Measured")}</th><th>{sortBtn("max_duration", "Up to")}</th>
              <th className="l">Start / end certainty</th><th className="l">Other monitors</th>
            </tr></thead>
            <tbody>{events.map((e) => (
              <tr key={e.event_key} className="clickable" onClick={rowClick(() => nav(withDs(`/event/${e.event_key}`)))}>
                <td className="l"><Link to={withDs(`/event/${e.event_key}`)}>{fmtTs(e.start_ts)}</Link></td><td className="l">{fmtTs(e.end_ts).slice(11)}</td>
                <td>{fmtMin(e.min_duration)}</td><td>{e.max_duration > e.min_duration ? fmtMin(e.max_duration) : "–"}</td>
                <td className="l"><Certainty value={e.start_certainty} /> / <Certainty value={e.end_certainty} />{!e.is_interruption && " (below threshold)"}</td>
                <td className="l">{e.group_key ? <span className="badge">potential shared supply event</span> : ""}</td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
