import { motion, useReducedMotion } from "motion/react";
import { ArrowIcon, ShieldIcon } from "./icons";
import type { ScanResult } from "../api";
import { HeroPreview } from "./HeroPreview";
import { ImportCard } from "./ImportCard";
import { SurfaceBackdrop } from "./SurfaceBackdrop";

export function HomePage({ onOpen, onImported }: { onOpen: () => void; onImported: (result: ScanResult) => void }) {
  const reduce = useReducedMotion();
  const spring = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 200, damping: 26 };
  const rise = (delay: number) => ({
    initial: reduce ? false : { opacity: 0, y: 16 },
    animate: { opacity: 1, y: 0 },
    transition: { ...spring, delay: reduce ? 0 : delay },
  });

  return (
    <div className="min-h-screen w-full">
      <SurfaceBackdrop />
      <header className="px-6 py-4">
        <span className="font-display text-lg font-medium">flagpact</span>
      </header>
      <main className="mx-auto w-full max-w-5xl px-6 pb-16 pt-10">
        <div className="grid items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <motion.h1 className="font-display text-5xl font-medium leading-tight" {...rise(0)}>
              Ship config changes without breaking old app versions
            </motion.h1>
            <motion.p className="mt-4 max-w-md text-lg leading-relaxed text-ink-muted" {...rise(0.08)}>
              Test a Flagsmith config change against every app version. Keep the ones it would break on the safe value.
            </motion.p>
          </div>
          <motion.div {...rise(0.2)}>
            <HeroPreview />
          </motion.div>
        </div>

        <div className="mt-14 grid items-start gap-6 md:grid-cols-2">
          <motion.section className="panel p-5" aria-labelledby="demo-title" {...rise(0.3)}>
            <h2 id="demo-title" className="flex items-center gap-2 font-display text-xl font-medium">
              <ShieldIcon size={16} className="text-ink-muted" /> Try the demo project
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-muted">
              Three app versions read one banner config from a local Flagsmith. Break it, see who crashes, fix it, and roll it out in stages.
            </p>
            <button className="btn btn-primary mt-5 flex w-full items-center justify-center gap-2" onClick={onOpen}>
              Open the console <ArrowIcon size={14} />
            </button>
          </motion.section>
          <motion.div {...rise(0.36)}>
            <ImportCard onImported={onImported} />
          </motion.div>
        </div>
      </main>
    </div>
  );
}
