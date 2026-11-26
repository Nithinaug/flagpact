import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

type Props = {
  open: boolean;
  title: string;
  lines: string[];
  details: string[];
  busy: boolean;
  confirmLabel: string;
  busyLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({ open, title, lines, details, busy, confirmLabel, busyLabel, onConfirm, onCancel }: Props) {
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
            <ul className="my-4 space-y-2 text-sm text-ink-primary">
              {lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <details className="mb-4 text-xs text-ink-muted">
              <summary className="cursor-pointer">Technical details</summary>
              <ul className="mt-2 space-y-1">
                {details.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
            {busy && (
              <div className="mb-4" role="status">
                <div className="h-px overflow-hidden bg-border-subtle">
                  <motion.div
                    className="h-px w-1/3 bg-accent"
                    animate={{ x: ["-100%", "300%"] }}
                    transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
                  />
                </div>
                <p className="kicker mt-2">Writing to Flagsmith, then re-checking every app version</p>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button className="btn" disabled={busy} onClick={onCancel}>Cancel</button>
              <button ref={confirm} className="btn btn-primary" disabled={busy} onClick={onConfirm}>
                {busy ? busyLabel : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
