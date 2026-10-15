import { useEffect, useState } from "react";
import { ApiError, uploads, type UploadPreview, type UploadRec } from "../api";

// Plain words for the SQL steps that run inside Exasol while an upload is built.
const STEP_TEXT: Record<string, string> = {
  "u20_validate.sql": "checking the file", "u30_canonical.sql": "turning it into standard rows",
  "020_location.sql": "reading the monitor list", "030_unpivot.sql": "splitting hours into minutes",
  "040_clean.sql": "setting repeated readings aside", "050_segments.sql": "classifying every minute",
  "060_events.sql": "finding outage events", "070_uncertain_claims.sql": "bounding uncertain edges",
  "080_daily.sql": "adding up each day", "090_monthly.sql": "adding up each month",
  "095_quality.sql": "summarising data quality", "100_coincidence.sql": "checking for shared supply events",
};
const ORDER_TEXT: Record<string, string> = {
  YMD: "Year first (2018-06-01 18:42)", DMY: "Day first (01-06-2018 18:42)", MDY: "Month first (06/01/2018 18:42)",
};
const MB = 1_000_000;

type LongMap = { location_col: number | null; ts_col: number | null; value_col: number | null; order: string;
                 single_monitor_name: string };
type Typed = Record<string, { district: string; state: string }>;

function message(e: unknown): string {
  return e instanceof ApiError || e instanceof Error ? e.message : String(e);
}

