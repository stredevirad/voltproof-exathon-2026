import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtHours, fmtPct } from "../api";
import { ErrorBox, Skeleton, useApi, useDataset } from "../ui";

export default function Home() {
  const nav = useNavigate();
  const ds = useDataset();
  const states = useApi(() => api.states(), []);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [q, setQ] = useState("");
  const [locId, setLocId] = useState<number | null>(null);
  const locs = useApi(() => api.locations(state || undefined, undefined, undefined), [state]);
  const loc = useApi(() => (locId ? api.location(locId) : Promise.resolve(null)), [locId]);
  const [demoError, setDemoError] = useState<Error | null>(null);
  const [demoBusy, setDemoBusy] = useState(false);

  const districts = useMemo(() => Array.from(new Set((locs.data || []).map((l) => l.district))).sort(), [locs.data]);
  const shown = useMemo(() => (locs.data || []).filter((l) =>
    (!district || l.district === district) && (!q || l.display_name.toLowerCase().includes(q.toLowerCase()))), [locs.data, district, q]);

  async function startDemo() {
    setDemoBusy(true);
    setDemoError(null);
    try {
      const d = await api.demo();
      nav(`/location/${d.location_id}/${d.month}?demo=1&day=${d.day}&event=${d.event_key}`);
    } catch (e) {
      setDemoError(e as Error);
    } finally {
      setDemoBusy(false);
    }
  }

  return (
    <>
      <section className="hero">
        <div>
          <h1>Turn minute-by-minute voltage records into traceable evidence of power cuts and poor supply.</h1>
          <p className="muted">
            Pick a monitored location and a month. VoltProof shows every interruption the independent monitor recorded,
            how certain each one is, and whether other monitors in the district lost supply at the same time. Then it
            produces a report that traces every number back to the source file and line.{" "}
            {ds?.synthetic
              ? <>Data: the SYNTHETIC demo set (invented monitors, January 2030), for trying the app without a download.</>
              : <>Data: Prayas (Energy Group) ESMI, Uttar Pradesh, 2016–2019 (historical). January–June 2019 figures are lower
                bounds because of a defect in the published file (see Data &amp; sources).</>}
          </p>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Guided demo</h3>
          <p className="small muted">Opens one {ds?.synthetic ? "SYNTHETIC" : "real"} location-month chosen by a fixed, documented rule (shown on the next page).
            It is one example, not a typical month.</p>
          <button className="primary" onClick={startDemo} disabled={demoBusy} data-testid="guided-demo">
            {demoBusy ? "Opening…" : "Start guided demo"}
          </button>
          {demoError && <div style={{ marginTop: 8 }}><ErrorBox error={demoError} what="the demo preset" /></div>}
        </div>
      </section>

      <h2>Choose a monitor</h2>
      {states.error && <ErrorBox error={states.error} what="the list of states" />}
      <div className="row">
        <label className="field">State
          <select value={state} onChange={(e) => { setState(e.target.value); setDistrict(""); setLocId(null); }} data-testid="state-select">
            <option value="">All states in scope</option>
            {(states.data || []).map((s) => <option key={s.state_name} value={s.state_name}>{s.state_name} ({s.locations})</option>)}
          </select>
        </label>
        <label className="field">District
          <select value={district} onChange={(e) => { setDistrict(e.target.value); setLocId(null); }} data-testid="district-select">
            <option value="">All districts</option>
            {districts.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="field">Search a location
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={ds?.synthetic ? "e.g. Synthpur" : "e.g. Lucknow"} data-testid="location-search" />
        </label>
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          {locs.loading && !locs.data ? <Skeleton label="locations" /> : locs.error ? <ErrorBox error={locs.error} what="locations" /> : (
            shown.length === 0 ? <p className="muted">No monitored location matches. Clear the search or pick another district.</p> : (
              <div className="scroll">
                <table className="data" data-testid="location-table">
                  <thead><tr><th className="l">Location</th><th className="l">District</th><th>Months (comparable)</th><th>Coverage</th></tr></thead>
                  <tbody>
                    {shown.map((l) => (
                      <tr key={l.location_id} className="clickable" tabIndex={0} aria-selected={locId === l.location_id}
                          onClick={() => setLocId(l.location_id)} onKeyDown={(e) => e.key === "Enter" && setLocId(l.location_id)}>
                        <td className="l">{l.display_name}{l.is_offline && <span className="muted small"> (monitoring ended)</span>}</td>
                        <td className="l">{l.district}</td>
                        <td>{l.months_in_window} ({l.comparable_months})</td>
                        <td>{fmtPct(l.coverage_window)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
        </div>
        <div className="card">
          {!locId ? <p className="muted">Select a location to see its months.</p> : loc.loading && !loc.data ? <Skeleton label="months" /> :
            loc.error ? <ErrorBox error={loc.error} what="the location" /> : loc.data && (
              <>
                <h3 style={{ marginTop: 0 }}>{loc.data.display_name}</h3>
                <p className="small muted">{loc.data.district}, {loc.data.state_name} · {loc.data.source_category} · {loc.data.connection_type}</p>
                <div className="scroll">
                  <table className="data" data-testid="month-table">
                    <thead><tr><th className="l">Month</th><th>Interruptions</th><th>Outage hours (min.)</th><th>Coverage</th></tr></thead>
                    <tbody>
                      {loc.data.months.map((m) => (
                        <tr key={m.month_key} className="clickable" tabIndex={0}
                            onClick={() => nav(`/location/${locId}/${m.month_key}`)}
                            onKeyDown={(e) => e.key === "Enter" && nav(`/location/${locId}/${m.month_key}`)}>
                          <td className="l">{m.month_key} {m.is_comparable ? <span className="badge ok">comparable</span> : <span className="badge warn">low coverage</span>}
                            {m.data_warning && <span className="badge warn" title="Source-file defect: outage figures are lower bounds">lower bound</span>}</td>
                          <td>{m.interruptions}</td><td>{fmtHours(m.outage_min_lower)}</td><td>{fmtPct(m.coverage_calendar)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
        </div>
      </div>
    </>
  );
}
