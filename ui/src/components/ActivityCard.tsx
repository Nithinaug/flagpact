import { motion } from "motion/react";

export type Entry = { id: number; tone: "amber" | "red" | "green" | "idle"; title: string; sub: string; time: string };

const DOT: Record<Entry["tone"], string> = {
  amber: "bg-status-amber",
  red: "bg-status-red",
  green: "bg-status-green",
  idle: "bg-status-idle",
};

export function ActivityCard({ entries }: { entries: Entry[] }) {
  return (
    <section className="panel p-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-lg font-medium">Activity</h2>
        <span className="text-xs text-ink-muted">This session</span>
      </div>
      <ul role="log" aria-live="polite" className="mt-4 space-y-4">
        {entries.map((entry) => (
          <motion.li
            key={entry.id}
            layout
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="flex gap-3"
          >
            <i className={`mt-1.5 inline-block size-2.5 shrink-0 rounded-full ${DOT[entry.tone]}`} />
            <div className="min-w-0">
              <div className="text-sm">{entry.title}</div>
              <div className="text-xs text-ink-muted">{entry.sub ? `${entry.sub} · ` : ""}{entry.time}</div>
            </div>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}
