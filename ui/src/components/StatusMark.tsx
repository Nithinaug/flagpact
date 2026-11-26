import { AnimatePresence, motion } from "motion/react";
import { LABELS, type Verdict } from "../api";

const COLORS: Record<Verdict, string> = {
  red: "var(--status-red)",
  amber: "var(--status-amber)",
  green: "var(--status-green)",
  idle: "var(--status-idle)",
};

export function StatusMark({ state }: { state: Verdict }) {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-xs">
      <motion.i
        className="inline-block size-1.5 rounded-full"
        animate={{ backgroundColor: COLORS[state], scale: [1, 1.9, 1] }}
        transition={{ type: "spring", stiffness: 300, damping: 18 }}
        key={state}
      />
      <span className="relative inline-block min-w-20 overflow-hidden">
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={state}
            className="inline-block"
            initial={{ y: 12, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -12, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            {LABELS[state]}
          </motion.span>
        </AnimatePresence>
      </span>
    </span>
  );
}
