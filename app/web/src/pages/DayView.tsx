import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, withDs, fmtMin, fmtTs } from "../api";
import { esc, C, EChart, hatch } from "../charts";
import { Certainty, DataWarning, ErrorBox, Skeleton, StateLegend, useApi } from "../ui";

const toMs = (ts: string) => new Date(ts + ":00").getTime(); // local wall-clock (IST as recorded)

export default function DayView() {
  const { id, day } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const locationId = Number(id);
  const selected = sp.get("event");
  const { data, error, loading } = useApi(() => api.day(locationId, day!), [locationId, day]);
  const [showTable, setShowTable] = useState(false);

  const option = useMemo(() => {
    if (!data) return null;
    const start = toMs(`${day}T00:00`);
    const end = toMs(`${day}T23:59`);
    const byTs = new Map(data.readings.map((r) => [r.ts, r.voltage]));
    const pts: [number, number | null][] = [];
    for (let i = 0; i < 1440; i++) {
      const t = start + i * 60000;
      const d = new Date(t);
      const key = `${day}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      pts.push([t, byTs.has(key) ? byTs.get(key)! : null]);
    }
    const clip = (a: string, b: string): [number, number] => [Math.max(toMs(a), start), Math.min(toMs(b) + 60000, end + 60000)];
    const noData = data.segments.filter((s) => s.supply_state === "NO_DATA").map((s) => {
      const [a, b] = clip(s.start_ts, s.end_ts);
      return [{ name: "no reading — not counted as outage", xAxis: a, itemStyle: { color: hatch() } }, { xAxis: b }];
    });
    const outages = data.events.map((e) => {
      const [a, b] = clip(e.start_ts, e.end_ts);
      const sel = e.event_key === selected;
      return [{ name: e.event_key, xAxis: a,
                itemStyle: { color: C.outage, opacity: sel ? 0.55 : 0.3, borderColor: sel ? C.ink1 : undefined, borderWidth: sel ? 1.5 : 0 },
                // label only wide blocks (or the selected one) so labels never collide; every outage is in the table
                label: { show: b - a >= 100 * 60000 || sel, formatter: `${e.min_duration} min`, color: C.ink1, fontSize: 11 } },
              { xAxis: b }];
    });
    return {
      animation: false,
      grid: { left: 54, right: 150, top: 24, bottom: 56 },
      tooltip: { trigger: "axis", axisPointer: { type: "line" },
                 formatter: (ps: any[]) => {
                   const p = ps.find((x) => x.seriesName === "Voltage");
                   if (!p) return "";
                   const t = new Date(p.value[0]);
                   const hh = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
                   const v = p.value[1];
                   if (v == null) return `${esc(hh)}<br/>no reading (not counted as outage)`;
                   const st = v <= 130 ? "no supply" : v < 205 ? "low voltage" : v <= 270 ? "normal" : "high voltage";
                   return `${esc(hh)}<br/><b>${esc(v)} V</b>, ${esc(st)}`;
                 } },
      xAxis: { type: "time", min: start, max: end + 60000, axisLine: { lineStyle: { color: C.axis } },
               axisLabel: { color: C.ink2, formatter: "{HH}:{mm}" }, splitLine: { show: false } },
      yAxis: { type: "value", min: 0, max: 380, name: "volts", nameTextStyle: { color: C.ink2 },
               axisLabel: { color: C.ink2 }, splitLine: { lineStyle: { color: C.grid } } },
      dataZoom: [{ type: "inside", xAxisIndex: 0 }, { type: "slider", xAxisIndex: 0, height: 18, bottom: 8 }],
      series: [
        { name: "Voltage", type: "line", data: pts, showSymbol: false, connectNulls: false,
          lineStyle: { color: C.ink2, width: 2 }, itemStyle: { color: C.ink2 }, z: 5,
          markArea: { silent: true, data: [
            [{ yAxis: 0, itemStyle: { color: C.outage, opacity: 0.08 }, name: "No supply ≤ 130 V" }, { yAxis: 130 }],
            [{ yAxis: 130, itemStyle: { color: C.low, opacity: 0.07 }, name: "Low 131–204 V" }, { yAxis: 205 }],
            [{ yAxis: 205, itemStyle: { color: "#ffffff", opacity: 0 }, name: "Normal 205–270 V" }, { yAxis: 270 }],
            [{ yAxis: 270, itemStyle: { color: C.high, opacity: 0.08 }, name: "High > 270 V" }, { yAxis: 380 }],
          ], label: { position: "right", color: C.ink2, fontSize: 11 } } },
        { name: "No reading", type: "line", data: [], markArea: { silent: true, data: noData,
          label: { show: true, position: "insideTop", color: C.ink2, fontSize: 10, overflow: "truncate" } } },
        { name: "Outage", type: "line", data: [], markArea: { data: outages } },
      ],
    };
  }, [data, day, selected]);

  const onClick = useCallback((p: any) => {
    if (p?.componentType === "markArea" && p?.seriesName === "Outage" && p?.data?.name) nav(withDs(`/event/${p.data.name}`));
  }, [nav]);

  if (loading && !data) return <Skeleton height={420} label="the day" />;
  if (error) return <ErrorBox error={error} what="this day" />;
  if (!data) return null;
  const d = data.daily;
  return (
    <>
      <p className="small muted" style={{ marginBottom: 0 }}>
        <Link to={withDs("/")}>Start</Link> / <Link to={withDs(`/location/${locationId}/${day!.slice(0, 7)}`)}>{data.location?.display_name} · {day!.slice(0, 7)}</Link>
      </p>
      <h1 data-testid="day-title">{data.location?.display_name} · {day}</h1>
      <DataWarning text={data.data_warning} />
      {d ? (
        <p className="muted">
          {d.interruptions} interruptions · outage at least {fmtMin(d.outage_min_lower)}
          {d.outage_min_upper > d.outage_min_lower && ` (up to ${fmtMin(d.outage_min_upper)})`} ·
          read {((100 * d.observed_minutes) / 1440).toFixed(0)}% of the day · evening outage at least {fmtMin(d.evening_outage_lower)}
        </p>
      ) : <p className="muted">This day is outside the monitoring window.</p>}
      <StateLegend />
      <div className="card">
        <EChart option={option} height={380} onClick={onClick} testId="voltage-trace"
                ariaLabel={`Minute-by-minute voltage on ${day}. Outages and missing readings are listed in the table below.`} />
        <p className="small muted">Select a shaded outage to see its evidence. Drag the slider or scroll to zoom. The grey line is the measured voltage; it breaks where there is no reading.</p>
        <button onClick={() => setShowTable(!showTable)} aria-expanded={showTable}>{showTable ? "Hide" : "Show"} minute segments as a table</button>
        {showTable && (
          <div className="scroll" style={{ marginTop: 8 }}>
            <table className="data" data-testid="segment-table">
              <thead><tr><th className="l">State</th><th className="l">From</th><th className="l">To</th><th>Minutes</th></tr></thead>
              <tbody>{data.segments.map((s) => (
                <tr key={s.seg_no}><td className="l">{s.supply_state === "NO_DATA" ? "no reading (not counted as outage)" : s.supply_state.toLowerCase()}</td>
                  <td className="l">{fmtTs(s.start_ts)}</td><td className="l">{fmtTs(s.end_ts)}</td><td>{s.minutes}</td></tr>))}</tbody>
            </table>
          </div>
        )}
      </div>
      <h2>Outages on this day</h2>
      {data.events.length === 0 ? <p className="muted">No outage on this day.</p> : (
        <table className="data card" data-testid="day-events">
          <thead><tr><th className="l">Start</th><th className="l">End</th><th>Measured</th><th>Up to</th><th className="l">Certainty</th><th className="l"></th></tr></thead>
          <tbody>{data.events.map((e) => (
            <tr key={e.event_key} className="clickable" tabIndex={0} onClick={() => nav(withDs(`/event/${e.event_key}`))}
                onKeyDown={(k) => k.key === "Enter" && nav(withDs(`/event/${e.event_key}`))} aria-current={e.event_key === selected}>
              <td className="l">{fmtTs(e.start_ts)}</td><td className="l">{fmtTs(e.end_ts)}</td><td>{fmtMin(e.min_duration)}</td>
              <td>{e.max_duration > e.min_duration ? fmtMin(e.max_duration) : "–"}</td>
              <td className="l"><Certainty value={e.start_certainty} /> / <Certainty value={e.end_certainty} /></td>
              <td className="l">{e.group_key && <span className="badge">other monitors lost supply too</span>}
                {e.event_key === selected && <Link to={withDs(`/event/${e.event_key}`)} data-testid="open-selected-event"> open evidence →</Link>}</td>
            </tr>))}</tbody>
        </table>
      )}
    </>
  );
}
