// Typed client for the VoltProof API (same origin; FastAPI serves both the API and this app).

export type Loc = {
  location_id: number; display_name: string; source_name: string; is_offline: boolean; district: string;
  state_name: string; source_category: string; connection_type: string; first_ts: string; last_ts: string;
  coverage_window: number; months_in_window: number; comparable_months: number; outage_minutes: number;
};
export type MonthRow = {
  month_key: string; outage_min_lower: number; outage_min_upper: number; interruptions: number;
  coverage_calendar: number; is_comparable: boolean; data_warning: boolean;
};
export type Day = {
  cal_day: string; expected_minutes: number; observed_minutes: number; outage_min_lower: number;
  outage_min_upper: number; outage_zero_minutes: number; low_minutes: number; high_minutes: number;
  evening_outage_lower: number; evening_outage_upper: number; interruptions: number; longest_interruption: number;
};
export type Ev = {
  event_key: string; start_ts: string; end_ts: string; min_duration: number; max_duration: number;
  bridged_minutes?: number; zero_minutes?: number; start_certainty: string; end_certainty: string;
  is_interruption: boolean; group_key: string | null;
};
export type Baseline = {
  district: string; month_key: string; n_locations: number; n_interruptions: number; observed_pairs: number;
  expected_pairs: number; p_value: number; n_shifts: number; comparable_only: boolean;
};
export type MonthData = {
  location: Loc; days: Day[]; events: Ev[]; baseline: Baseline | null; data_warning: string | null;
  month: Day & { month_key: string; calendar_minutes: number; coverage_calendar: number; coverage_window: number;
                 is_comparable: boolean; outage_zero_minutes: number };
};
export type Segment = { seg_no: number; supply_state: string; start_ts: string; end_ts: string; minutes: number };
export type DayData = {
  location: Loc; day: string; daily: Day | null; readings: { ts: string; voltage: number; supply_state: string }[];
  segments: Segment[]; claims: { claim_start: string; claim_end: string; claim_minutes: number; side: string }[];
  events: Ev[]; data_warning: string | null;
};
export type GroupData = {
  group_key: string; district: string; start_ts: string; end_ts: string; n_members: number; n_locations: number;
  n_pairs: number; district_locations_with_interruptions: number; baseline: Baseline | null;
  members: { event_key: string; location_id: number; display_name: string; start_ts: string; end_ts: string;
             offset_from_group_start_min: number; min_duration: number; max_duration: number }[];
};
export type EventData = Ev & {
  location_id: number; display_name: string; district: string; state_name: string; bridged_minutes: number;
  zero_minutes: number; before: Segment | null; after: Segment | null;
  source_lines: { ts: string; voltage: number; file_id: number; line_no: number; file_name: string }[];
  provenance: { step: string; stmt_index: number; sql_file_sha256: string; stmt_sha256: string;
                exa_session_id: number; exa_stmt_id: number; run_id: string;
                exa_duration_s: number | null; exa_temp_db_ram_peak_mib: number | null }[];
  group: GroupData | null; baseline: Baseline | null; data_warning: string | null;
};
export type Demo = { location_id: number; month: string; day: string; event_key: string; group_key: string; rule: string;
                     window_from: string; window_to_exclusive: string };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** The dataset this page shows: the `ds` URL parameter (a schema name from /api/datasets), or null for the server's
 *  own dataset. Fixed for the page's lifetime: switching datasets loads the start page with the new `ds`. */
const DS_PARAM = new URLSearchParams(window.location.search).get("ds");
export const CURRENT_DS: string | null = DS_PARAM && /^[A-Z][A-Z0-9_]{0,39}$/.test(DS_PARAM) ? DS_PARAM : null;

/** `path` (an app or API path) with the current dataset added, so links and requests stay on the same dataset. */
export function withDs(path: string): string {
  if (!CURRENT_DS) return path;
  const [p, hash] = path.split("#");
  return `${p}${p.includes("?") ? "&" : "?"}ds=${encodeURIComponent(CURRENT_DS)}${hash ? "#" + hash : ""}`;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(withDs(path));
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); detail = j.detail || detail; } catch { /* plain text */ }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => get<Record<string, unknown>>("/api/health"),
  meta: () => get<any>("/api/meta"),
  states: () => get<{ state_name: string; locations: number; districts: number }[]>("/api/states"),
  locations: (state?: string, district?: string, q?: string) => {
    const p = new URLSearchParams();
    if (state) p.set("state", state);
    if (district) p.set("district", district);
    if (q) p.set("q", q);
    return get<Loc[]>(`/api/locations?${p}`);
  },
  location: (id: number) => get<Loc & { months: MonthRow[] } & Record<string, any>>(`/api/locations/${id}`),
  month: (id: number, m: string) => get<MonthData>(`/api/locations/${id}/months/${m}`),
  day: (id: number, d: string) => get<DayData>(`/api/locations/${id}/days/${d}`),
  event: (key: string) => get<EventData>(`/api/events/${key}`),
  group: (key: string) => get<GroupData>(`/api/groups/${encodeURIComponent(key)}`),
  demo: () => get<Demo>("/api/demo"),
  report: async (location_id: number, month: string) => {
    const r = await fetch(withDs("/api/reports"), { method: "POST", headers: { "Content-Type": "application/json" },
                                             body: JSON.stringify({ location_id, month }) });
    if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json() as Promise<{ report_id: string; pdf_url: string; html_url: string; json_url: string;
                                 generated_at_ist: string; reused: boolean }>;
  },
};

