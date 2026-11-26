import type { Pane } from "../api";
import { parseBanner } from "../lib/diff";
import { BanIcon } from "./icons";

export function MiniBanner({ pane }: { pane?: Pane | null }) {
  if (!pane) {
    return <div className="grid h-[68px] w-36 place-items-center rounded-lg border border-dashed border-border-strong text-xs text-ink-muted">Not previewed</div>;
  }
  if (!pane.ok) {
    return (
      <div className="flex h-[68px] w-36 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-status-red/60 bg-status-red/5 text-xs text-status-red">
        <BanIcon size={16} />
        Banner hidden
      </div>
    );
  }
  const banner = parseBanner(pane.output);
  return (
    <div className="flex h-[68px] w-36 flex-col justify-between rounded-lg border border-border-strong bg-subtle p-2">
      <div>
        <div className="truncate text-xs font-medium">{banner.title}</div>
        {banner.sub && <div className="truncate text-[10px] text-ink-muted">{banner.sub}</div>}
      </div>
      {banner.button && <span className="w-fit rounded-full bg-ink-primary px-2 py-0.5 text-[10px] text-canvas">{banner.button}</span>}
    </div>
  );
}
