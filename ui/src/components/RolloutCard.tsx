import { motion, useReducedMotion } from "motion/react";
import type { Rollout } from "../api";
import { CheckIcon, FlagIcon, UndoIcon, XIcon } from "./icons";

type Props = {
  rollout: Rollout | null;
  loading: boolean;
  busy: boolean;
  hasShares: boolean;
  pending: boolean;
  onNext: () => void;
  onBack: () => void;
};

export function RolloutCard({ rollout, loading, busy, hasShares, pending, onNext, onBack }: Props) {
  const reduce = useReducedMotion();
  const spring = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 220, damping: 28 };
  const stages = rollout?.stages ?? [];
  const current = rollout?.current ?? -1;
  const next = current + 1;
  const upcoming = stages[next];
  const done = stages.length > 0 && next >= stages.length;

  return (
    <details className="panel p-5" open={current >= 0 || undefined}>
      <summary className="flex cursor-pointer items-center gap-2 font-display text-xl font-medium">
        <FlagIcon size={16} className="text-ink-muted" /> Roll out in stages
      </summary>

      {loading && (
        <div className="mt-4" role="status">
          <div className="h-px overflow-hidden bg-border-subtle">
            <motion.div
              className="h-px w-1/3 bg-accent"
              animate={reduce ? undefined : { x: ["-100%", "300%"] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
            />
          </div>
          <p className="kicker mt-2">Checking every stage against every app version</p>
        </div>
      )}

      {!loading && rollout?.error && <p className="mt-4 text-sm text-ink-muted">No stages: {rollout.error}</p>}

      {!loading && stages.length > 0 && (
        <>
          <ol className="mt-4 space-y-2">
            {stages.map((stage, i) => {
              const applied = i <= current;
              const isNext = i === next && !done;
              const total = stage.gets_change.length + stage.kept.length;
              return (
                <motion.li
                  key={stage.boundary}
                  initial={reduce ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ ...spring, delay: reduce ? 0 : i * 0.06 }}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${isNext ? "border-border-strong bg-subtle" : "border-border-subtle"}`}
                >
                  <span
                    className={`relative grid size-6 shrink-0 place-items-center rounded-full border text-xs ${
                      applied ? "border-status-green bg-status-green/15 text-status-green" : stage.ok ? "border-border-strong text-ink-muted" : "border-status-red text-status-red"
                    }`}
                  >
                    {isNext && <motion.span layoutId="next-stage" transition={spring} className="absolute -inset-1 rounded-full border-2 border-accent" />}
                    {applied ? <CheckIcon size={13} /> : stage.ok ? i + 1 : <XIcon size={13} />}
                  </span>
                  <span className="min-w-0 flex-1 text-sm">
                    {stage.kept.length === 0 ? (stage.holds_missing ? "Every app version gets your change" : "Everyone gets your change") : `${stage.boundary} and newer get your change`}
                    <span className="block truncate text-xs text-ink-muted">
                      {stage.ok
                        ? stage.kept.length === 0
                          ? stage.holds_missing ? "Builds with no app_version keep the previous value" : "No version is held back"
                          : `${stage.kept.join(", ")} keep the previous value`
                        : `Would break ${stage.blocked.join(", ")}`}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-ink-muted">{hasShares ? `${Math.round(stage.share_new)}%` : `${stage.gets_change.length} of ${total}`}</span>
                </motion.li>
              );
            })}
          </ol>

          {pending && (
            <p className="mt-4 text-xs text-status-amber">A fix is applied but not published. Publish it or undo it before staging.</p>
          )}

          {done && <p className="mt-4 rounded-lg border border-status-green/30 bg-status-green/10 px-4 py-3 text-sm text-status-green">Every stage is applied</p>}

          {upcoming && !done && (
            <button className="btn btn-primary mt-4 w-full" disabled={busy || pending || !upcoming.ok} onClick={onNext}>
              Roll out stage {next + 1}
            </button>
          )}
          {current >= 0 && (
            <button className="btn mt-2 flex w-full items-center justify-center gap-2" disabled={busy} onClick={onBack}>
              <UndoIcon size={14} /> {current === 0 ? "Undo the rollout" : `Back to stage ${current}`}
            </button>
          )}
        </>
      )}
    </details>
  );
}
