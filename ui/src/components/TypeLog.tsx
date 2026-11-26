import { motion } from "motion/react";
import { useEffect, useRef } from "react";

export function TypeLog({ lines }: { lines: string[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [lines.length]);

  return (
    <div role="log" aria-live="polite" className="h-40 overflow-y-auto text-xs leading-relaxed text-ink-muted">
      {lines.map((line, i) => (
        <motion.div
          key={`${i}-${line}`}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {line}
        </motion.div>
      ))}
      <div ref={end} />
    </div>
  );
}
