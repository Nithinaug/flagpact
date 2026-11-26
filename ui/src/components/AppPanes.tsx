import { AnimatePresence, motion } from "motion/react";
import type { Pane } from "../api";
import { plainCrash } from "../plain";

type Props = { panes: Pane[]; mode: "live" | "preview" | "" };

export function AppPanes({ panes, mode }: Props) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">What each app version shows</h3>
        <span className="kicker">{mode === "preview" ? "Preview with your new value" : mode === "live" ? "Live right now" : ""}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {panes.map((pane) => (
          <div key={pane.version} className="border border-border-subtle bg-canvas/50 p-3">
            <div className="mb-3 flex items-center justify-between">
              <span className="chip">App {pane.version}</span>
              <span className={`kicker ${pane.ok ? "" : "text-status-red"}`}>{pane.ok ? "Works" : "Crashes"}</span>
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={`${pane.ok}-${pane.output}`}
                initial={{ opacity: 0, y: 8 }}
                animate={pane.ok ? { opacity: 1, y: 0, x: 0 } : { opacity: 1, y: 0, x: [0, -5, 5, -3, 0] }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className={`min-h-20 break-words border p-3 text-sm ${pane.ok ? "border-border-strong text-ink-primary" : "border-status-red text-status-red"}`}
              >
                {pane.ok ? pane.output.replace("[BANNER] ", "") : plainCrash(pane.output)}
              </motion.div>
            </AnimatePresence>
          </div>
        ))}
      </div>
    </div>
  );
}
