import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { api, type ScanResult } from "../api";
import { CloneIcon, WarnIcon } from "./icons";

export function ImportCard({ onImported }: { onImported: (result: ScanResult) => void }) {
  const reduce = useReducedMotion();
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const scan = async () => {
    setLoading(true);
    setError("");
    try {
      onImported(await api.importScan(source));
    } catch (failure) {
      setError((failure as Error).message);
      setLoading(false);
    }
  };

  return (
    <section className="panel p-5" aria-labelledby="import-title">
      <h2 id="import-title" className="flex items-center gap-2 font-display text-xl font-medium">
        <CloneIcon size={16} className="text-ink-muted" /> Start from your own project
      </h2>
      <p className="mt-1 text-sm leading-relaxed text-ink-muted">
        Paste a public GitHub repository. flagpact reads the code without running it.
      </p>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (source.trim() && !loading) void scan();
        }}
      >
        <label className="sr-only" htmlFor="import-source">GitHub repository URL</label>
        <input
          id="import-source"
          className="min-w-0 flex-1 rounded-lg border border-border-strong bg-transparent px-3 py-2 font-mono text-xs text-ink-primary placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          placeholder="https://github.com/owner/repo"
          value={source}
          maxLength={300}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => setSource(event.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !source.trim()}>
          {loading ? "Scanning" : "Scan"}
        </button>
      </form>

      {loading && (
        <div className="mt-4" role="status">
          <div className="h-px overflow-hidden bg-border-subtle">
            <motion.div
              className="h-px w-1/3 bg-accent"
              animate={reduce ? undefined : { x: ["-100%", "300%"] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
            />
          </div>
          <p className="kicker mt-2">Reading source files, nothing is run</p>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 flex items-start gap-2 text-sm text-status-red">
          <WarnIcon size={15} className="mt-0.5 shrink-0" /> {error}
        </p>
      )}
    </section>
  );
}
