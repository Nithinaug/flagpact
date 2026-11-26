import { AnimatePresence, motion } from "motion/react";
import type { Pane } from "../api";

type Props = { panes: Pane[]; mode: "live" | "preview" | "" };

export function AppPanes({ panes, mode }: Props) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="kicker">RUNNING_APPS</span>
        <span className="kicker">{mode === "preview" ? "PREVIEW_OF_PENDING_VALUE" : mode === "live" ? "LIVE_FLAGSMITH_VALUE" : "--"}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {panes.map((pane) => (
          <div key={pane.version} className="border border-border-subtle bg-canvas/50 p-3">
            <div className="mb-3 flex items-center justify-between">
              <span className="chip">{pane.version}</span>
              <span className="kicker">{pane.ok ? "RUNNING" : "CRASHED"}</span>
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={`${pane.ok}-${pane.output}`}
                initial={{ opacity: 0, y: 8 }}
                animate={pane.ok ? { opacity: 1, y: 0, x: 0 } : { opacity: 1, y: 0, x: [0, -5, 5, -3, 0] }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className={`min-h-16 break-words border p-3 text-sm ${pane.ok ? "border-border-strong text-ink-primary" : "border-status-red text-status-red"}`}
              >
                {pane.output || "no output"}
              </motion.div>
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  );
}
