import { motion, useMotionTemplate, useMotionValue, useSpring } from "motion/react";
import { useEffect } from "react";

export function SurfaceBackdrop() {
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.3);
  const sx = useSpring(x, { stiffness: 80, damping: 20 });
  const sy = useSpring(y, { stiffness: 80, damping: 20 });
  const left = useMotionTemplate`${sx}%`;
  const top = useMotionTemplate`${sy}%`;

  useEffect(() => {
    const move = (event: PointerEvent) => {
      x.set((event.clientX / window.innerWidth) * 100);
      y.set((event.clientY / window.innerHeight) * 100);
    };
    window.addEventListener("pointermove", move);
    return () => window.removeEventListener("pointermove", move);
  }, [x, y]);

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-canvas">
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: "radial-gradient(circle, var(--grid-dot) 1px, transparent 1px)",
          backgroundSize: "24px 24px",
          maskImage: "radial-gradient(ellipse at 50% 40%, black 30%, transparent 85%)",
        }}
      />
      <motion.div
        className="absolute h-[42rem] w-[42rem] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          left,
          top,
          background: "radial-gradient(circle, color-mix(in oklch, var(--accent) 9%, transparent), transparent 62%)",
        }}
      />
    </div>
  );
}
