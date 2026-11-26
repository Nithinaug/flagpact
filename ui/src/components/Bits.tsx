import { animate } from "animejs";
import { useEffect, useRef } from "react";
import type { Verdict } from "../api";
import { LABELS } from "../api";
import { CheckIcon, HelpIcon, XIcon } from "./icons";

export function ShareBar({ share }: { share: number }) {
  const fill = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = fill.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if (el) el.style.width = `${share}%`;
      return;
    }
    const run = animate(el, { width: ["0%", `${share}%`], duration: 700, ease: "outExpo" });
    return () => {
      run.pause();
    };
  }, [share]);
  return (
    <div className="h-1.5 w-28 overflow-hidden rounded-full bg-subtle">
      <div ref={fill} className="h-full rounded-full bg-ink-muted" style={{ width: `${share}%` }} />
    </div>
  );
}

const TONE: Record<Verdict, string> = {
  red: "border-status-red/40 bg-status-red/10 text-status-red",
  amber: "border-status-amber/40 bg-status-amber/10 text-status-amber",
  green: "border-status-green/40 bg-status-green/10 text-status-green",
  idle: "border-border-strong text-ink-muted",
};

export function ResultBadge({ state }: { state: Verdict }) {
  const Icon = state === "red" ? XIcon : state === "green" ? CheckIcon : HelpIcon;
  return (
    <span className={`pill ${TONE[state]}`}>
      <Icon size={14} />
      {LABELS[state]}
    </span>
  );
}
