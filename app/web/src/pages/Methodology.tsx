import { api } from "../api";
import { ErrorBox, Skeleton, useApi } from "../ui";

export default function Methodology() {
  const { data, error, loading } = useApi(() => api.meta(), []);
  if (loading && !data) return <Skeleton label="the methodology" />;
  if (error) return <ErrorBox error={error} what="the methodology" />;
  const p: Record<string, any> = Object.fromEntries((data.params as any[]).map((r) => [r.name, r.num_value ?? r.str_value]));
  return (
    <>
      <h1>Methodology</h1>
      <p className="muted">Method version {data.method_version} · app {data.git_commit}. The full rules (R-1 to R-21) are in docs/METHODOLOGY.md.
        Every step below runs as versioned SQL inside Exasol; numbers in the app are read from the tables it produces.</p>
      <h2>Measured vs inferred</h2>
      <ul>
        <li><b>Measured:</b> a minute with a valid voltage reading. Outage minutes, low- and high-voltage minutes and coverage count only measured minutes.</li>
        <li><b>Inferred:</b> upper bounds. Where an outage borders missing readings, the missing minutes next to it (at most {p["events.max_uncertain_extension_minutes"]} per side)
          <i> may</i> also have been outage. They are shown as a range and never in the headline.</li>
        <li><b>Missing readings are never counted as outage.</b> Prayas: "Missing data should be interpreted as unavailable data and not as interruption."</li>
      </ul>
      <h2>Voltage classes</h2>
      <table className="data card" style={{ maxWidth: 720 }}>
        <thead><tr><th className="l">Class</th><th className="l">Rule (recorded volts v)</th></tr></thead>
        <tbody>
          <tr><td className="l"><span className="swatch outage" /> No supply</td><td className="l">v ≤ {p["classification.outage_max_v"]} V</td></tr>
          <tr><td className="l"><span className="swatch low" /> Low</td><td className="l">{p["classification.outage_max_v"]} &lt; v &lt; {p["classification.normal_min_v"]} V</td></tr>
          <tr><td className="l">Normal</td><td className="l">{p["classification.normal_min_v"]} ≤ v ≤ {p["classification.normal_max_v"]} V</td></tr>
          <tr><td className="l"><span className="swatch high" /> High</td><td className="l">v &gt; {p["classification.normal_max_v"]} V</td></tr>
        </tbody>
      </table>
      <p className="small muted">Source: Prayas (Energy Group), "How does ESMI work?", {p["classification.source_url"]} (retrieved {p["classification.retrieved_on"]}).</p>
      <h2>Events, certainty and aggregates</h2>
      <ul>
        <li>An outage event is a run of consecutive "no supply" minutes. Its start/end is <i>exact</i> if the neighbouring minute was measured, <i>bounded</i> if it has no reading, and <i>censored</i> at the start or end of monitoring.</li>
        <li>An event counts as an interruption from {p["events.interruption_min_minutes"]} minute(s). Gap bridging is {Number(p["events.gap_bridge_max_minutes"]) > 0 ? `on (gaps up to ${p["events.gap_bridge_max_minutes"]} min)` : "off"}.</li>
        <li>Minutes are attributed to the calendar day they fall on; an interruption is counted on the day it starts. Evening = {p["windows.evening_start_hour"]}:00–{p["windows.evening_end_hour_exclusive"]}:00.</li>
        <li>A month is <i>comparable</i> when more than {100 * Number(p["coverage.comparable_month_min_coverage_exclusive"])}% of its calendar minutes were read (Prayas's Uttar Pradesh method). Other months are shown but not compared.</li>
      </ul>
      <h2>Potential shared supply events</h2>
      <ul>
        <li>Two interruptions at different monitors in the same district are coincident when their starts are at most {p["coincidence.max_start_offset_minutes"]} minutes apart and they overlap by at least {p["coincidence.min_overlap_minutes"]} minute.</li>
        <li>Chance baseline: each monitor's interruptions are shifted by whole days within the month ({p["coincidence.baseline_shifts"]} variants), keeping its time-of-day pattern, and the coincidences are counted again. Only comparable location-months are used.</li>
        <li>These are coincidences, not proof of a common cause.</li>
      </ul>
      <h2>Known limitations</h2>
      <ul>
        <li>A plug-in monitor is not the utility's meter. It sees one socket, and an outage there may also come from the premises or the monitor.</li>
        {data.synthetic
          ? <li>This build runs on SYNTHETIC demo data: invented readings that show the method and describe no real supply.</li>
          : <li>The data are historical (2016–2019 for Uttar Pradesh); they show a method, not today's supply.</li>}
        <li>Monitor accuracy is ±4 V, so readings within 4 V of a class boundary are sensitive.</li>
        <li>Some monitors report a floor value (about 101 V or 99 V) during deep sags; Prayas counts these as no supply, and VoltProof shows the 0 V share separately.</li>
        <li>The published 2019 July–December file lost its hour column and is excluded (see Data &amp; sources).</li>
      </ul>
    </>
  );
}
