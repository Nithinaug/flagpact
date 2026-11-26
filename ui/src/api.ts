export type Verdict = "red" | "amber" | "green" | "idle";

export const LABELS: Record<Verdict, string> = {
  red: "Breaks",
  amber: "Not checked",
  green: "Safe",
  idle: "Waiting",
};

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

export type Plan = {
  cells: Cell[];
  limit?: string;
  diff?: string[];
  segment?: string;
  error?: string;
};

export type State = {
  flag: string;
  value: Record<string, unknown>;
  versions: string[];
  applied: boolean;
  contracts: Record<string, Read[]>;
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
  plan: (value: unknown) => call<Plan>("POST", "/api/plan", { value }),
  apply: (value: unknown) => call<{ steps: string[]; cells: Cell[] }>("POST", "/api/apply", { value }),
  render: (value?: unknown) => call<{ mode: "live" | "preview"; panes: Pane[] }>("POST", "/api/render", value === undefined ? {} : { value }),
  rollback: () => call<{ steps: string[] }>("POST", "/api/rollback", {}),
};
