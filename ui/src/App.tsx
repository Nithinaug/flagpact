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
import { plainReason, plainStep, plainType } from "./plain";

type Filter = "ALL" | "red" | "amber" | "green";

const FILTERS: Filter[] = ["ALL", "red", "amber", "green"];
const ROW_HEIGHT = 64;
const BREAKING = { heading: "Sale on now", cta: { text: "Shop" } };
const PHASES = [
  { key: "CHECK", label: "Check your change" },
  { key: "FIX", label: "Apply the fix" },
  { key: "ROLLBACK", label: "Undo if needed" },
];

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parse(text: string): { value?: Record<string, unknown>; error?: string } {
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== "object" || Array.isArray(value)) return { error: "The value must be a JSON object" };
    return { value };
  } catch {
    return { error: "This is not valid JSON yet" };
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
  const [log, setLog] = useState<string[]>(["Ready"]);
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
      .then((next) => {
        setDraft(pretty(next.value));
        setApplied(next.applied);
        if (next.applied) {
          api.render().then((result) => {
            setPanes(result.panes);
            setPaneMode(result.mode);
          });
          api.check(next.value, true).then((result) => setCells(result.cells));
        }
      })
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
        api
          .render()
          .then((result) => {
            if (mineLive !== token.current) return;
            setPanes(result.panes);
            setPaneMode(result.mode);
          })
          .catch(() => undefined);
      }
      return;
    }
    const mine = ++token.current;
    const timer = window.setTimeout(async () => {
      try {
        setRun((n) => n + 1);
        push(`Checking ${state.versions.length} app versions`);
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
        full.cells.forEach((cell) => push(`${cell.version}: ${LABELS[cell.state].toLowerCase()}`));
      } catch (error) {
        push(`Something went wrong: ${(error as Error).message}`);
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
  const broken = rows.filter((row) => row.state === "red").map((row) => row.version);

  const confirmApply = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.apply(parsed.value);
      setCells(result.cells);
      setApplied(true);
      setRun((n) => n + 1);
      push(...result.steps.map(plainStep));
      push(`Re-checked: ${result.cells.filter((c) => c.state === "green").length} versions are safe`);
      await refresh();
      const live = await api.render();
      setPanes(live.panes);
      setPaneMode(live.mode);
    } catch (error) {
      push(`Something went wrong: ${(error as Error).message}`);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  const undo = async () => {
    setBusy(true);
    try {
      const result = await api.rollback();
      push(...result.steps.map(plainStep));
      const next = await refresh();
      setDraft(pretty(next.value));
      setApplied(false);
      setCells([]);
      setPlan(null);
    } catch (error) {
      push(`Something went wrong: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const phase = applied ? "ROLLBACK" : plan?.diff ? "FIX" : "CHECK";

  if (loadError) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <SurfaceBackdrop />
        <p className="text-sm text-status-red">Cannot reach the flagpact server: {loadError}</p>
      </main>
    );
  }

  const summary = plan?.limit
    ? [
        `Versions below ${plan.limit} keep the old value.`,
        "Everyone else gets your new value.",
        `Why: ${broken.join(" and ")} can't read the new value.`,
      ]
    : [];

  return (
    <main className="grid min-h-screen w-full gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_360px] xl:p-6">
      <SurfaceBackdrop />

      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-3 lg:col-span-2 xl:col-span-3">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="font-display text-xl font-medium">flagpact</span>
        </div>
        <span className="flex items-center gap-2 text-sm text-ink-muted">
          <i className={`inline-block size-2 rounded-full ${applied ? "bg-status-amber" : "bg-status-green"}`} />
          {applied ? "A fix is live" : "Nothing published yet"}
        </span>
      </header>

      <aside className="panel flex flex-col gap-6 p-5">
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <i className="inline-block size-2 rounded-full bg-status-green" />
          Connected to Flagsmith
        </div>
        <div>
          <div className="kicker">Config being checked</div>
          <h1 className="mt-1 font-display text-2xl font-medium">
            <ScrambleText text={state?.flag ?? "loading"} />
          </h1>
        </div>
        <dl className="grid grid-cols-2 gap-3">
          <div>
            <dt className="kicker">App versions</dt>
            <dd className="text-xl tabular-nums">{state?.versions.length ?? 0}</dd>
          </div>
          <div>
            <dt className="kicker">Status</dt>
            <dd className="text-xl">{applied ? "Fix live" : "Editing"}</dd>
          </div>
        </dl>
        <div>
          <div className="kicker mb-2">Steps</div>
          <ol className="space-y-1.5 text-sm">
            {PHASES.map((item, index) => (
              <li key={item.key} className={phase === item.key ? "text-ink-primary" : "text-ink-muted/60"}>
                {index + 1}. {item.label}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <div className="kicker mb-2">Value in Flagsmith now</div>
          <pre className="overflow-x-auto text-xs leading-relaxed text-ink-muted">{state ? pretty(state.value) : ""}</pre>
        </div>
      </aside>

      <section className="panel flex flex-col p-6">
        <h2 className="font-display text-4xl font-medium">App version check</h2>
        <p className="mt-3 flex flex-wrap gap-x-5 text-sm">
          <span className="text-status-red"><Counter value={count("red")} /> would break</span>
          <span className="text-status-amber"><Counter value={count("amber")} /> not checked</span>
          <span className="text-status-green"><Counter value={count("green")} /> safe</span>
        </p>

        <div className="mt-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="pending" className="text-sm font-medium">New value to publish</label>
            <span className="flex gap-2">
              <button className="btn" disabled={applied || !state} onClick={() => setDraft(pretty(BREAKING))}>Try a breaking change</button>
              <button className="btn" disabled={applied || !state} onClick={() => state && setDraft(pretty(state.value))}>Reset</button>
            </span>
          </div>
          <textarea
            id="pending"
            spellCheck={false}
            value={draft}
            disabled={applied}
            onChange={(event) => setDraft(event.target.value)}
            rows={6}
            className="mt-2 w-full resize-y border border-border-subtle bg-canvas/60 p-3 text-sm text-ink-primary"
          />
          {parsed.error && <p className="mt-1 text-xs text-status-red">{parsed.error}</p>}
        </div>

        <div className="mt-6">
          <AppPanes panes={panes} mode={paneMode} />
        </div>

        <div className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-medium">Result for each app version</h3>
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by result">
              <span className="kicker">Show</span>
              {FILTERS.map((name) => (
                <button key={name} aria-pressed={filter === name} className={`btn ${filter === name ? "bg-subtle" : ""}`} onClick={() => setFilter(name)}>
                  {name === "ALL" ? "All" : LABELS[name]}
                </button>
              ))}
            </div>
          </div>
          <div className="kicker grid grid-cols-[96px_minmax(0,1fr)_120px] gap-3 pb-2 pl-8">
            <span>App version</span>
            <span>Gets this value</span>
            <span>Result</span>
          </div>
          <div className="relative">
            <SignalLine rows={visible.length} rowHeight={ROW_HEIGHT} run={run} />
            <LayoutGroup>
              <ul>
                {visible.map((row, index) => (
                  <motion.li
                    layout
                    key={row.version}
                    tabIndex={0}
                    onClick={() => setSelected(row.version)}
                    onKeyDown={(event) => event.key === "Enter" && setSelected(row.version)}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30, delay: index * 0.04 }}
                    className="grid cursor-pointer grid-cols-[96px_minmax(0,1fr)_120px] items-center gap-3 border-t border-border-subtle pl-8 hover:bg-subtle/40"
                    style={{ height: ROW_HEIGHT, boxShadow: active?.version === row.version ? "inset 2px 0 0 var(--accent)" : undefined }}
                  >
                    <span className="chip w-fit">{row.version}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-ink-primary">
                        {Object.keys(row.value).length ? `Reads: ${Object.keys(row.value).join(", ")}` : "No value yet"}
                      </span>
                      <span className="block truncate text-xs text-ink-muted">{plainReason(row.reason)}</span>
                    </span>
                    <StatusMark state={row.state} />
                  </motion.li>
                ))}
              </ul>
            </LayoutGroup>
            {visible.length === 0 && <p className="py-4 text-sm text-ink-muted">No app versions match this filter.</p>}
          </div>
          <div className="mt-3 flex flex-wrap justify-between gap-2 border-t border-border-subtle pt-3 text-xs text-ink-muted">
            <span>Older builds that don't send an app_version are not protected by the fix.</span>
            <span>{lastMs === null ? "Not checked yet" : `Last check took ${(lastMs / 1000).toFixed(1)} s`}</span>
          </div>
        </div>
      </section>

      <aside className="panel flex flex-col gap-4 p-5 lg:col-span-2 xl:col-span-1">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-medium">The fix</h2>
          {plan?.limit && <span className="chip">Below {plan.limit}</span>}
        </div>

        {applied ? (
          <p className="text-sm leading-relaxed">The fix is live. Older versions keep the previous value and everyone else has the new one. Undo to go back to how it was.</p>
        ) : summary.length > 0 ? (
          <ul className="space-y-2 text-sm leading-relaxed">
            {summary.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : plan?.error ? (
          <p className="text-sm leading-relaxed text-ink-muted">{plan.error}</p>
        ) : (
          <p className="text-sm leading-relaxed text-ink-muted">Edit the value, or try the breaking change. flagpact will suggest a fix if any version would break.</p>
        )}

        {plan?.diff && !applied && (
          <details className="text-xs text-ink-muted">
            <summary className="cursor-pointer">Technical details</summary>
            <ul className="mt-2 space-y-1">
              {plan.diff.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
        )}

        {applied ? (
          <button className="btn" disabled={busy} onClick={undo}>Undo the fix</button>
        ) : (
          <button className="btn btn-primary" disabled={!plan?.diff || busy} onClick={() => setConfirming(true)}>Apply the fix</button>
        )}

        {active && (
          <div className="border-t border-border-subtle pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Selected app version</h3>
              <span className="chip">{active.version}</span>
            </div>
            <p className="mt-2 text-sm text-ink-muted">{plainReason(active.reason)}</p>
            <div className="kicker mb-1 mt-3">What this version reads</div>
            {reads.length === 0 ? (
              <p className="text-xs text-ink-muted">No recorded behaviour</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {reads.map((read) => (
                  <li key={read.path} className="flex justify-between gap-2">
                    <span className="truncate">{read.path}</span>
                    <span className="shrink-0 text-xs text-ink-muted">{read.has_default ? "optional" : "required"}, {plainType(read.type)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="mt-auto border-t border-border-subtle pt-4">
          <h3 className="mb-2 text-sm font-medium">Activity</h3>
          <TypeLog lines={log} />
        </div>
      </aside>

      <ConfirmDialog
        open={confirming}
        title="Publish this change safely?"
        lines={summary}
        details={plan?.diff ?? []}
        busy={busy}
        onConfirm={confirmApply}
        onCancel={() => setConfirming(false)}
      />
    </main>
  );
}
