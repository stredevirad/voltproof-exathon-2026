// Typed client for the VoltProof API (same origin; FastAPI serves both the API and this app).

export type Loc = {
  location_id: number; display_name: string; source_name: string; is_offline: boolean; district: string;
  state_name: string; source_category: string; connection_type: string; first_ts: string; last_ts: string;
  coverage_window: number; months_in_window: number; comparable_months: number; outage_minutes: number;
};
export type MonthRow = {
  month_key: string; outage_min_lower: number; outage_min_upper: number; interruptions: number;
  coverage_calendar: number; is_comparable: boolean;
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
  location: Loc; days: Day[]; events: Ev[]; baseline: Baseline | null;
  month: Day & { month_key: string; calendar_minutes: number; coverage_calendar: number; coverage_window: number;
                 is_comparable: boolean; outage_zero_minutes: number };
};
export type Segment = { seg_no: number; supply_state: string; start_ts: string; end_ts: string; minutes: number };
export type DayData = {
  location: Loc; day: string; daily: Day | null; readings: { ts: string; voltage: number; supply_state: string }[];
  segments: Segment[]; claims: { claim_start: string; claim_end: string; claim_minutes: number; side: string }[];
  events: Ev[];
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
                exa_session_id: number; exa_stmt_id: number; run_id: string }[];
  group: GroupData | null; baseline: Baseline | null;
};
export type Demo = { location_id: number; month: string; day: string; event_key: string; group_key: string; rule: string };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
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
    const r = await fetch("/api/reports", { method: "POST", headers: { "Content-Type": "application/json" },
                                             body: JSON.stringify({ location_id, month }) });
    if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json() as Promise<{ report_id: string; pdf_url: string; html_url: string; json_url: string }>;
  },
};

export const fmtMin = (m: number | null | undefined) =>
  m == null ? "–" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
export const fmtHours = (m: number) => (m / 60).toLocaleString("en-IN", { maximumFractionDigits: 1 });
export const fmtPct = (x: number | null | undefined) => (x == null ? "–" : `${(100 * x).toFixed(1)}%`);
export const fmtTs = (ts: string) => ts.replace("T", " ");
export const fmtP = (p: number, n: number) => (p === 0 ? `none of ${n} shifted variants reached it` : `${(p * 100).toFixed(0)}% of ${n} shifted variants reached it`);
