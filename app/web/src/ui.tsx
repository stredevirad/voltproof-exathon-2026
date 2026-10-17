import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import { api, ApiError, CURRENT_DS, uploads, type DatasetItem } from "./api";

export type Dataset = {
  synthetic: boolean; dataset_label: string; kind: "real" | "synthetic" | "upload";
  upload?: { file_name: string; sha256: string; uploaded_at: string; bytes: number };
};
let datasetPromise: Promise<Dataset> | null = null;

/** Which data this page shows: real Prayas ESMI data, the SYNTHETIC demo set (D-033) or an upload; fetched once per
 *  page load (a page shows one dataset; switching loads the start page again). */
export function useDataset(): Dataset | null {
  const [ds, setDs] = useState<Dataset | null>(null);
  useEffect(() => {
    if (!datasetPromise) datasetPromise = api.meta().then((m) => ({
      synthetic: !!m.synthetic, dataset_label: m.dataset_label,
      kind: m.dataset_kind || (m.synthetic ? "synthetic" : "real"), upload: m.upload }));
    datasetPromise.then(setDs).catch(() => setDs(null));
  }, []);
  return ds;
}

/** Shown on every page while the app shows an uploaded file. */
export function UploadBanner() {
  const ds = useDataset();
  if (ds?.kind !== "upload") return null;
  return (
    <div className="synthetic-banner" role="status" data-testid="upload-banner">
      <strong>Uploaded data — not verified by VoltProof.</strong> Your file “{ds.upload?.file_name}”, analysed with the
      same method as every dataset here. Nobody has checked where the readings came from.{" "}
      <a href="/upload">Your uploads</a>
    </div>
  );
}

export function datasetName(d: DatasetItem): string {
  if (d.kind === "real") return "Prayas ESMI data (real, Uttar Pradesh 2016–2019)";
  if (d.kind === "synthetic") return "SYNTHETIC demo set (invented monitors)";
  return `Your upload: ${d.file_name || "file"}`;
}

/** Choose which dataset the app shows. Switching opens the start page of that dataset. */
export function DatasetSwitcher() {
  const [items, setItems] = useState<DatasetItem[] | null>(null);
  useEffect(() => { uploads.datasets().then(setItems).catch(() => setItems(null)); }, []);
  if (!items || items.length < 2) return null;
  const current = CURRENT_DS || items.find((d) => d.default)?.ds || "";
  return (
    <label className="ds-switch">Data
      <select value={current} data-testid="dataset-select" onChange={(e) => {
        const d = items.find((x) => x.ds === e.target.value);
        window.location.assign(d && !d.default ? `/?ds=${encodeURIComponent(d.ds)}` : "/");
      }}>
        {items.map((d) => <option key={d.ds} value={d.ds}>{datasetName(d)}</option>)}
      </select>
    </label>
  );
}

/** Shown on every page while the app runs on the SYNTHETIC demo set. */
export function SyntheticBanner() {
  const ds = useDataset();
  if (!ds?.synthetic) return null;
  return (
    <div className="synthetic-banner" role="status" data-testid="synthetic-banner">
      <strong>SYNTHETIC DEMO DATA</strong>: invented monitors and readings, so VoltProof can be tried without a
      download. Not ESMI data; no figure here describes real electricity supply. To analyse the real data, see the
      README section "Real data".
    </div>
  );
}

/** Load data; keep the previous result visible (dimmed) while refetching instead of flashing a skeleton. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    load().then((d) => { if (alive) { setData(d); setLoading(false); } })
      .catch((e) => { if (alive) { setError(e); setLoading(false); } });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

export function Skeleton({ height = 160, label }: { height?: number; label: string }) {
  return <div className="skeleton" style={{ height }} role="status" aria-label={`Loading ${label}`} />;
}

export function ErrorBox({ error, what }: { error: Error; what: string }) {
  const status = error instanceof ApiError ? error.status : 0;
  let next = "Check that the VoltProof server is running (scripts\\start.ps1) and reload the page.";
  if (status === 404) next = CURRENT_DS && /dataset not found/.test(error.message)
    ? "This dataset is no longer on this computer (it may have been deleted). Open the start page to pick another."
    : "This item does not exist in the analysed data. Go back to the start page and pick a monitor and month.";
  if (status === 503) next = "Start the database with scripts\\exa.ps1 start, build the data with scripts\\load.ps1, then reload.";
  return (
    <div className="error" role="alert">
      <strong>Could not load {what}.</strong> <span className="muted">{error.message}</span>
      <div style={{ marginTop: 6 }}>{next}</div>
    </div>
  );
}

/** Known defect in the source file for this period (config/source_files.yaml, D-031). Presentation only. */
export function DataWarning({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <div className="banner warn" role="note" data-testid="data-warning">
      <strong>Lower bounds: known defect in the source file.</strong> {text}
    </div>
  );
}

/** A number tile. `lead` marks the one number the page leads with; `plain` is a one-line explanation in everyday
 *  words under the number. */
export function Kpi({ label, value, sub, plain, lead, testId }: { label: string; value: ReactNode; sub?: ReactNode;
                     plain?: ReactNode; lead?: boolean; testId?: string }) {
  return (
    <div className={lead ? "kpi lead-tile" : "kpi"} data-testid={testId}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
      {plain && <div className="plain" data-testid={testId && `${testId}-plain`}>{plain}</div>}
    </div>
  );
}

/** Click handler for a table row whose first cell holds the real link or button (audit F-14: keyboard and
 *  screen-reader users reach that element; a mouse click anywhere else on the row does the same). */
export function rowClick(go: () => void) {
  return (ev: MouseEvent) => {
    if (!(ev.target as HTMLElement).closest("a, button")) go();
  };
}

export function StateLegend() {
  return (
    <div className="chips small" aria-label="Legend">
      <span className="state"><span className="swatch outage" />No supply (≤ 130 V)</span>
      <span className="state"><span className="swatch low" />Low voltage (131–204 V)</span>
      <span className="state"><span className="swatch high" />High voltage (&gt; 270 V)</span>
      <span className="state"><span className="swatch nodata" />No reading — not counted as outage</span>
    </div>
  );
}

export function Certainty({ value }: { value: string }) {
  const text: Record<string, string> = {
    exact: "exact (neighbouring minute measured with supply)",
    bounded: "bounded (neighbouring minutes have no reading)",
    censored: "censored (monitoring started or ended during the outage)",
  };
  return <span title={text[value] || value}>{value}</span>;
}
