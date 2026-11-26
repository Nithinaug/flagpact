import { SparkIcon, UndoIcon } from "./icons";

type Props = {
  canUndo: boolean;
  busy: boolean;
  onUndo: () => void;
  onSimulate: () => void;
  demo: boolean;
  onHome?: () => void;
};

export function TopBar({ canUndo, busy, onUndo, onSimulate, demo, onHome }: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle px-6 py-3">
      <div className="flex items-center gap-3 text-sm">
        {onHome ? (
          <button className="font-display text-lg font-medium hover:text-ink-muted" onClick={onHome}>flagpact</button>
        ) : (
          <span className="font-display text-lg font-medium">flagpact</span>
        )}
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
