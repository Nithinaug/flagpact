import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  lines: string[];
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({ open, title, lines, busy, onConfirm, onCancel }: Props) {
  const confirm = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirm.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open, onCancel]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-20 grid place-items-center bg-canvas/70 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            className="panel w-[min(32rem,92vw)] p-5"
            initial={{ y: 16, scale: 0.97 }}
            animate={{ y: 0, scale: 1 }}
            exit={{ y: 8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="confirm-title" className="font-display text-xl font-medium">{title}</h2>
            <ul className="my-4 space-y-2 font-mono text-xs text-ink-muted">
              {lines.map((line) => (
                <li key={line}>&gt; {line}</li>
              ))}
            </ul>
            <div className="flex justify-end gap-2">
              <button className="btn" onClick={onCancel}>Cancel</button>
              <button ref={confirm} className="btn btn-primary" disabled={busy} onClick={onConfirm}>
                {busy ? "Writing" : "Write to Flagsmith"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
