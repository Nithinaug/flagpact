import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, MISSING, type Cell, type Pane, type Plan, type Rehearsal, type Rollout, type State, type Watch } from "./api";
import { ActivityCard, type Entry } from "./components/ActivityCard";
import { ChangeEditor } from "./components/ChangeEditor";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { FixCard } from "./components/FixCard";
import { LiveAlert } from "./components/LiveAlert";
import { Notices } from "./components/Notices";
import { RolloutCard } from "./components/RolloutCard";
import { ImpactTable, type Filter } from "./components/ImpactTable";
import { Stepper, type StepState } from "./components/Stepper";
import { SummaryCard } from "./components/SummaryCard";
import { SurfaceBackdrop } from "./components/SurfaceBackdrop";
import { TopBar } from "./components/TopBar";
import { clock, pathPresent, pretty } from "./lib/diff";
import { plainStep } from "./plain";

const BREAKING = { heading: "Sale on now", subheading: "Up to 40% off", cta: { label: "Shop the sale" } };

function parse(text: string): { value?: Record<string, unknown>; error?: string } {
  try {
    const value = JSON.parse(text);
    if (value === null || typeof value !== "object" || Array.isArray(value)) return { error: "Must be a JSON object" };
    return { value };
  } catch {
    return { error: "Not valid JSON yet" };
  }
}

