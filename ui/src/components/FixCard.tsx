import { motion } from "motion/react";
import { MISSING, type Meta, type Plan, type Rehearsal } from "../api";
import { CheckIcon, CloneIcon, ExternalIcon, ShieldIcon, SparkIcon, XIcon } from "./icons";

type Props = {
  plan: Plan | null;
  meta: Record<string, Meta>;
  missing: { share: number; users: number } | null;
  includeMissing: boolean;
  onToggleMissing: () => void;
  applied: boolean;
  published: boolean;
  busy: boolean;
  dashboard: string;
  onApply: () => void;
  onPublish: () => void;
  rehearsal: Rehearsal | null;
  rehearsing: boolean;
  onRehearse: () => void;
};

export function FixCard({ plan, meta, missing, includeMissing, onToggleMissing, applied, published, busy, dashboard, onApply, onPublish, rehearsal, rehearsing, onRehearse }: Props) {
  const hasFix = Boolean(plan?.limit);
  const brokenVersions = plan?.cells.filter((c) => c.state === "red" && c.version !== MISSING).map((c) => c.version) ?? [];
  const olderShare = brokenVersions.reduce((sum, v) => sum + (meta[v]?.share ?? 0), 0);
  const restShare = Object.entries(meta)
    .filter(([v]) => !brokenVersions.includes(v))
    .reduce((sum, [, m]) => sum + (m.share ?? 0), 0);
  const hasShares = Object.values(meta).some((m) => m.share !== null);
  const remaining = plan?.after ? plan.after.filter((c) => c.state === "red").length : 0;

  return (
    <section className="panel border-status-green/30 p-5">
      <div className="flex items-center gap-2 text-xs text-status-green">
        <SparkIcon size={14} />
        <span className="kicker-caps text-status-green">Suggested fix</span>
      </div>

      {!hasFix && !applied && !published ? (
        <p className="mt-3 text-sm leading-relaxed text-ink-muted">{plan?.error ?? "No fix needed until a change breaks an app version."}</p>
      ) : (
        <>
          <h2 className="mt-3 font-display text-xl font-medium">Keep older versions on the live value</h2>

          {hasFix && (applied || published) && (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer text-ink-muted">Show the rule</summary>
          <div className="mt-4 overflow-hidden rounded-lg border border-border-subtle">
            <div className="px-4 py-3">
              <div className="kicker-caps">If</div>
              <div className="mt-2 flex items-center gap-2">
                <code className="rounded bg-accent-alt/10 px-2 py-0.5 font-mono text-xs text-status-green">app_version</code>
                <span className="text-ink-muted">&lt;</span>
                <code className="rounded bg-subtle px-2 py-0.5 font-mono text-xs">{plan?.limit}</code>
              </div>
              <div className="mt-3 flex justify-between text-sm">
                <span>↑ Serve the live value</span>
                <span className="text-ink-muted">{brokenVersions.join(", ")}{hasShares ? ` · ${olderShare}%` : ""}</span>
              </div>
            </div>
            {missing && (
              <label className="flex cursor-pointer items-start gap-3 border-t border-border-subtle px-4 py-3">
                <input type="checkbox" className="mt-1 size-4 accent-[var(--status-green)]" checked={includeMissing} disabled={applied} onChange={onToggleMissing} />
                <span className="text-sm">
                  Also serve the live value when <code className="font-mono text-xs text-status-green">app_version</code> is missing
                  <span className="block text-xs text-ink-muted">Covers the {missing.share}% we couldn't check. Recommended.</span>
                </span>
              </label>
            )}
            <div className="border-t border-border-subtle px-4 py-3">
              <div className="kicker-caps">Everyone else</div>
              <div className="mt-2 flex justify-between text-sm">
                <span>↑ Serve your change</span>
                <span className="text-ink-muted">{plan?.limit}+{hasShares ? ` · ${restShare}%` : ""}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-ink-muted">After the fix</span>
            <span className="flex items-center gap-3">
              <span className={remaining === 0 ? "text-status-green" : "text-status-red"}>● {remaining} break</span>
              {plan?.protected !== undefined && hasShares && <span>{Math.round(plan.protected)}% protected</span>}
            </span>
          </div>
            </details>
          )}
          {hasFix && !applied && !published && (
            <>
          <div className="mt-4 overflow-hidden rounded-lg border border-border-subtle">
            <div className="px-4 py-3">
              <div className="kicker-caps">If</div>
              <div className="mt-2 flex items-center gap-2">
                <code className="rounded bg-accent-alt/10 px-2 py-0.5 font-mono text-xs text-status-green">app_version</code>
                <span className="text-ink-muted">&lt;</span>
                <code className="rounded bg-subtle px-2 py-0.5 font-mono text-xs">{plan?.limit}</code>
              </div>
              <div className="mt-3 flex justify-between text-sm">
                <span>↑ Serve the live value</span>
                <span className="text-ink-muted">{brokenVersions.join(", ")}{hasShares ? ` · ${olderShare}%` : ""}</span>
              </div>
            </div>
            {missing && (
              <label className="flex cursor-pointer items-start gap-3 border-t border-border-subtle px-4 py-3">
                <input type="checkbox" className="mt-1 size-4 accent-[var(--status-green)]" checked={includeMissing} disabled={applied} onChange={onToggleMissing} />
                <span className="text-sm">
                  Also serve the live value when <code className="font-mono text-xs text-status-green">app_version</code> is missing
                  <span className="block text-xs text-ink-muted">Covers the {missing.share}% we couldn't check. Recommended.</span>
                </span>
              </label>
            )}
            <div className="border-t border-border-subtle px-4 py-3">
              <div className="kicker-caps">Everyone else</div>
              <div className="mt-2 flex justify-between text-sm">
                <span>↑ Serve your change</span>
                <span className="text-ink-muted">{plan?.limit}+{hasShares ? ` · ${restShare}%` : ""}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-ink-muted">After the fix</span>
            <span className="flex items-center gap-3">
              <span className={remaining === 0 ? "text-status-green" : "text-status-red"}>● {remaining} break</span>
              {plan?.protected !== undefined && hasShares && <span>{Math.round(plan.protected)}% protected</span>}
            </span>
          </div>
            </>
          )}

          {!applied && !published && (
            <div className="mt-4">
              {rehearsing ? (
                <div role="status">
                  <div className="h-px overflow-hidden bg-border-subtle">
                    <motion.div className="h-px w-1/3 bg-status-green" animate={{ x: ["-100%", "300%"] }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }} />
                  </div>
                  <p className="mt-2 text-xs text-ink-muted">Cloning the environment, applying the fix and probing every version</p>
                </div>
              ) : rehearsal ? (
                <div className={`rounded-lg border px-4 py-3 ${rehearsal.ok ? "border-status-green/30 bg-status-green/5" : "border-status-red/40 bg-status-red/5"}`}>
                  <ul className="space-y-1.5 text-sm">
                    {rehearsal.rows.map((row) => (
                      <li key={row.version} className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2">
                          {row.ok ? <CheckIcon size={14} className="text-status-green" /> : <XIcon size={14} className="text-status-red" />}
                          <span className="font-mono text-xs">{row.version === MISSING ? "no app_version" : row.version}</span>
                        </span>
                        <span className="text-xs text-ink-muted">{row.expects === "old" ? "keeps the live value" : "gets your change"}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-ink-muted">
                    {rehearsal.ok ? "Verified on a real clone of the environment" : "The clone did not behave as planned"} · {rehearsal.seconds} s · clone deleted
                  </p>
                </div>
              ) : (
                <button className="btn flex w-full items-center justify-center gap-2" disabled={busy} onClick={onRehearse}>
                  <CloneIcon size={14} /> Rehearse on a clone
                </button>
              )}
            </div>
          )}

          {published ? (
            <p className="mt-4 rounded-lg border border-status-green/30 bg-status-green/10 px-4 py-3 text-sm text-status-green">Published. Use Undo to go back.</p>
          ) : applied ? (
            <button className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-status-green px-4 py-3 font-medium text-accent-ink" disabled={busy} onClick={onPublish}>
              Publish your change
            </button>
          ) : (
            <button className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-status-green px-4 py-3 font-medium text-accent-ink disabled:opacity-50" disabled={busy || rehearsing || (rehearsal !== null && !rehearsal.ok)} onClick={onApply}>
              <ShieldIcon size={16} /> Apply the fix
            </button>
          )}
          {dashboard && (
            <a href={dashboard} target="_blank" rel="noreferrer" className="mt-3 flex items-center justify-center gap-1.5 text-sm text-ink-muted hover:text-ink-primary">
              Preview rule in Flagsmith <ExternalIcon size={13} />
            </a>
          )}
        </>
      )}
    </section>
  );
}
