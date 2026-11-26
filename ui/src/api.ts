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
  error?: string;
  limit?: string;
  diff?: string[];
  segment?: string;
  include_missing?: boolean;
  after?: Cell[];
  protected?: number;
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
  publish: (value: unknown) => call<{ steps: string[] }>("POST", "/api/publish", { value }),
  render: (value?: unknown) =>
    call<{ before: Pane[]; after: Pane[] | null }>("POST", "/api/render", value === undefined ? {} : { value }),
  rollback: () => call<{ steps: string[] }>("POST", "/api/rollback", {}),
};
