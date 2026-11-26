import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { CheckIcon, XIcon } from "./icons";

type Tone = "green" | "red";

const VERSIONS = ["1.0.0", "2.0.0", "3.0.0"];

const PHASES: { caption: string; rows: { tone: Tone; text: string }[] }[] = [
  {
    caption: "Live value",
    rows: [
      { tone: "green", text: "Safe" },
      { tone: "green", text: "Safe" },
      { tone: "green", text: "Safe" },
    ],
  },
  {
    caption: "Pending change: a field is removed",
    rows: [
      { tone: "red", text: "Would break" },
      { tone: "red", text: "Would break" },
      { tone: "green", text: "Safe" },
    ],
  },
  {
    caption: "Fix: older versions keep the live value",
    rows: [
      { tone: "green", text: "Keeps live value" },
      { tone: "green", text: "Keeps live value" },
      { tone: "green", text: "Gets your change" },
    ],
  },
];

const STYLE: Record<Tone, string> = {
  green: "border-status-green/40 bg-status-green/10 text-status-green",
  red: "border-status-red/50 bg-status-red/10 text-status-red",
};

export function HeroPreview() {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState(reduce ? 2 : 0);

  useEffect(() => {
    if (reduce) {
      setPhase(2);
      return;
    }
    const id = window.setInterval(() => setPhase((p) => (p + 1) % PHASES.length), 2600);
    return () => window.clearInterval(id);
  }, [reduce]);

  const current = PHASES[phase];
  const spring = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 260, damping: 26 };

  return (
    <div className="panel p-5 shadow-surface" role="img" aria-label="Animated example: a config change breaks two app versions, then a fix keeps them on the live value">
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span />
        <span className="flex gap-1.5">
          {PHASES.map((_, i) => (
            <motion.span key={i} className="h-1.5 rounded-full bg-accent" animate={{ width: i === phase ? 20 : 6, opacity: i === phase ? 1 : 0.3 }} transition={spring} />
          ))}
        </span>
      </div>

      <div className="mt-4 h-5 overflow-hidden text-sm">
        <AnimatePresence mode="wait">
          <motion.p
            key={phase}
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? undefined : { opacity: 0, y: -10 }}
            transition={{ duration: reduce ? 0 : 0.22 }}
          >
            {current.caption}
          </motion.p>
        </AnimatePresence>
      </div>

      <ul className="mt-3 space-y-2.5">
        {VERSIONS.map((version, i) => {
          const row = current.rows[i];
          return (
            <motion.li
              key={version}
              layout
              className={`flex items-center justify-between rounded-lg border px-4 py-3 ${STYLE[row.tone]}`}
              animate={{ scale: row.tone === "red" ? 1.02 : 1 }}
              transition={spring}
            >
              <span className="flex items-center gap-3">
                {row.tone === "green" ? <CheckIcon size={16} /> : <XIcon size={16} />}
                <span className="font-mono text-sm text-ink-primary">{version}</span>
              </span>
              <AnimatePresence mode="wait">
                <motion.span
                  key={row.text}
                  className="text-sm"
                  initial={reduce ? false : { opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={reduce ? undefined : { opacity: 0, x: -8 }}
                  transition={{ duration: reduce ? 0 : 0.18 }}
                >
                  {row.text}
                </motion.span>
              </AnimatePresence>
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
