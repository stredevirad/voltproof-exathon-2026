import { Link, useParams } from "react-router-dom";
import { api, fmtMin, fmtP, fmtTs, type GroupData } from "../api";
import { ErrorBox, Skeleton, useApi } from "../ui";

function edgeText(kind: "start" | "end", certainty: string, seg: { supply_state: string; minutes: number } | null, cap = 60) {
  const where = kind === "start" ? "before it began" : "after it ended";
  if (certainty === "exact") return `Exact: the minute ${where} was measured with ${seg?.supply_state.toLowerCase()} supply.`;
  if (certainty === "bounded") return `Bounded: the ${seg?.minutes} minute(s) ${where} have no reading, so the outage may have ` +
    `${kind === "start" ? "started" : "ended"} up to ${Math.min(seg?.minutes ?? 0, cap)} minutes ${kind === "start" ? "earlier" : "later"}. ` +
    "Missing minutes are not counted in the measured duration.";
  return `Censored: monitoring ${kind === "start" ? "started" : "ended"} during this outage, so its true ${kind} is unknown.`;
}

export function GroupPanel({ g, highlight }: { g: GroupData; highlight?: string }) {
  return (
    <div className="card" data-testid="coincidence-panel">
      <h3 style={{ marginTop: 0 }}>
        {highlight
          ? `${g.n_locations - 1} other monitor${g.n_locations - 1 === 1 ? "" : "s"} lost supply within 2 minutes`
          : `${g.n_locations} monitors lost supply within 2 minutes of each other`}
      </h3>
      <p className="small muted">Potential shared supply event {g.group_key}: {g.n_pairs} coincident pairs in {g.district} district.
        {" "}{g.district_locations_with_interruptions} monitors in the district had interruptions that month.</p>
      <div className="scroll" style={{ maxHeight: 300 }}>
        <table className="data">
          <thead><tr><th className="l">Monitor</th><th className="l">Start</th><th>Offset</th><th>Measured</th></tr></thead>
          <tbody>{g.members.map((m) => (
            <tr key={m.event_key} style={m.event_key === highlight ? { fontWeight: 700 } : undefined}>
              <td className="l"><Link to={`/event/${m.event_key}`}>{m.display_name}</Link></td>
              <td className="l">{fmtTs(m.start_ts)}</td><td>+{m.offset_from_group_start_min} min</td><td>{fmtMin(m.min_duration)}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {g.baseline ? (
        <p className="small" data-testid="baseline-note">Chance comparison, {g.baseline.district} {g.baseline.month_key} (comparable months only):
          <b> {g.baseline.observed_pairs.toLocaleString("en-IN")}</b> coincident pairs observed, about <b>{g.baseline.expected_pairs.toFixed(1)}</b>{" "}
          expected if each monitor's outage days were shifted at random; {fmtP(g.baseline.p_value, g.baseline.n_shifts)}.</p>
      ) : <p className="small muted">No chance comparison for this district-month.</p>}
      <div className="note caveat small">Coincidence is not cause. A shared upstream cause is possible, but a single-premise fault, a monitor
        fault or chance can produce the same pattern. VoltProof calls this a <i>potential shared supply event</i> and does not identify any equipment.</div>
    </div>
  );
}

export default function EventView() {
  const { key } = useParams();
  const { data: e, error, loading } = useApi(() => api.event(key!), [key]);
  if (loading && !e) return <Skeleton height={360} label="the event" />;
  if (error) return <ErrorBox error={error} what="this outage event" />;
  if (!e) return null;
  const day = e.start_ts.slice(0, 10);
  return (
    <>
      <p className="small muted" style={{ marginBottom: 0 }}>
        <Link to="/">Start</Link> / <Link to={`/location/${e.location_id}/${e.start_ts.slice(0, 7)}`}>{e.display_name} · {e.start_ts.slice(0, 7)}</Link> /{" "}
        <Link to={`/location/${e.location_id}/day/${day}?event=${e.event_key}`}>{day}</Link>
      </p>
      <h1 data-testid="event-title">Outage at {e.display_name}, {fmtTs(e.start_ts)}</h1>
      <div className="grid-2">
        <div className="card" data-testid="event-details">
          <table className="data">
            <tbody>
              <tr><td className="l">First outage minute (measured)</td><td className="l" data-testid="event-start">{fmtTs(e.start_ts)}</td></tr>
              <tr><td className="l">Last outage minute (measured)</td><td className="l" data-testid="event-end">{fmtTs(e.end_ts)}</td></tr>
              <tr><td className="l">Measured duration (lower bound)</td><td className="l"><b data-testid="event-min">{fmtMin(e.min_duration)}</b></td></tr>
              <tr><td className="l">Possible duration (upper bound)</td><td className="l" data-testid="event-max">{fmtMin(e.max_duration)}</td></tr>
              <tr><td className="l">Minutes reading exactly 0 V</td><td className="l">{e.zero_minutes} of {e.min_duration}</td></tr>
              {e.bridged_minutes > 0 && <tr><td className="l">Unobserved minutes bridged inside the event</td><td className="l">{e.bridged_minutes}</td></tr>}
              <tr><td className="l">Counted as an interruption</td><td className="l">{e.is_interruption ? "yes" : "no (shorter than the threshold)"}</td></tr>
              <tr><td className="l">Event key</td><td className="l mono">{e.event_key}</td></tr>
            </tbody>
          </table>
          <h3>How certain are the start and end?</h3>
          <p className="small" data-testid="start-certainty">{edgeText("start", e.start_certainty, e.before)}</p>
          <p className="small" data-testid="end-certainty">{edgeText("end", e.end_certainty, e.after)}</p>
          <details data-testid="provenance">
            <summary>How was this computed?</summary>
            <p className="small">Readings at or below 130 V (Prayas's "no supply" class) in consecutive minutes form one event. This was computed
              by versioned SQL inside Exasol; missing minutes are never counted. Source lines of the first and last minute:</p>
            <ul className="small">{e.source_lines.map((s) => (
              <li key={s.ts}>{fmtTs(s.ts)}: {s.voltage} V, <span className="mono">{s.file_name}</span>, line {s.line_no}</li>))}</ul>
            <table className="data small">
              <thead><tr><th className="l">SQL step</th><th>#</th><th className="l">File SHA-256</th><th className="l">Exasol session / statement</th></tr></thead>
              <tbody>{e.provenance.map((p) => (
                <tr key={`${p.step}-${p.stmt_index}`}><td className="l">sql/{p.step}</td><td>{p.stmt_index}</td>
                  <td className="l mono">{p.sql_file_sha256.slice(0, 16)}…</td><td className="l mono">{p.exa_session_id} / {p.exa_stmt_id}</td></tr>))}</tbody>
            </table>
            <p className="small muted">Each session/statement pair can be looked up in Exasol's audit table, where the SQL text matches these hashes.</p>
          </details>
        </div>
        <div>
          {e.group ? <GroupPanel g={e.group} highlight={e.event_key} /> : (
            <div className="card" data-testid="coincidence-panel">
              <h3 style={{ marginTop: 0 }}>Other monitors</h3>
              <p className="small">No other monitor in {e.district} district lost supply within 2 minutes of this interruption.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
