import { useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";

export type Dataset = { synthetic: boolean; dataset_label: string };
let datasetPromise: Promise<Dataset> | null = null;

/** Which data this build holds (real ESMI data or the SYNTHETIC demo set, D-033); fetched once per page load. */
export function useDataset(): Dataset | null {
  const [ds, setDs] = useState<Dataset | null>(null);
  useEffect(() => {
    if (!datasetPromise) datasetPromise = api.meta().then((m) => ({ synthetic: !!m.synthetic, dataset_label: m.dataset_label }));
    datasetPromise.then(setDs).catch(() => setDs(null));
  }, []);
  return ds;
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
  if (status === 404) next = "This item does not exist in the analysed data. Go back to the start page and pick a monitor and month.";
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

export function Kpi({ label, value, sub, testId }: { label: string; value: ReactNode; sub?: ReactNode; testId?: string }) {
  return (
    <div className="kpi" data-testid={testId}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
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