export default function Upload() {
  const [list, setList] = useState<UploadRec[] | null>(null);
  const [rec, setRec] = useState<UploadRec | null>(null);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [readings, setReadings] = useState<File | null>(null);
  const [locations, setLocations] = useState<File | null>(null);
  const [sent, setSent] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [long, setLong] = useState<LongMap>({ location_col: null, ts_col: null, value_col: null, order: "DMY",
                                               single_monitor_name: "" });
  const [answers, setAnswers] = useState<Record<string, string | number>>({});
  const [typed, setTyped] = useState<Typed>({});
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);

  const refreshList = () => uploads.list().then(setList).catch(() => setList([]));
  useEffect(() => { refreshList(); }, []);

  // After an analysis starts, ask for its progress every second until it is ready or failed (the first answers may
  // still say "validated": the build starts in the background a moment later)
  useEffect(() => {
    if (!watching || !rec) return;
    const t = window.setInterval(() => {
      uploads.status(rec.id).then((r) => {
        setRec(r);
        if (r.status === "ready" || r.status === "failed") { setWatching(false); refreshList(); }
      }).catch(() => {});
    }, 1000);
    return () => window.clearInterval(t);
  }, [watching, rec?.id]);

  async function run<T>(what: string, f: () => Promise<T>): Promise<T | undefined> {
    setBusy(what);
    setError(null);
    try {
      return await f();
    } catch (e) {
      setError(message(e));
      return undefined;
    } finally {
      setBusy(null);
    }
  }

  async function startUpload() {
    if (!readings) return;
    const ok = await run("Sending the file to VoltProof on this computer…", async () => {
      const r = await uploads.start();
      setSent(0);
      await uploads.putFile(r.id, "readings", readings, setSent);
      if (locations) await uploads.putFile(r.id, "locations", locations, () => {});
      const p = await uploads.preview(r.id);
      setPreview(p);
      setRec(await uploads.status(r.id));
      if (p.suggest) setLong({ location_col: p.suggest.location_col, ts_col: p.suggest.ts_col,
                               value_col: p.suggest.value_col, order: p.suggest.order, single_monitor_name: "" });
      return true;
    });
    setSent(null);
    if (!ok) refreshList();
  }

  function mapping() {
    const m: Record<string, unknown> = { ...answers };
    if (preview?.layout === "long") m.long = { ...long, order_confirmed: "long_order" in answers,
                                               order: (answers.long_order as string) || long.order };
    const t = Object.entries(typed).filter(([, v]) => v.district.trim() && v.state.trim())
      .map(([name, v]) => ({ name, district: v.district, state: v.state }));
    if (t.length) m.typed_locations = t;
    return m;
  }

  async function check() {
    if (!rec) return;
    await run("Checking the file inside Exasol…", async () => setRec(await uploads.validate(rec.id, mapping())));
  }

  async function build() {
    if (!rec) return;
    await run("Starting the build…", async () => {
      await uploads.build(rec.id);
      setRec({ ...rec, status: "building", progress: { step: null, done: 0, total: 0 } });
      setWatching(true);
    });
  }

  async function remove(id: string) {
    await run("Deleting…", async () => {
      await uploads.remove(id);
      if (rec?.id === id) { setRec(null); setPreview(null); }
      setConfirmDelete(null);
      await refreshList();
    });
  }

  function reset() {
    setRec(null); setPreview(null); setReadings(null); setLocations(null); setAnswers({}); setTyped({}); setError(null);
  }

  const v = rec?.validation;
  const header = preview?.header || [];
  const step = rec?.progress?.step ? STEP_TEXT[rec.progress.step] || rec.progress.step : "starting";

  return (
    <>
      <h1>Upload your own voltage data</h1>
      <p className="muted" style={{ maxWidth: 820 }}>
        VoltProof can analyse your own minute-by-minute voltage readings with exactly the same method it uses for the
        Prayas ESMI data: every step runs as SQL inside the Exasol database on this computer.
      </p>
      <div className="note small" data-testid="upload-privacy" style={{ maxWidth: 820 }}>
        <b>Your file stays on this computer.</b> It is stored in a local folder and analysed in the local database; it is
        never sent anywhere. You can delete it, and everything made from it, with one button. Only upload a file you have
        the right to use.
      </div>

      {error && <div className="error" role="alert" data-testid="upload-error" style={{ marginTop: 12 }}>
        <strong>That did not work.</strong> {error}</div>}
      {busy && <p role="status" className="muted" data-testid="upload-busy">{busy}
        {sent != null && ` ${Math.round(100 * sent)}%`}</p>}

      {!rec && (
        <section className="card" style={{ marginTop: 16 }}>
          <h2 style={{ marginTop: 0 }}>1. Choose your files</h2>
          <p className="small">
            <b>Readings</b> (required): a CSV file of 1-minute voltage readings, either in the ESMI layout (one row per
            monitor and hour: Location name, Date, Hour, Min 0 … Min 59, as in the Prayas files, also as the Harvard
            Dataverse .tab file) or with one reading per line (a monitor, a date and time, and a voltage).
            Up to {150} MB per file, because larger files can exhaust the memory of a 16 GB laptop.
          </p>
          <label className="field">Readings file
            <input type="file" accept=".csv,.tab,.txt,text/csv" data-testid="upload-readings"
                   onChange={(e) => setReadings(e.target.files?.[0] || null)} />
          </label>
          <p className="small" style={{ marginTop: 12 }}>
            <b>Locations</b> (optional): the ESMI location file (Location name, From date, To date, District, State,
            Category, Connection Type). Without it, you type the district and state of each monitor in step 3.
          </p>
          <label className="field">Location file
            <input type="file" accept=".csv,.tab,.txt,text/csv" data-testid="upload-locations"
                   onChange={(e) => setLocations(e.target.files?.[0] || null)} />
          </label>
          {readings && readings.size > 150 * MB && <p className="error">This file is larger than 150 MB; split it
            into smaller files (for example by month).</p>}
          <div style={{ marginTop: 12 }}>
            <button className="primary" disabled={!readings || !!busy || (readings?.size || 0) > 150 * MB}
                    onClick={startUpload} data-testid="upload-send">Upload and preview</button>
          </div>
        </section>
      )}

      {rec && preview && rec.status !== "ready" && rec.status !== "building" && (
        <section className="card" style={{ marginTop: 16 }} data-testid="upload-preview">
          <h2 style={{ marginTop: 0 }}>2. Check how VoltProof reads your file</h2>
          <p className="small"><b>{rec.readings?.name}</b> ({((rec.readings?.bytes || 0) / MB).toFixed(1)} MB).{" "}
            {preview.explain}</p>
          <div className="scroll" style={{ maxHeight: 260 }}>
            <table className="data small">
              <thead><tr>{header.slice(0, 12).map((h, i) => <th key={i} className="l">{h}</th>)}
                {header.length > 12 && <th className="l">… {header.length - 12} more</th>}</tr></thead>
              <tbody>{preview.rows.slice(0, 20).map((r, i) => (
                <tr key={i}>{r.slice(0, 12).map((c, j) => <td key={j} className="l">{c}</td>)}
                  {header.length > 12 && <td className="l">…</td>}</tr>))}</tbody>
            </table>
          </div>
          {preview.layout === "long" && (
            <div className="row" style={{ marginTop: 12 }} data-testid="upload-mapping">
              <label className="field">Monitor column
                <select value={long.location_col ?? ""} data-testid="map-location"
                        onChange={(e) => setLong({ ...long, location_col: e.target.value === "" ? null : Number(e.target.value) })}>
                  <option value="">(no monitor column: one monitor)</option>
                  {header.map((h, i) => <option key={i} value={i}>{h}</option>)}
                </select>
              </label>
              {long.location_col == null && <label className="field">Name of the monitor
                <input value={long.single_monitor_name} data-testid="map-single-name" maxLength={120}
                       onChange={(e) => setLong({ ...long, single_monitor_name: e.target.value })} /></label>}
              <label className="field">Date and time column
                <select value={long.ts_col ?? ""} data-testid="map-time"
                        onChange={(e) => setLong({ ...long, ts_col: Number(e.target.value) })}>
                  <option value="" disabled>choose…</option>
                  {header.map((h, i) => <option key={i} value={i}>{h}</option>)}
                </select>
              </label>
              <label className="field">Voltage column
                <select value={long.value_col ?? ""} data-testid="map-voltage"
                        onChange={(e) => setLong({ ...long, value_col: Number(e.target.value) })}>
                  <option value="" disabled>choose…</option>
                  {header.map((h, i) => <option key={i} value={i}>{h}</option>)}
                </select>
              </label>
              <label className="field">How dates are written
                <select value={long.order} data-testid="map-order" onChange={(e) => setLong({ ...long, order: e.target.value })}>
                  {Object.entries(ORDER_TEXT).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
                </select>
              </label>
            </div>
          )}
          <p className="small muted">Readings must be one per minute. Clock times are read as local time, exactly as
            written; a time-zone suffix such as +05:30 is not accepted.</p>
          <button className="primary" onClick={check} disabled={!!busy} data-testid="upload-check">
            {v ? "Check again" : "Check the file"}</button>{" "}
          <button onClick={() => remove(rec.id)} disabled={!!busy}>Cancel and delete</button>
        </section>
      )}

      {rec && v && rec.status !== "ready" && rec.status !== "building" && (
        <section className="card" style={{ marginTop: 16 }} data-testid="upload-summary">
          <h2 style={{ marginTop: 0 }}>3. What VoltProof found</h2>
          <p>{v.rows.toLocaleString("en-IN")} lines · {v.monitors} monitor(s) ·{" "}
            {v.first_day ? `${v.first_day} to ${v.last_day}` : "dates not read yet"}
            {v.states.length > 0 && ` · ${v.states.join(", ")}`}
            {v.typical_voltage != null && ` · typical reading ${v.typical_voltage} V`}</p>
          {v.refusals.length > 0 && (
            <div className="error" role="alert" data-testid="upload-refusals">
              <strong>This file cannot be analysed:</strong>
              <ul>{v.refusals.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
          {v.questions.map((q) => (
            <fieldset key={q.key} className="note" data-testid={`question-${q.key}`} style={{ marginTop: 8 }}>
              <legend><b>{q.text}</b></legend>
              {q.options?.map((o) => (
                <label key={String(o.value)} style={{ display: "block" }}>
                  <input type="radio" name={q.key} checked={answers[q.key] === o.value}
                         onChange={() => setAnswers({ ...answers, [q.key]: o.value })} /> {o.label}
                </label>
              ))}
              {q.monitors && (
                <table className="data small"><thead><tr><th className="l">Monitor</th><th className="l">District</th>
                  <th className="l">State</th></tr></thead>
                  <tbody>{q.monitors.map((name) => (
                    <tr key={name}><td className="l">{name}</td>
                      <td className="l"><input aria-label={`District of ${name}`} value={typed[name]?.district || ""} maxLength={200}
                        onChange={(e) => setTyped({ ...typed, [name]: { state: typed[name]?.state || "", district: e.target.value } })} /></td>
                      <td className="l"><input aria-label={`State of ${name}`} value={typed[name]?.state || ""} maxLength={200}
                        onChange={(e) => setTyped({ ...typed, [name]: { district: typed[name]?.district || "", state: e.target.value } })} /></td>
                    </tr>))}</tbody></table>
              )}
            </fieldset>
          ))}
          {v.set_aside.length > 0 && (
            <div className="note small" data-testid="upload-set-aside" style={{ marginTop: 8 }}>
              <b>Set aside, not analysed</b> (missing or unreadable lines are never counted as power cuts):
              <ul>{v.set_aside.map((a, i) => <li key={i}>{a.rows.toLocaleString("en-IN")} {a.what}</li>)}</ul>
            </div>
          )}
          {v.warnings.map((w, i) => <p key={i} className="small">{w}</p>)}
          {v.questions.length > 0 && <button onClick={check} disabled={!!busy} data-testid="upload-recheck">
            Use my answers and check again</button>}{" "}
          <button className="primary" onClick={build} disabled={!!busy || !v.ready_to_build} data-testid="upload-build">
            Analyse this file</button>
          <p className="small muted">Analysing takes from a few seconds to a few minutes; the app may be slower
            meanwhile. Only one analysis can run at a time.</p>
        </section>
      )}

      {rec?.status === "building" && (
        <section className="card" style={{ marginTop: 16 }} data-testid="upload-progress">
          <h2 style={{ marginTop: 0 }}>4. Analysing inside Exasol</h2>
          <progress max={rec.progress?.total || 1} value={rec.progress?.done || 0} style={{ width: "100%" }} />
          <p className="small">Step {rec.progress?.done || 0} of {rec.progress?.total || "…"}: {step}</p>
        </section>
      )}

      {rec?.status === "failed" && (
        <div className="error" role="alert" style={{ marginTop: 16 }} data-testid="upload-failed">
          <strong>The analysis did not finish.</strong> {rec.error}{" "}
          <button onClick={() => remove(rec.id)}>Delete this upload</button>
        </div>
      )}

      {rec?.status === "ready" && rec.build && (
        <section className="card" style={{ marginTop: 16 }} data-testid="upload-done">
          <h2 style={{ marginTop: 0 }}>Done: your file has been analysed</h2>
          <p>{rec.build.locations} monitor(s), {rec.build.minutes.toLocaleString("en-IN")} measured minutes,{" "}
            {rec.build.events.toLocaleString("en-IN")} outage events, {rec.build.shared_events} potential shared supply
            event(s), in {rec.build.seconds} s.</p>
          <p className="small muted" data-testid="upload-same-method">Same method as every dataset here:{" "}
            {rec.build.statements} SQL statements ran inside Exasol, and every one was matched to Exasol's own audit log
            ({rec.build.provenance.matches} matched, {rec.build.provenance.different} different,{" "}
            {rec.build.provenance.missing} missing).</p>
          <a className="button primary" href={`/?ds=${encodeURIComponent(rec.schema)}`} data-testid="upload-open">
            Open this dataset</a>{" "}
          <button onClick={reset}>Upload another file</button>
        </section>
      )}

      <h2 style={{ marginTop: 24 }}>Your uploads on this computer</h2>
      {!list ? <p className="muted">Loading…</p> : list.length === 0 ? <p className="muted">None yet.</p> : (
        <div className="card scroll">
          <table className="data" data-testid="upload-list">
            <thead><tr><th className="l">File</th><th className="l">Uploaded</th><th className="l">State</th><th className="l" /></tr></thead>
            <tbody>{list.map((u) => (
              <tr key={u.id}>
                <td className="l">{u.readings?.name || "(no file yet)"}</td>
                <td className="l">{u.created_at}</td>
                <td className="l">{u.status === "ready" ? "analysed" : u.status === "failed" ? "did not finish" : "not analysed yet"}</td>
                <td className="l">
                  {u.status === "ready" && <><a href={`/?ds=${encodeURIComponent(u.schema)}`}>Open</a>{" · "}</>}
                  {confirmDelete === u.id ? (
                    <span data-testid="delete-confirm">Delete this upload and everything made from it?{" "}
                      <button onClick={() => remove(u.id)} disabled={!!busy} data-testid="delete-yes">Yes, delete</button>{" "}
                      <button onClick={() => setConfirmDelete(null)}>No</button></span>
                  ) : <button onClick={() => setConfirmDelete(u.id)} disabled={u.status === "building"}
                              data-testid={`delete-${u.id}`}>Delete</button>}
                </td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </>
  );
}