export default function App({ onHome }: { onHome?: () => void }) {
  const [state, setState] = useState<State | null>(null);
  const [loadError, setLoadError] = useState("");
  const [draft, setDraft] = useState("");
  const [cells, setCells] = useState<Cell[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [before, setBefore] = useState<Pane[]>([]);
  const [after, setAfter] = useState<Pane[] | null>(null);
  const [applied, setApplied] = useState(false);
  const [published, setPublished] = useState(false);
  const [includeMissing, setIncludeMissing] = useState(true);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [confirm, setConfirm] = useState<"apply" | "publish" | "stage" | null>(null);
  const [rollout, setRollout] = useState<Rollout | null>(null);
  const [rolloutLoading, setRolloutLoading] = useState(false);
  const rolloutToken = useRef(0);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [rehearsal, setRehearsal] = useState<Rehearsal | null>(null);
  const [rehearsing, setRehearsing] = useState(false);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [lastMs, setLastMs] = useState<number | null>(null);
  const [checkedAt, setCheckedAt] = useState("");
  const [watch, setWatch] = useState<Watch | null>(null);
  const watching = useRef(false);
  const prevOk = useRef<boolean | null>(null);
  const token = useRef(0);
  const entryId = useRef(0);
  const firstToggle = useRef(true);
  const serverFlags = useRef({ applied: false, published: false });

  const push = useCallback((tone: Entry["tone"], title: string, sub = "") => {
    setEntries((old) => [{ id: ++entryId.current, tone, title, sub, time: clock() }, ...old].slice(0, 20));
  }, []);

  const refresh = useCallback(async () => {
    const next = await api.state();
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    serverFlags.current = { applied, published };
  }, [applied, published]);

  const resync = useCallback(async () => {
    const next = await refresh();
    setApplied(next.applied);
    setPublished(next.published);
    if (!next.applied) {
      setDraft(pretty(next.value));
      setCells([]);
      setPlan(null);
      setAfter(null);
      api.render().then((result) => setBefore(result.before)).catch(() => undefined);
    }
  }, [refresh]);

  useEffect(() => {
    const onFocus = () => {
      api.state().then((next) => {
        if (next.applied !== serverFlags.current.applied || next.published !== serverFlags.current.published) void resync();
      }).catch(() => undefined);
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [resync]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      if (watching.current) return;
      watching.current = true;
      try {
        const result = await api.watch();
        if (!alive) return;
        setWatch(result);
      } catch {
        return;
      } finally {
        watching.current = false;
      }
    };
    void tick();
    const id = window.setInterval(tick, 3000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!watch) return;
    const was = prevOk.current;
    prevOk.current = watch.ok;
    if (was === true && !watch.ok) {
      push("red", "Watch caught a change outside flagpact", `Live value now breaks ${watch.broken.join(" and ")}`);
      void resync();
    } else if (was === false && watch.ok) {
      push("green", "Live value is safe again");
      void resync();
    } else if (was === null && !watch.ok) {
      push("red", "Live value breaks an app version", watch.broken.join(" and "));
    }
  }, [watch, push, resync]);

  useEffect(() => {
    refresh()
      .then((next) => {
        setDraft(pretty(next.value));
        setApplied(next.applied);
        setPublished(next.published);
        push("idle", "Connected to Flagsmith", "Local environment");
        if (next.applied) {
          api.render(next.value).then((result) => {
            setBefore(result.before);
            setAfter(result.after);
          });
          api.check(next.value, true).then((result) => setCells(result.cells));
        }
      })
      .catch((error: Error) => setLoadError(error.message));
  }, [refresh, push]);

  const parsed = useMemo(() => parse(draft), [draft]);

  useEffect(() => {
    setRehearsal(null);
  }, [draft, includeMissing, applied]);
  const unchanged = state !== null && parsed.value !== undefined && pretty(parsed.value) === pretty(state.value);
  const editing = parsed.value !== undefined && !unchanged;
  const liveBroken = watch !== null && !watch.ok && !applied;
  const hasChange = editing || applied || liveBroken;
  const showCompare = liveBroken && !editing && Boolean(watch?.previous);

  useEffect(() => {
    if (!state || applied) return;
    if (!parsed.value || unchanged) {
      setCells([]);
      setPlan(null);
      setAfter(null);
      if (parsed.value) {
        const live = ++token.current;
        api
          .render()
          .then((result) => {
            if (live === token.current) setBefore(result.before);
          })
          .catch(() => undefined);
      }
      return;
    }
    const mine = ++token.current;
    const timer = window.setTimeout(async () => {
      try {
        setChecking(true);
        const quick = await api.check(parsed.value, false);
        if (mine !== token.current) return;
        setCells(quick.cells);
        const started = performance.now();
        const full = await api.plan(parsed.value, includeMissing);
        if (mine !== token.current) return;
        setLastMs(Math.round(performance.now() - started));
        setCheckedAt(clock());
        setCells(full.cells);
        setPlan(full);
        const preview = await api.render(parsed.value);
        if (mine !== token.current) return;
        setBefore(preview.before);
        setAfter(preview.after);
        const real = full.cells.filter((c) => c.version !== MISSING);
        const broken = real.filter((c) => c.state === "red").map((c) => c.version);
        const safe = real.filter((c) => c.state === "green").map((c) => c.version);
        push("idle", `Checked ${real.length} app versions`, "Against recorded contracts");
        if (broken.length) {
          push("red", `${broken.length} versions would break`, `${broken.join(", ")} · ${safe.join(", ")} safe`);
        }
        if (full.limit) push("amber", "Fix suggested", `Segment override for app_version < ${full.limit}`);
      } catch (error) {
        push("red", "Something went wrong", (error as Error).message);
      } finally {
        if (mine === token.current) setChecking(false);
      }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [parsed.value, unchanged, state, applied, push]);

  useEffect(() => {
    if (firstToggle.current) {
      firstToggle.current = false;
      return;
    }
    if (!plan || applied || !parsed.value || unchanged) return;
    api.plan(parsed.value, includeMissing).then(setPlan).catch(() => undefined);
  }, [includeMissing]);

  useEffect(() => {
    if (!state || !parsed.value || !(editing || applied) || checking) {
      if ((!editing && !applied) || (checking && !applied)) setRollout(null);
      return;
    }
    const mine = ++rolloutToken.current;
    setRolloutLoading(true);
    api
      .stages(parsed.value, includeMissing)
      .then((result) => {
        if (mine === rolloutToken.current) setRollout(result);
      })
      .catch(() => {
        if (mine === rolloutToken.current) setRollout(null);
      })
      .finally(() => {
        if (mine === rolloutToken.current) setRolloutLoading(false);
      });
  }, [parsed.value, includeMissing, applied, published, editing, checking, state]);

  const rows: Cell[] = useMemo(() => {
    if (!state) return [];
    const idle = (version: string): Cell => ({ version, state: "idle", reason: "waiting for a pending change", value: {} });
    const source = liveBroken && !editing && watch ? watch.cells : cells;
    const list = state.versions.map((version) => source.find((c) => c.version === version) ?? idle(version));
    if (state.missing) list.push(source.find((c) => c.version === MISSING) ?? idle(MISSING));
    return list;
  }, [state, cells, liveBroken, editing, watch]);

  const real = rows.filter((r) => r.version !== MISSING);
  const brokenVersions = real.filter((r) => r.state === "red").map((r) => r.version);
  const removed = useMemo(() => {
    if (!state || !parsed.value) return [];
    const paths = new Set<string>();
    brokenVersions.forEach((version) => {
      (state.contracts[version] ?? []).forEach((read) => {
        if (!read.has_default && !pathPresent(parsed.value, read.path)) paths.add(read.path);
      });
    });
    return [...paths];
  }, [state, parsed.value, brokenVersions.join(",")]);

  const hasShares = state ? Object.values(state.meta).some((m) => m.share !== null) : false;

  const rehearse = async () => {
    if (!parsed.value) return;
    setRehearsing(true);
    push("idle", "Rehearsing on a clone of the environment");
    try {
      const result = await api.rehearse(parsed.value, includeMissing);
      setRehearsal(result);
      const good = result.rows.filter((r) => r.ok).length;
      push(result.ok ? "green" : "red", result.ok ? "Rehearsal passed on a clone" : "Rehearsal found a problem", `${good} of ${result.rows.length} as expected · clone deleted · ${result.seconds} s`);
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
    } finally {
      setRehearsing(false);
    }
  };

  const restoreLive = async () => {
    setBusy(true);
    try {
      await api.restore();
      push("green", "Restored the previous value", "Put back from before the outside edit");
      await resync();
      setWatch(await api.watch());
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const protectLive = async () => {
    if (!watch) return;
    setBusy(true);
    try {
      const result = await api.protect();
      push("green", "Older versions are protected", `Versions below ${result.limit} keep the previous value`);
      await resync();
      const live = watch.value;
      api.check(live, true).then((checked) => setCells(checked.cells)).catch(() => undefined);
      api.render(live).then((preview) => {
        setBefore(preview.before);
        setAfter(preview.after);
      }).catch(() => undefined);
      setWatch(await api.watch());
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const simulateEdit = async () => {
    try {
      await api.outsideEdit();
      push("amber", "Edited the config directly in Flagsmith", "Demo of an edit made in the dashboard");
      setWatch(await api.watch());
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
    }
  };

  const confirmApply = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.apply(parsed.value, includeMissing);
      setCells(result.cells);
      setApplied(true);
      push("green", "Fix applied", result.steps.map(plainStep).join(", "));
      await refresh();
      const preview = await api.render(parsed.value);
      setBefore(preview.before);
      setAfter(preview.after);
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
      void resync().catch(() => undefined);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  const confirmPublish = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.publish(parsed.value);
      setPublished(true);
      push("green", "Change published", result.steps.map(plainStep).join(", "));
      await refresh();
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
      void resync().catch(() => undefined);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  const refreshAfterStage = async (value: Record<string, unknown>) => {
    await resync();
    api.check(value, true).then((result) => setCells(result.cells)).catch(() => undefined);
    api.render(value).then((preview) => {
      setBefore(preview.before);
      setAfter(preview.after);
    }).catch(() => undefined);
  };

  const confirmStage = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.stageNext(parsed.value, includeMissing);
      setApplied(true);
      setPublished(true);
      push("green", `Stage ${result.stage + 1} applied`, result.steps.map(plainStep).join(", "));
      await refreshAfterStage(parsed.value);
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
      void resync().catch(() => undefined);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  const stageBack = async () => {
    if (!parsed.value) return;
    setBusy(true);
    try {
      const result = await api.stageBack(parsed.value, includeMissing);
      push("amber", result.stage < 0 ? "Rollout undone" : `Back to stage ${result.stage + 1}`, result.steps.map(plainStep).join(", "));
      await refreshAfterStage(parsed.value);
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
      void resync().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  const undo = async () => {
    setBusy(true);
    try {
      const result = await api.rollback();
      push("amber", "Rolled back", result.steps.map(plainStep).join(", "));
      const next = await refresh();
      setDraft(pretty(next.value));
      setApplied(false);
      setPublished(false);
      setCells([]);
      setPlan(null);
      setAfter(null);
      const live = await api.render();
      setBefore(live.before);
    } catch (error) {
      push("red", "Something went wrong", (error as Error).message);
      void resync().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <SurfaceBackdrop />
        <p className="text-sm text-status-red">Cannot reach the flagpact server: {loadError}</p>
      </main>
    );
  }

  const nextStage = (rollout?.current ?? -1) + 1;
  const stagePreview = rollout?.stages[nextStage];
  const planned = Boolean(plan?.limit);
  const steps: { label: string; state: StepState }[] = [
    { label: "Check change", state: hasChange && !checking ? "done" : "active" },
    { label: "Apply fix", state: applied || published ? "done" : planned ? "active" : "todo" },
    { label: "Publish", state: published ? "done" : applied ? "active" : "todo" },
    { label: "Undo if needed", state: applied || published ? "todo" : "off" },
  ];

  return (
    <div className="min-h-screen w-full">
      <SurfaceBackdrop />
      <TopBar
        canUndo={applied}
        busy={busy}
        onUndo={undo}
        onSimulate={simulateEdit}
        onHome={onHome}
        demo={new URLSearchParams(window.location.search).has("demo") || window.location.pathname.replace(/\/$/, "") === "/demo"}
      />
      <main className="w-full px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-6">
          <h1 className="font-display text-4xl font-medium">App version check</h1>
          <Stepper steps={steps} />
        </div>
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="min-w-0 space-y-6">
            <Notices lines={state?.notices ?? []} />
            {liveBroken && !editing && watch ? (
              <LiveAlert watch={watch} hasShares={hasShares} busy={busy} onProtect={protectLive} onRestore={restoreLive} />
            ) : (
            <SummaryCard
              cells={rows}
              hasChange={hasChange}
              checking={checking}
              total={state?.versions.length ?? 0}
              removed={removed}
              brokenVersions={brokenVersions}
              atRisk={hasShares && plan && !applied ? plan.at_risk : null}
              atRiskUsers={hasShares && plan && !applied ? plan.at_risk_users : null}
              done={published ? "published" : applied ? "applied" : null}
            />
            )}
            <ChangeEditor
              live={showCompare && watch?.previous ? watch.previous : state?.value ?? {}}
              draft={showCompare && watch ? pretty(watch.value) : draft}
              parsed={showCompare && watch ? watch.value : parsed.value}
              error={parsed.error}
              locked={applied || !state || showCompare}
              collapsed={(applied || published) && !showCompare}
              compare={showCompare}
              leftLabel={showCompare ? "Before the edit" : undefined}
              rightLabel={showCompare ? "Live in Flagsmith now" : undefined}
              onChange={setDraft}
              onBreak={() => setDraft(pretty(BREAKING))}
              onReset={() => state && setDraft(pretty(state.value))}
            />
            <ImpactTable
              rows={rows}
              meta={state?.meta ?? {}}
              missing={state?.missing ?? null}
              latest={state?.latest ?? ""}
              contracts={state?.contracts ?? {}}
              newValue={hasChange ? parsed.value : undefined}
              before={before}
              after={after}
              filter={filter}
              onFilter={setFilter}
              includeMissing={includeMissing}
              onToggleMissing={() => setIncludeMissing((v) => !v)}
              locked={applied}
              lastMs={lastMs}
              checkedAt={checkedAt}
            />
          </div>
          <aside className="min-w-0 space-y-6">
            <FixCard
              plan={plan}
              meta={state?.meta ?? {}}
              missing={state?.missing ?? null}
              includeMissing={includeMissing}
              onToggleMissing={() => setIncludeMissing((v) => !v)}
              applied={applied}
              published={published}
              busy={busy}
              dashboard={state?.dashboard ?? ""}
              onApply={() => setConfirm("apply")}
              onPublish={() => setConfirm("publish")}
              rehearsal={rehearsal}
              rehearsing={rehearsing}
              onRehearse={rehearse}
            />
            {!(liveBroken && !editing) && (rolloutLoading || rollout) && (
              <RolloutCard
                rollout={rollout}
                loading={rolloutLoading}
                busy={busy}
                hasShares={hasShares}
                pending={applied && !published}
                onNext={() => setConfirm("stage")}
                onBack={stageBack}
              />
            )}
            <ActivityCard entries={entries} />
          </aside>
        </div>
      </main>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm === "stage" ? `Roll out stage ${nextStage + 1}?` : confirm === "publish" ? "Publish your change?" : "Apply the fix?"}
        lines={
          confirm === "stage" && stagePreview
            ? [
                `${stagePreview.gets_change.join(", ")} get your change.`,
                stagePreview.kept.length ? `${stagePreview.kept.join(", ")} keep the previous value.` : "No version is held back.",
                "It is checked again against every app version when you confirm.",
              ]
            : confirm === "publish"
            ? ["Everyone on a newer version gets your change.", "Older versions keep the live value."]
            : [`Versions below ${plan?.limit ?? ""} keep the live value.`, "Your change is not published yet."]
        }
        details={confirm === "stage" && stagePreview ? [`segment ${rollout?.segment ?? ""}: app_version < ${stagePreview.boundary}`] : plan?.diff ?? []}
        busy={busy}
        confirmLabel={confirm === "stage" ? "Roll out" : confirm === "publish" ? "Publish" : "Apply the fix"}
        busyLabel="Working"
        onConfirm={confirm === "stage" ? confirmStage : confirm === "publish" ? confirmPublish : confirmApply}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