export type DatasetItem = { ds: string; kind: "real" | "synthetic" | "upload"; default: boolean; upload_id?: string;
                            file_name?: string; uploaded_at?: string; sha256?: string; locations?: number;
                            first_day?: string; last_day?: string };
export type UploadQuestion = { key: string; text: string; options?: { value: string | number; label: string }[];
                               monitors?: string[] };
export type UploadSummary = {
  refusals: string[]; questions: UploadQuestion[]; set_aside: { what: string; rows: number }[]; warnings: string[];
  rows: number; monitors: number; monitor_list: { name: string; rows: number; district: string | null;
  state: string | null; has_location: boolean }[]; first_day: string | null; last_day: string | null;
  states: string[]; typical_voltage: number | null; ready_to_build: boolean; reads_as: string[];
};
export type UploadFile = { name: string; bytes: number; sha256: string; received_at: string };
export type UploadRec = {
  id: string; schema: string; status: "new" | "uploaded" | "validated" | "building" | "ready" | "failed";
  created_at: string; readings: UploadFile | null; locations: UploadFile | null; preview: any; mapping: any;
  validation: UploadSummary | null; error: string | null; progress: { step: string | null; done: number; total: number } | null;
  build: { built_at: string; seconds: number; statements: number; provenance: { matches: number; different: number;
           missing: number }; locations: number; minutes: number; events: number; months: number;
           comparable_months: number; shared_events: number } | null;
};
export type UploadPreview = { layout: "wide" | "long"; sep: string; header: string[]; rows: string[][]; explain: string;
                              suggest?: { location_col: number | null; ts_col: number | null; value_col: number | null;
                                          order: string } };

// Requests that change something carry this header; the server refuses them without it (cross-site guard).
const CHANGE = { "X-VoltProof": "1" };

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, { method, headers: { ...CHANGE, "Content-Type": "application/json" },
                                body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json() as Promise<T>;
}

async function plain<T>(path: string): Promise<T> {  // no dataset parameter: uploads are not tied to one dataset
  const r = await fetch(path);
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json() as Promise<T>;
}

/** Send one file as the request body, reporting progress (0-1). */
function putFile(id: string, role: "readings" | "locations", file: File, onProgress: (f: number) => void): Promise<UploadRec> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("PUT", `/api/uploads/${id}/files/${role}?name=${encodeURIComponent(file.name)}`);
    x.setRequestHeader("X-VoltProof", "1");
    x.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    x.onload = () => {
      let j: any = {};
      try { j = JSON.parse(x.responseText); } catch { /* not JSON */ }
      if (x.status >= 200 && x.status < 300) resolve(j as UploadRec);
      else reject(new ApiError(x.status, j.detail || x.statusText));
    };
    x.onerror = () => reject(new ApiError(0, "The upload was interrupted. Check that VoltProof is still running."));
    x.send(file);
  });
}

export const uploads = {
  datasets: () => plain<DatasetItem[]>("/api/datasets"),
  list: () => plain<UploadRec[]>("/api/uploads"),
  start: () => send<UploadRec>("POST", "/api/uploads"),
  putFile,
  preview: (id: string) => plain<UploadPreview>(`/api/uploads/${id}/preview`),
  validate: (id: string, mapping: unknown) => send<UploadRec>("POST", `/api/uploads/${id}/validate`, { mapping }),
  build: (id: string) => send<{ id: string; status: string }>("POST", `/api/uploads/${id}/build`),
  status: (id: string) => plain<UploadRec>(`/api/uploads/${id}`),
  remove: (id: string) => send<{ deleted: boolean }>("DELETE", `/api/uploads/${id}`),
};

export const fmtMin = (m: number | null | undefined) =>
  m == null ? "–" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
export const fmtHours = (m: number) => (m / 60).toLocaleString("en-IN", { maximumFractionDigits: 1 });
export const fmtPct = (x: number | null | undefined) => (x == null ? "–" : `${(100 * x).toFixed(1)}%`);
export const fmtTs = (ts: string) => ts.replace("T", " ");
export const fmtP = (p: number, n: number) => (p === 0 ? `none of ${n} shifted variants reached it` : `${(p * 100).toFixed(0)}% of ${n} shifted variants reached it`);

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                     "November", "December"];

/** The guided demo's selection window [from, toExclusive) in words: "June–August 2018", "January 2030". */
export function fmtWindow(from: string, toExclusive: string): string {
  const [y0, m0] = from.split("-").map(Number);
  let [y1, m1] = toExclusive.split("-").map(Number);
  if (Number(toExclusive.slice(8, 10)) === 1) {  // the window ends on the last day of the previous month
    m1 -= 1;
    if (m1 === 0) { m1 = 12; y1 -= 1; }
  }
  const a = MONTH_NAMES[m0 - 1], b = MONTH_NAMES[m1 - 1];
  if (y0 === y1 && m0 === m1) return `${a} ${y0}`;
  return y0 === y1 ? `${a}–${b} ${y1}` : `${a} ${y0}–${b} ${y1}`;
}
