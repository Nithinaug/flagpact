import { animate, stagger, svg } from "animejs";
import { useEffect, useRef } from "react";

type Props = { rows: number; rowHeight: number; run: number };

export function SignalLine({ rows, rowHeight, run }: Props) {
  const spine = useRef<SVGPathElement>(null);
  const packet = useRef<SVGCircleElement>(null);
  const height = rows * rowHeight;
  const ticks = Array.from({ length: rows }, (_, i) => i * rowHeight + rowHeight / 2);

  useEffect(() => {
    if (run === 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const spineEl = spine.current;
    const packetEl = packet.current;
    if (!spineEl || !packetEl) return;
    const length = spineEl.getTotalLength();
    spineEl.style.strokeDasharray = `${length}`;
    const drawn = animate(spineEl, { strokeDashoffset: [length, 0], duration: 600, ease: "outExpo" });
    const tickAnim = animate(".signal-tick", { strokeDashoffset: [10, 0], delay: stagger(120), duration: 400, ease: "outExpo" });
    const { translateX, translateY } = svg.createMotionPath(spineEl);
    const moved = animate(packetEl, { translateX, translateY, duration: 700, ease: "inOutQuad" });
    return () => {
      drawn.pause();
      tickAnim.pause();
      moved.pause();
    };
  }, [run]);

  return (
    <svg aria-hidden="true" className="absolute left-0 top-0" width="24" height={height} viewBox={`0 0 24 ${height}`}>
      <path ref={spine} d={`M12 0 V${height}`} stroke="var(--border-strong)" strokeWidth="1" fill="none" />
      {ticks.map((y) => (
        <path
          key={y}
          className="signal-tick"
          d={`M12 ${y} H24`}
          stroke="var(--ink-muted)"
          strokeWidth="1"
          strokeDasharray="10"
          fill="none"
        />
      ))}
      <circle ref={packet} cx="12" cy="0" r="3" fill="var(--accent)" />
    </svg>
  );
}
