import { SparkIcon, UndoIcon } from "./icons";

type Props = {
  flag: string;
  canUndo: boolean;
  busy: boolean;
  onUndo: () => void;
  onSimulate: () => void;
  demo: boolean;
};

export function TopBar({ flag, canUndo, busy, onUndo, onSimulate, demo }: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle px-6 py-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-display text-lg font-medium">flagpact</span>
        <span className="text-ink-muted">›</span>
        <span className="font-mono text-sm">{flag}</span>
      </div>
      <div className="flex items-center gap-3">
        {demo && (
          <button className="btn flex items-center gap-2" disabled={busy} onClick={onSimulate}>
            <SparkIcon size={14} /> Simulate a dashboard edit
          </button>
        )}
        <button className="btn flex items-center gap-2" disabled={!canUndo || busy} onClick={onUndo}>
          <UndoIcon size={14} /> Undo
        </button>
      </div>
    </header>
  );
}
