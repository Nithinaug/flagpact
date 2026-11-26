import { motion } from "motion/react";
import type { Cell } from "../api";
import { Counter } from "./Counter";
import { CheckIcon, HelpIcon, WarnIcon } from "./icons";

type Props = {
  cells: Cell[];
  hasChange: boolean;
  checking: boolean;
  total: number;
  removed: string[];
  brokenVersions: string[];
  atRisk: number | null;
  done: "applied" | "published" | null;
};

export function SummaryCard({ cells, hasChange, checking, total, removed, brokenVersions, atRisk, done }: Props) {
  const count = (state: string) => cells.filter((c) => c.state === state).length;
  const broken = count("red");
  const safe = count("green");
  const unchecked = count("amber");

  let tone = "border-border-subtle";
  let icon = <HelpIcon size={22} />;
  let iconTone = "bg-subtle text-ink-muted";
  let title = "No pending change";
  let body = "Edit the new value, or try a breaking change.";

  if (checking) {
    title = "Checking app versions";
    body = "Running each version's own tests against your change.";
  } else if (done) {
    tone = "border-status-green/40 bg-status-green/5";
    icon = <CheckIcon size={22} />;
    iconTone = "bg-status-green/15 text-status-green";
    title = done === "published" ? "Your change is published" : "The fix is in place";
    body = "";
  } else if (hasChange && broken > 0) {
    tone = "border-status-red/40 bg-status-red/5";
    icon = <WarnIcon size={22} />;
    iconTone = "bg-status-red/15 text-status-red";
    title = `${broken} of ${total} app versions would break`;
    body = "";
  } else if (hasChange) {
    tone = "border-status-green/40 bg-status-green/5";
    icon = <CheckIcon size={22} />;
    iconTone = "bg-status-green/15 text-status-green";
    title = `All ${total} app versions can read this change`;
    body = "None of the checked versions would break.";
  }

  const stats = [
    { label: "Would break", value: broken, tone: "text-status-red" },
    { label: "Not checked", value: unchecked, tone: "text-status-amber" },
    { label: "Safe", value: safe, tone: "text-status-green" },
  ];

  const totalRows = Math.max(cells.length, 1);
  const segments = [
    { key: "red", n: broken, color: "var(--status-red)" },
    { key: "amber", n: unchecked, color: "var(--status-amber)" },
    { key: "green", n: safe, color: "var(--status-green)" },
  ];
  const showStats = hasChange && !checking;

  return (
    <section className={`panel flex flex-wrap items-center gap-x-8 gap-y-5 p-6 ${tone}`}>
      <div className="flex min-w-0 flex-1 basis-96 items-center gap-5">
        <span className={`grid size-14 shrink-0 place-items-center rounded-xl ${iconTone}`}>{icon}</span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl font-medium">{title}</h2>
          {hasChange && broken > 0 && !done && !checking ? (
            <p className="mt-1 text-sm leading-relaxed text-ink-muted">
              Your change removes{" "}
              {removed.map((path, i) => (
                <span key={path}>
                  {i > 0 && (i === removed.length - 1 ? " and " : ", ")}
                  <code className="font-mono text-status-red">{path}</code>
                </span>
              ))}
              , which {brokenVersions.join(" and ")} still {brokenVersions.length > 1 ? "require" : "requires"}.
              {atRisk ? ` ${atRisk}% of sessions would see a broken banner.` : ""}
            </p>
          ) : (
            body && <p className="mt-1 text-sm leading-relaxed text-ink-muted">{body}</p>
          )}
          {showStats && (
            <div className="mt-4 flex h-2 w-full overflow-hidden rounded-full bg-subtle" role="img" aria-label={`${broken} would break, ${unchecked} not checked, ${safe} safe`}>
              {segments.map((segment) => (
                <motion.div
                  key={segment.key}
                  className="h-full"
                  style={{ backgroundColor: segment.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${(segment.n / totalRows) * 100}%` }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
      {showStats && (
        <dl className={`grid flex-1 basis-96 overflow-hidden rounded-xl border border-border-subtle ${atRisk !== null ? "grid-cols-4" : "grid-cols-3"}`}>
          {stats.map((stat) => (
            <div key={stat.label} className="border-r border-border-subtle px-5 py-4 last:border-r-0">
              <dd className={`text-3xl font-medium ${stat.tone}`}><Counter value={stat.value} /></dd>
              <dt className="mt-1 text-xs text-ink-muted">{stat.label}</dt>
            </div>
          ))}
          {atRisk !== null && (
            <div className="px-5 py-4">
              <dd className="text-3xl font-medium">{atRisk}%</dd>
              <dt className="mt-1 text-xs text-ink-muted">Sessions at risk</dt>
            </div>
          )}
        </dl>
      )}
    </section>
  );
}
