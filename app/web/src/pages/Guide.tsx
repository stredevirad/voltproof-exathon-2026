import { Link, useNavigate } from "react-router-dom";
import { withDs } from "../api";
import { useDataset } from "../ui";

/** "Start here": how to use VoltProof, in plain words, for someone who has never seen it (Part 4). The wording follows
 *  the same rules as every page: measured is not inferred, coincidence is not cause, no legal claims. */
export default function Guide() {
  const ds = useDataset();
  const nav = useNavigate();
  const kind = ds?.kind;
  return (
    <div className="guide" data-testid="guide">
      <h1>How to use VoltProof</h1>
      <p className="lead">Start here. This page explains, in plain words, what VoltProof shows and how to read it.
        It takes about five minutes.</p>
      <p><button type="button" onClick={() => nav(withDs("/?tour=1"))} data-testid="guide-open-tour">
        Show the short tour of the start page</button></p>

      <section data-testid="guide-what">
        <h2>1. What VoltProof does</h2>
        <p>A small monitor plugged into a socket records the voltage every minute. VoltProof reads those records and
          shows when the power was off or weak, for how long, and how sure each answer is. Every number can be traced
          back to the line of the source file it came from, and to the database steps that computed it.</p>
        <p data-testid="guide-data">
          {kind === "upload"
            ? <>The data on these pages: your uploaded file “{ds?.upload?.file_name}”, which VoltProof has not verified.</>
            : kind === "synthetic"
            ? <>The data on these pages: the SYNTHETIC demo set, invented monitors and readings that show how VoltProof
                works. No figure here describes real electricity supply.</>
            : kind === "real"
            ? <>The data on these pages: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), Uttar
                Pradesh, 2016–2019. These are historical records; they show a method, not today's supply.</>
            : null}
        </p>
      </section>

      <section data-testid="guide-colours">
        <h2>2. What the colours mean</h2>
        <p>Every minute is put in one class by the voltage the monitor recorded (Prayas's classes):</p>
        <ul className="plain-list">
          <li><span className="swatch outage" /> <b>No supply (a power cut):</b> 130 V or less. A run of these minutes is
            one outage, also called an interruption.</li>
          <li><span className="swatch low" /> <b>Low voltage:</b> 131–204 V, below the normal range.</li>
          <li><span className="swatch" /> <b>Normal:</b> 205–270 V.</li>
          <li><span className="swatch high" /> <b>High voltage:</b> above 270 V.</li>
          <li><span className="swatch nodata" /> <b>No reading:</b> the monitor recorded nothing for that minute.
            VoltProof never counts a missing minute as a power cut.</li>
        </ul>
        <p>On a month's calendar, darker orange means more hours without supply that day. Each square shows the day of
          the month and the outage hours (at least) for that day. A hatched square marked “low data” is a day with less
          than 90% of its minutes read.</p>
      </section>

      <section data-testid="guide-pick">
        <h2>3. Pick a place and a month</h2>
        <p>On the <Link to={withDs("/")}>start page</Link>, choose a state and a district, then a monitor (one monitored
          location), then a month. Or press “Start guided demo” to open one example month chosen by a fixed rule.</p>
        <p>A month with more than 90% of its minutes read is “comparable”: it can be compared with other months and
          other monitors. Months with fewer minutes read are shown, but not compared.</p>
      </section>

      <section data-testid="guide-day">
        <h2>4. Read a month and a day</h2>
        <p>The month page leads with “Outage time (at least)”: the hours of power cuts, counted only in minutes that
          have a reading. When a cut borders minutes without a reading, it may have lasted longer; the “up to” figure
          shows how long it could have been. The headline always uses the lower figure.</p>
        <p>Select a day on the calendar to see its minutes. The grey line is the recorded voltage and breaks where there
          is no reading; orange blocks are power cuts; hatched blocks are minutes without a reading. Select a block, or
          a time in the table below the chart, to open that outage's evidence: its first and last minute, how certain
          its start and end are, and the source file lines.</p>
        <ul data-testid="guide-certainty">
          <li><b>Exact:</b> the minute next to the cut was measured with supply.</li>
          <li><b>Bounded:</b> the minutes next to the cut have no reading, so it may have started earlier or ended later.</li>
          <li><b>Censored:</b> monitoring started or ended during the cut, so its true start or end is not known.</li>
        </ul>
      </section>

      <section data-testid="guide-shared">
        <h2>5. Did other monitors lose supply too?</h2>
        <p>When monitors in the same district lose supply within 2 minutes of each other, VoltProof marks a potential
          shared supply event. It means the cuts started at about the same time, nothing more. Coincidence is not
          cause: a shared upstream cause is possible, but a fault inside one building, a monitor fault or chance can
          produce the same pattern. VoltProof does not identify any equipment.</p>
        <p>The chance comparison shows how many such coincidences chance alone would give (how it is worked out is in
          the <Link to={withDs("/methodology")}>Methodology</Link>). It compares timing only; it does not say why supply
          was lost.</p>
      </section>

      <section data-testid="guide-report">
        <h2>6. Download an evidence report</h2>
        <p>On a month page, press “Generate evidence report”. You get a PDF (and the same report as a web page, and the
          numbers as a data file) with the calendar, every outage and how certain it is, potential shared supply
          events, data quality, the method, and an appendix that traces each number to the source files, the SQL that
          computed it and the database statement that ran it. It is an evidence-analysis aid, not legal advice or an
          official determination.</p>
      </section>

      <section data-testid="guide-limits">
        <h2>7. What VoltProof can and cannot tell you</h2>
        <div className="grid-2">
          <div className="card">
            <h3 style={{ marginTop: 0 }}>It can show</h3>
            <ul>
              <li>when the voltage at the monitor showed a power cut, low voltage or high voltage, minute by minute;</li>
              <li>how long each cut lasted at least, and how certain its start and end are;</li>
              <li>how much of the time has no reading;</li>
              <li>which cuts started at about the same time at other monitors in the same district;</li>
              <li>a report you can download that traces every number back to its source.</li>
            </ul>
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>It cannot tell you</h3>
            <ul>
              <li>why the power went off, or which equipment was involved;</li>
              <li>what happened in minutes without a reading;</li>
              <li>anything beyond the one socket the monitor is plugged into: a cut there may also come from the
                building or the monitor itself;</li>
              {kind === "upload" && <li>whether an uploaded file is genuine;</li>}
              <li>whether anything is owed to anyone: VoltProof is an evidence-analysis aid, not legal advice or an
                official determination.</li>
            </ul>
          </div>
        </div>
        <p className="small muted">More detail: <Link to={withDs("/methodology")}>Methodology</Link> (every rule and its
          source) and <Link to={withDs("/sources")}>Data &amp; sources</Link> (the files and their checksums).</p>
      </section>

      <section data-testid="guide-upload">
        <h2>8. Use your own data</h2>
        <p>On <Link to="/upload">Upload your data</Link> you can add minute-by-minute voltage readings from your own
          monitor: the ESMI layout (one row per hour, 60 minute columns, also as a published “.tab” file), or one
          reading per line (time and voltage). The file stays on this computer and is never sent anywhere. VoltProof
          checks it, asks you about anything it cannot decide from the data (such as the date order), then analyses it
          with exactly the same steps. Every page then says “Uploaded data — not verified by VoltProof”, and you can
          delete the upload with one button. Only upload data you have the right to use.</p>
      </section>
    </div>
  );
}
