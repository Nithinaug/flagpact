import { LayoutGroup, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, LABELS, type Cell, type Pane, type Plan, type State, type Verdict } from "./api";
import { AppPanes } from "./components/AppPanes";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { Counter } from "./components/Counter";
import { ScrambleText } from "./components/ScrambleText";
import { SignalLine } from "./components/SignalLine";
import { StatusMark } from "./components/StatusMark";
import { SurfaceBackdrop } from "./components/SurfaceBackdrop";
import { TypeLog } from "./components/TypeLog";

const ROW_HEIGHT = 56;
type Filter = "ALL" | "red" | "amber" | "green";
const FILTERS: Filter[] = ["ALL", "red", "amber", "green"];
const BREAKING = { heading: "Sale on now", cta: { text: "Shop" } };

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parse(text: string): { value?: Record<string, unknown>; error?: string } {
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== "object" || Array.isArray(value)) return { error: "Value must be a JSON object" };
    return { value };
  } catch {
    return { error: "Not valid JSON yet" };
  }
}

export default function App() {
  const [state, setState] = useState<State | null>(null);
  const [loadError, setLoadError] = useState("");
  const [draft, setDraft] = useState("");
  const [cells, setCells] = useState<Cell[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [applied, setApplied] = useState(false);
  const [run, setRun] = useState(0);
  const [log, setLog] = useState<string[]>(["ready"]);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [selected, setSelected] = useState("");
  const [lastMs, setLastMs] = useState<number | null>(null);
  const [panes, setPanes] = useState<Pane[]>([]);
  const [paneMode, setPaneMode] = useState<"live" | "preview" | "">("");
  const token = useRef(0);

  const push = useCallback((...lines: string[]) => setLog((old) => [...old, ...lines].slice(-60)), []);

  const refresh = useCallback(async () => {
    const next = await api.state();
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    refresh()
      .then((next) => setDraft(pretty(next.value)))
      .catch((error: Error) => setLoadError(error.message));
  }, [refresh]);

  const parsed = useMemo(() => parse(draft), [draft]);
  const unchanged = state !== null && parsed.value !== undefined && pretty(parsed.value) === pretty(state.value);

  useEffect(() => {
    if (!state || applied) return;
    if (!parsed.value || unchanged) {
      setCells([]);
      setPlan(null);
      if (parsed.value) {
        const mineLive = ++token.current;
        api.render().then((result) => {
          if (mineLive !== token.current) return;
          setPanes(result.panes);
          setPaneMode(result.mode);
        }).catch(() => undefined);
      }
      return;
    }
    const mine = ++token.current;
    const timer = window.setTimeout(async () => {
      try {
        setRun((n) => n + 1);
        push(`check ${state.versions.length} versions`);
        const quick = await api.check(parsed.value, false);
        if (mine !== token.current) return;
        setCells(quick.cells);
        const started = performance.now();
        const full = await api.plan(parsed.value);
        setLastMs(Math.round(performance.now() - started));
        if (mine !== token.current) return;
        setCells(full.cells);
        setPlan(full);
        const preview = await api.render(parsed.value);
        if (mine !== token.current) return;
        setPanes(preview.panes);
        setPaneMode(preview.mode);
        full.cells.forEach((cell) => push(`v${cell.version} ${LABELS[cell.state].toLowerCase()}`));
      } catch (error) {
        push(`error ${(error as Error).message}`);
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [parsed.value, unchanged, state, applied, push]);

  const rows: Cell[] = useMemo(() => {
    if (!state) return [];
    return state.versions.map(
      (version) => cells.find((cell) => cell.version === version) ?? { version, state: "idle" as Verdict, reason: "waiting for a pending change", value: {} },
    );
  }, [state, cells]);

  const visible = rows.filter((row) => filter === "ALL" || row.state === filter);
  const active = rows.find((row) => row.version === selected) ?? rows[0];
  const reads = active && state ? state.contracts[active.version] ?? [] : [];

  const count = (verdict: Verdict) => rows.filter((row) => row.state === verdict).length;

  const confirmApply = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.apply(parsed.value);
      setCells(result.cells);
      setApplied(true);
      setRun((n) => n + 1);
      push(...result.steps);
      push(`recheck ${result.cells.filter((c) => c.state === "green").length} safe`);
      await refresh();
      const live = await api.render();
      setPanes(live.panes);
      setPaneMode(live.mode);
    } catch (error) {
      push(`error ${(error as Error).message}`);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  const undo = async () => {
    setBusy(true);
    try {
      const result = await api.rollback();
      push(...result.steps);
      const next = await refresh();
      setDraft(pretty(next.value));
      setApplied(false);
      setCells([]);
      setPlan(null);
    } catch (error) {
      push(`error ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const phase = applied ? "ROLLBACK" : plan?.diff ? "FIX" : "CHECK";

  if (loadError) {
    return (
      <main className="grid h-full place-items-center p-6">
        <SurfaceBackdrop />
        <p className="font-mono text-sm text-status-red">Cannot reach the flagpact server: {loadError}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto grid min-h-full max-w-[1280px] gap-3 p-3 lg:grid-cols-[220px_minmax(0,1fr)_300px]">
      <SurfaceBackdrop />

      <header className="kicker flex items-center justify-between border-b border-border-subtle px-1 pb-2 lg:col-span-3">
        <span className="flex gap-5">
          <span className="text-ink-primary">FLAGPACT</span>
          <span>ENV: LOCAL</span>
          <span>VERSIONS: {state?.versions.length ?? 0}</span>
          <span>CONTRACTS: {state ? Object.keys(state.contracts).length : 0}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <i className={`inline-block size-1.5 rounded-full ${applied ? "bg-status-red" : "bg-status-green"}`} />
          {applied ? "LIVE_FIX_ACTIVE" : "NO_PENDING_FIX"}
        </span>
      </header>

      <aside className="panel flex flex-col gap-5 p-4">
        <div className="flex items-center justify-between">
          <span className="kicker">FLAGPACT_NAV</span>
          <span className="kicker flex items-center gap-1.5">
            LINK.OK <i className="inline-block size-1.5 rounded-full bg-status-green" />
          </span>
        </div>
        <div>
          <div className="kicker">ACTIVE_FLAG</div>
          <h1 className="mt-1 font-display text-2xl font-medium">
            <ScrambleText text={state?.flag ?? "loading"} />
          </h1>
        </div>
        <dl className="grid grid-cols-2 gap-3">
          <div>
            <dt className="kicker">VERSIONS</dt>
            <dd className="font-mono text-lg tabular-nums">{state?.versions.length ?? 0}</dd>
          </div>
          <div>
            <dt className="kicker">MODE</dt>
            <dd className="font-mono text-lg">{applied ? "LIVE" : "DRAFT"}</dd>
          </div>
        </dl>
        <div>
          <div className="kicker mb-2">OPERATIONS</div>
          <ul className="space-y-1 font-mono text-xs">
            {["CHECK", "FIX", "ROLLBACK"].map((name) => (
              <li key={name} className={phase === name ? "text-ink-primary" : "text-ink-muted/50"}>
                [ {name} ]
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="kicker mb-2">CURRENT_DEFAULT</div>
          <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-ink-muted">{state ? pretty(state.value) : ""}</pre>
        </div>
      </aside>

      <section className="panel flex flex-col p-5">
        <h2 className="font-display text-4xl font-medium">Version matrix</h2>
        <p className="kicker mt-1">
          <span className="text-status-red"><Counter value={count("red")} /> {LABELS.red}</span>
          {"  "}
          <span className="text-status-amber"><Counter value={count("amber")} /> {LABELS.amber}</span>
          {"  "}
          <span className="text-status-green"><Counter value={count("green")} /> {LABELS.green}</span>
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label="Filter by verdict">
          <span className="kicker mr-2">STATE</span>
          {FILTERS.map((name) => (
            <button
              key={name}
              aria-pressed={filter === name}
              className={`btn ${filter === name ? "bg-subtle" : ""}`}
              onClick={() => setFilter(name)}
            >
              {name === "ALL" ? "ALL" : LABELS[name]}
            </button>
          ))}
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between">
            <label htmlFor="pending" className="kicker">&gt; edit --value</label>
            <span className="flex gap-2">
              <button className="btn" disabled={applied || !state} onClick={() => setDraft(pretty(BREAKING))}>Remove title</button>
              <button className="btn" disabled={applied || !state} onClick={() => state && setDraft(pretty(state.value))}>Reset</button>
            </span>
          </div>
          <textarea
            id="pending"
            spellCheck={false}
            value={draft}
            disabled={applied}
            onChange={(event) => setDraft(event.target.value)}
            rows={7}
            className="mt-2 w-full resize-y border border-border-subtle bg-canvas/60 p-3 font-mono text-xs text-ink-primary"
          />
          {parsed.error && <p className="mt-1 font-mono text-[11px] text-status-red">{parsed.error}</p>}
        </div>

        <div className="mt-5">
          <AppPanes panes={panes} mode={paneMode} />
        </div>

        <div className="relative mt-5">
          <div className="kicker grid grid-cols-[72px_minmax(0,1fr)_96px] gap-3 pl-8 pb-2">
            <span>VER</span>
            <span>RECEIVES</span>
            <span>STATUS</span>
          </div>
          <div className="relative">
            <SignalLine rows={visible.length} rowHeight={ROW_HEIGHT} run={run} />
            <LayoutGroup>
              <ul>
                {visible.map((row, index) => (
                  <motion.li
                    layout
                    key={row.version}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30, delay: index * 0.04 }}
                    tabIndex={0}
                    onClick={() => setSelected(row.version)}
                    onKeyDown={(event) => event.key === "Enter" && setSelected(row.version)}
                    className="grid cursor-pointer grid-cols-[72px_minmax(0,1fr)_96px] items-center gap-3 border-t border-border-subtle pl-8 hover:bg-subtle/40"
                    style={{ height: ROW_HEIGHT, boxShadow: active?.version === row.version ? "inset 2px 0 0 var(--accent)" : undefined }}
                  >
                    <span className="chip w-fit">{row.version}</span>
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-xs text-ink-primary">
                        {Object.keys(row.value).length ? `gets ${Object.keys(row.value).join(", ")}` : "no value yet"}
                      </span>
                      <span className="block truncate text-[11px] text-ink-muted">{row.reason}</span>
                    </span>
                    <StatusMark state={row.state} />
                  </motion.li>
                ))}
              </ul>
            </LayoutGroup>
          </div>
          {visible.length === 0 && <p className="kicker py-4">No versions match this filter.</p>}
          <div className="kicker mt-3 flex justify-between border-t border-border-subtle pt-3">
            <span>Builds without an app_version trait are not covered by the fix.</span>
            <span>{lastMs === null ? "LAST_CHECK --" : `LAST_CHECK ${(lastMs / 1000).toFixed(1)}S`}</span>
          </div>
        </div>
      </section>

      <aside className="panel flex flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <span className="kicker">FIX_PLAN</span>
          {plan?.limit && <span className="chip">{plan.limit}</span>}
        </div>

        {applied ? (
          <p className="text-sm leading-relaxed text-ink-primary">The fix is live. Old versions keep the previous value. Roll back to restore the default.</p>
        ) : plan?.diff ? (
          <ul className="space-y-2 text-sm leading-relaxed text-ink-primary">
            {plan.diff.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : plan?.error ? (
          <p className="text-sm leading-relaxed text-ink-muted">{plan.error}</p>
        ) : (
          <p className="text-sm leading-relaxed text-ink-muted">Edit the value. flagpact replays each version's own tests against it, then proposes a fix.</p>
        )}

        {applied ? (
          <button className="btn" disabled={busy} onClick={undo}>Roll back</button>
        ) : (
          <button className="btn btn-primary" disabled={!plan?.diff || busy} onClick={() => setConfirming(true)}>Apply fix</button>
        )}

        {active && (
          <div className="border-t border-border-subtle pt-3">
            <div className="flex items-center justify-between">
              <span className="kicker">VERSION_DETAIL</span>
              <span className="chip">{active.version}</span>
            </div>
            <p className="mt-2 text-xs text-ink-muted">{active.reason}</p>
            <div className="kicker mt-3 mb-1">CONTRACT_READS</div>
            {reads.length === 0 ? (
              <p className="font-mono text-[11px] text-ink-muted">no contract recorded</p>
            ) : (
              <ul className="space-y-1 font-mono text-[11px]">
                {reads.map((read) => (
                  <li key={read.path} className="flex justify-between gap-2">
                    <span className="truncate text-ink-primary">{read.path}</span>
                    <span className="shrink-0 text-ink-muted">{read.has_default ? "optional" : "required"} {read.type}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-auto">
          <TypeLog lines={log} />
        </div>
      </aside>

      <ConfirmDialog
        open={confirming}
        title="Write this fix to Flagsmith"
        lines={plan?.diff ?? []}
        busy={busy}
        onConfirm={confirmApply}
        onCancel={() => setConfirming(false)}
      />
    </main>
  );
}
