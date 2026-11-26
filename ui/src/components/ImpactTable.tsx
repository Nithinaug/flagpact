import { LayoutGroup, motion } from "motion/react";
import { LABELS, MISSING, type Cell, type Meta, type Pane, type Read, type Verdict } from "../api";
import { compactUsers, pathPresent } from "../lib/diff";
import { plainReason } from "../plain";
import { ResultBadge, ShareBar } from "./Bits";
import { ArrowIcon, CheckIcon, XIcon } from "./icons";
import { MiniBanner } from "./MiniBanner";

export type Filter = "ALL" | Verdict;

type Props = {
  rows: Cell[];
  meta: Record<string, Meta>;
  missing: { share: number; users: number } | null;
  latest: string;
  contracts: Record<string, Read[]>;
  newValue?: Record<string, unknown>;
  before: Pane[];
  after: Pane[] | null;
  filter: Filter;
  onFilter: (filter: Filter) => void;
  includeMissing: boolean;
  onToggleMissing: () => void;
  locked: boolean;
  lastMs: number | null;
  checkedAt: string;
};

const EDGE: Record<Verdict, string> = {
  red: "var(--status-red)",
  amber: "var(--status-amber)",
  green: "var(--status-green)",
  idle: "var(--status-idle)",
};

const GRID = "grid grid-cols-[minmax(190px,1.1fr)_minmax(190px,1.2fr)_minmax(330px,1.5fr)_minmax(170px,1fr)] items-center gap-4";

function FieldChip({ read, value }: { read: Read; value?: Record<string, unknown> }) {
  const present = value ? pathPresent(value, read.path) : null;
  const required = !read.has_default;
  let tone = "border-border-strong text-ink-primary";
  let icon = null;
  let suffix = required ? "" : " opt";
  if (present === true) {
    tone = "border-status-green/30 text-status-green";
    icon = <CheckIcon size={12} />;
  } else if (present === false && required) {
    tone = "border-status-red/50 bg-status-red/10 text-status-red";
    icon = <XIcon size={12} />;
    suffix = " req";
  } else if (present === false) {
    tone = "border-border-strong text-ink-muted";
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-xs ${tone}`}>
      {icon}
      {read.path}
      {suffix}
    </span>
  );
}

export function ImpactTable(props: Props) {
  const { rows, meta, missing, latest, contracts, newValue, before, after, filter, onFilter, includeMissing, onToggleMissing, locked, lastMs, checkedAt } = props;
  const count = (state: Verdict) => rows.filter((r) => r.state === state).length;
  const tabs: { key: Filter; label: string; n: number; tone: string }[] = [
    { key: "ALL", label: "All", n: rows.length, tone: "text-ink-muted" },
    { key: "red", label: "Breaks", n: count("red"), tone: "text-status-red" },
    { key: "amber", label: LABELS.amber, n: count("amber"), tone: "text-status-amber" },
    { key: "green", label: LABELS.green, n: count("green"), tone: "text-status-green" },
  ];
  const visible = rows.filter((r) => filter === "ALL" || r.state === filter);

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <h2 className="font-display text-lg font-medium">Impact by app version</h2>
        <div role="group" aria-label="Filter by result" className="flex gap-1 rounded-lg border border-border-subtle p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              aria-pressed={filter === tab.key}
              onClick={() => onFilter(tab.key)}
              className={`rounded-md px-3 py-1 text-sm ${filter === tab.key ? "bg-subtle text-ink-primary" : "text-ink-muted"}`}
            >
              {tab.label} <span className={tab.tone}>{tab.n}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[960px]">
          <div className={`kicker-caps ${GRID} border-t border-border-subtle px-5 py-3`}>
            <span>App version</span>
            <span>Fields it reads</span>
            <span>Before → after</span>
            <span className="text-right">Result</span>
          </div>
          <LayoutGroup>
            {visible.map((row, index) => {
              const isMissing = row.version === MISSING;
              const info = isMissing ? missing : meta[row.version];
              const share = info?.share ?? null;
              return (
                <motion.div
                  layout
                  key={row.version}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30, delay: index * 0.05 }}
                  className={`${GRID} border-t border-border-subtle px-5 py-4`}
                  style={{ boxShadow: `inset 3px 0 0 ${EDGE[row.state]}` }}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      {isMissing ? (
                        <span className="chip border-dashed">no app_version</span>
                      ) : (
                        <span className="chip text-base">{row.version}</span>
                      )}
                      {!isMissing && <span className="text-sm text-ink-muted">{meta[row.version]?.platforms}</span>}
                      {!isMissing && row.version === latest && <span className="rounded bg-status-green/15 px-1.5 text-[10px] text-status-green">Latest</span>}
                    </div>
                    {share !== null && info && (
                      <div className="mt-3 flex items-center gap-3 text-sm text-ink-muted">
                        <ShareBar share={share} />
                        <span>{share}% · {compactUsers(info.users)} users</span>
                      </div>
                    )}
                  </div>
                  {isMissing ? (
                    <p className="col-span-2 pr-4 text-sm text-ink-muted">
                      Older builds that don't send <code className="font-mono text-ink-primary">app_version</code>. We can't tell what they read, so they're not checked.
                    </p>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-2">
                        {(contracts[row.version] ?? []).map((read) => (
                          <FieldChip key={read.path} read={read} value={newValue} />
                        ))}
                        {(contracts[row.version] ?? []).length === 0 && <span className="text-sm text-ink-muted">No recorded behaviour</span>}
                      </div>
                      <div className="flex items-center gap-3">
                        <MiniBanner pane={before.find((p) => p.version === row.version)} />
                        <ArrowIcon size={16} className="text-ink-muted" />
                        <MiniBanner pane={after ? after.find((p) => p.version === row.version) : null} />
                      </div>
                    </>
                  )}
                  <div className="flex flex-col items-end gap-2 text-right">
                    <ResultBadge state={row.state} />
                    {isMissing ? (
                      includeMissing ? (
                        <span className="text-sm text-status-green">Protected by the fix</span>
                      ) : (
                        <button className="text-sm text-status-amber hover:underline disabled:opacity-40" disabled={locked} onClick={onToggleMissing}>
                          Protect them in the fix →
                        </button>
                      )
                    ) : (
                      <span className="text-sm text-ink-muted">{plainReason(row.reason)}</span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </LayoutGroup>
          {visible.length === 0 && <p className="border-t border-border-subtle px-5 py-6 text-sm text-ink-muted">No app versions match this filter.</p>}
        </div>
      </div>
      <div className="flex flex-wrap justify-between gap-2 border-t border-border-subtle px-5 py-3 text-xs text-ink-muted">
        <span>Traffic share from your config</span>
        <span>{lastMs === null ? "Not checked yet" : `Last check ${(lastMs / 1000).toFixed(1)} s · ${checkedAt}`}</span>
      </div>
    </section>
  );
}
