import { motion } from "motion/react";
import type { Watch } from "../api";
import { WarnIcon } from "./icons";

type Props = { watch: Watch; hasShares: boolean; busy: boolean; onProtect: () => void; onRestore: () => void };

export function LiveAlert({ watch, hasShares, busy, onProtect, onRestore }: Props) {
  const names = watch.broken.join(" and ");
  return (
    <motion.section
      role="alert"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="panel flex flex-wrap items-center justify-between gap-5 border-status-red/50 bg-status-red/5 p-6"
    >
      <div className="flex min-w-0 flex-1 basis-96 items-center gap-5">
        <motion.span
          className="grid size-14 shrink-0 place-items-center rounded-xl bg-status-red/15 text-status-red"
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
        >
          <WarnIcon size={22} />
        </motion.span>
        <div className="min-w-0">
          <h2 className="font-display text-xl font-medium">Live value breaks {names} right now</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Watch mode caught a change made outside flagpact
            {hasShares && watch.at_risk ? `. ${watch.at_risk}% of sessions are affected` : ""}
          </p>
        </div>
      </div>
      {watch.previous ? (
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-primary" disabled={busy} onClick={onProtect}>
            {busy ? "Protecting" : "Protect older versions"}
          </button>
          <button className="btn" disabled={busy || !watch.restore} onClick={onRestore}>
            Restore previous value
          </button>
        </div>
      ) : (
        <span className="text-sm text-ink-muted">No earlier safe value is known</span>
      )}
    </motion.section>
  );
}
