import { useMemo, useState } from "react";
import { diffLines, fieldCounts, pretty } from "../lib/diff";
import { CheckIcon, SparkIcon, UndoIcon } from "./icons";

const LINE = 24;

type Props = {
  live: Record<string, unknown>;
  draft: string;
  parsed: Record<string, unknown> | undefined;
  error: string | undefined;
  locked: boolean;
  collapsed: boolean;
  onChange: (text: string) => void;
  onBreak: () => void;
  onReset: () => void;
};

function Gutter({ count, marks }: { count: number; marks: Map<number, string> }) {
  return (
    <div aria-hidden="true" className="code select-none pr-2 text-right text-ink-muted/50">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} style={{ height: LINE }}>{marks.has(i) ? <span className={marks.get(i)}>{i + 1}</span> : i + 1}</div>
      ))}
    </div>
  );
}

export function ChangeEditor({ live, draft, parsed, error, locked, collapsed, onChange, onBreak, onReset }: Props) {
  const liveLines = useMemo(() => pretty(live).split("\n"), [live]);
  const draftLines = useMemo(() => draft.split("\n"), [draft]);
  const diff = useMemo(() => diffLines(liveLines, draftLines), [liveLines, draftLines]);
  const counts = parsed ? fieldCounts(live, parsed) : { removed: 0, added: 0 };
  const rows = Math.max(liveLines.length, draftLines.length, 7);
  const [expanded, setExpanded] = useState(false);

  const leftMarks = new Map([...diff.removed].map((i) => [i, "text-status-red"]));
  const rightMarks = new Map([...diff.added].map((i) => [i, "text-status-green"]));

  if (collapsed && !expanded) {
    return (
      <section className="panel flex items-center justify-between gap-3 px-5 py-4">
        <div className="flex items-baseline gap-3">
          <h2 className="font-display text-lg font-medium">Your change</h2>
          <span className="text-sm text-ink-muted">Now matches what is live</span>
        </div>
        <button className="btn" onClick={() => setExpanded(true)}>Show</button>
      </section>
    );
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="flex items-baseline gap-3">
          <h2 className="font-display text-lg font-medium">Your change</h2>
          <span className="code text-ink-muted">
            -{counts.removed} fields · +{counts.added} fields
          </span>
        </div>
        <div className="flex gap-2">
          <button className="btn flex items-center gap-2" disabled={locked} onClick={onBreak}>
            <SparkIcon size={14} /> Try a breaking change
          </button>
          <button className="btn flex items-center gap-2" disabled={locked} onClick={onReset}>
            <UndoIcon size={14} /> Reset to live
          </button>
        </div>
      </div>
      <div className="grid border-t border-border-subtle md:grid-cols-2">
        <div className="border-b border-border-subtle md:border-b-0 md:border-r">
          <div className="kicker-caps flex justify-between bg-subtle/40 px-5 py-2">
            <span>Live in Flagsmith</span>
          </div>
          <div className="flex px-3 py-4">
            <Gutter count={rows} marks={leftMarks} />
            <div className="code relative min-w-0 flex-1 overflow-x-auto">
              {Array.from({ length: rows }, (_, i) => (
                <div key={i} className={`whitespace-pre pl-2 ${diff.removed.has(i) ? "bg-status-red/10" : ""}`} style={{ height: LINE }}>
                  {diff.removed.has(i) && <span className="mr-2 text-status-red">-</span>}
                  {liveLines[i] ?? ""}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div>
          <div className="kicker-caps flex items-center justify-between bg-subtle/40 px-5 py-2">
            <span>New value to publish</span>
            {error ? (
              <span className="normal-case tracking-normal text-status-red">{error}</span>
            ) : (
              <span className="flex items-center gap-1 normal-case tracking-normal text-status-green"><CheckIcon size={12} /> Valid JSON</span>
            )}
          </div>
          <div className="flex px-3 py-4">
            <Gutter count={rows} marks={rightMarks} />
            <div className="relative min-w-0 flex-1" style={{ height: rows * LINE }}>
              <div aria-hidden="true" className="code absolute inset-0">
                {Array.from({ length: rows }, (_, i) => (
                  <div key={i} className={diff.added.has(i) ? "bg-status-green/10" : ""} style={{ height: LINE }} />
                ))}
              </div>
              <textarea
                aria-label="New value to publish"
                spellCheck={false}
                wrap="off"
                disabled={locked}
                value={draft}
                onChange={(event) => onChange(event.target.value)}
                className="code absolute inset-0 resize-none overflow-hidden bg-transparent pl-6 text-ink-primary outline-none"
                style={{ height: rows * LINE }}
              />
              <div aria-hidden="true" className="code pointer-events-none absolute left-1 top-0 text-status-green">
                {Array.from({ length: rows }, (_, i) => (
                  <div key={i} style={{ height: LINE }}>{diff.added.has(i) ? "+" : ""}</div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
