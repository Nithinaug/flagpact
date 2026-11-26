import { UndoIcon } from "./icons";

type Props = {
  flag: string;
  syncedAgo: number;
  canUndo: boolean;
  busy: boolean;
  onUndo: () => void;
};

export function TopBar({ flag, syncedAgo, canUndo, busy, onUndo }: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle px-6 py-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-display text-lg font-medium">flagpact</span>
        <span className="text-ink-muted">›</span>
        <span className="font-mono text-sm">{flag}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-2 text-xs text-ink-muted">
          <i className="inline-block size-1.5 rounded-full bg-status-green" />
          Connected · synced {syncedAgo}s ago
        </span>
        <button className="btn flex items-center gap-2" disabled={!canUndo || busy} onClick={onUndo}>
          <UndoIcon size={14} /> Undo
        </button>
      </div>
    </header>
  );
}
