export type Verdict = "red" | "amber" | "green" | "idle";

export type Cell = {
  version: string;
  state: Verdict;
  reason: string;
  value: Record<string, unknown>;
};

export type Read = {
  path: string;
  has_default: boolean;
  type: string;
  observed_values: unknown[];
};

export type Pane = {
  version: string;
  ok: boolean;
  output: string;
};

export type Meta = {
  share: number | null;
  users: number | null;
  platforms: string;
};

export type Plan = {
  cells: Cell[];
  at_risk: number;
  at_risk_users: number;
  error?: string;
  limit?: string;
  diff?: string[];
  segment?: string;
  include_missing?: boolean;
  after?: Cell[];
  protected?: number;
};

export type Stage = {
  index: number;
  boundary: string;
  gets_change: string[];
  kept: string[];
  share_new: number;
  cells: Cell[];
  ok: boolean;
  blocked: string[];
  holds_missing: boolean;
};

export type Rollout = {
  stages: Stage[];
  current: number;
  segment?: string;
  held: string[];
  published?: boolean;
  error?: string;
};

export type ScanRead = {
  path: string;
  required: boolean;
  required_in: string[];
  default_in: string[];
  places: string[];
};

export type ScanFlag = {
  flag: string;
  sites: { file: string; line: number; call: string }[];
  reads: ScanRead[];
  languages: string[];
};

export type ScanResult = {
  kind: "local" | "github";
  source: string;
  files_scanned: number;
  flags: ScanFlag[];
  versions: { version: string; directory: string; file: string; line: number; guessed: boolean }[];
  draft: Record<string, unknown> | null;
  needs_review: string[];
  notes: string[];
};

export type State = {
  flag: string;
  value: Record<string, unknown>;
  versions: string[];
  meta: Record<string, Meta>;
  missing: { share: number; users: number } | null;
  latest: string;
  applied: boolean;
  published: boolean;
  dashboard: string;
  contracts: Record<string, Read[]>;
  notices: string[];
};

export type Rehearsal = {
  ok: boolean;
  seconds: number;
  rows: { version: string; expects: "old" | "new"; ok: boolean; fields: string[] }[];
};

export type Watch = {
  ok: boolean;
  value: Record<string, unknown>;
  broken: string[];
  cells: Cell[];
  at_risk: number;
  restore: boolean;
  previous: Record<string, unknown> | null;
  checked_at: number;
};

export const MISSING = "none";

export const LABELS: Record<Verdict, string> = {
  red: "Breaks",
  amber: "Not checked",
  green: "Safe",
  idle: "Waiting",
};

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error ?? `request failed (${response.status})`);
  return payload as T;
}

export const api = {
  state: () => call<State>("GET", "/api/state"),
  check: (value: unknown, replay: boolean) => call<{ cells: Cell[] }>("POST", "/api/check", { value, replay }),
  plan: (value: unknown, includeMissing: boolean) => call<Plan>("POST", "/api/plan", { value, include_missing: includeMissing }),
  apply: (value: unknown, includeMissing: boolean) =>
    call<{ steps: string[]; cells: Cell[] }>("POST", "/api/apply", { value, include_missing: includeMissing }),
  rehearse: (value: unknown, includeMissing: boolean) =>
    call<Rehearsal>("POST", "/api/rehearse", { value, include_missing: includeMissing }),
  stages: (value: unknown, includeMissing: boolean) =>
    call<Partial<Rollout> & { stages: Stage[]; current: number }>("POST", "/api/stages", { value, include_missing: includeMissing }).then(
      (r): Rollout => ({ ...r, held: r.held ?? [] }),
    ),
  stageNext: (value: unknown, includeMissing: boolean) =>
    call<{ steps: string[]; stage: number; done: boolean }>("POST", "/api/stage-next", { value, include_missing: includeMissing }),
  stageBack: (value: unknown, includeMissing: boolean) =>
    call<{ steps: string[]; stage: number }>("POST", "/api/stage-back", { value, include_missing: includeMissing }),
  importScan: (source: string) => call<ScanResult>("POST", "/api/import", { source }),
  watch: () => call<Watch>("GET", "/api/watch"),
  protect: () => call<{ steps: string[]; limit: string }>("POST", "/api/protect", {}),
  restore: () => call<{ value: Record<string, unknown> }>("POST", "/api/restore", {}),
  outsideEdit: () => call<{ value: Record<string, unknown> }>("POST", "/api/outside-edit", {}),
  publish: (value: unknown) => call<{ steps: string[] }>("POST", "/api/publish", { value }),
  render: (value?: unknown) =>
    call<{ before: Pane[]; after: Pane[] | null }>("POST", "/api/render", value === undefined ? {} : { value }),
  rollback: () => call<{ steps: string[] }>("POST", "/api/rollback", {}),
};
