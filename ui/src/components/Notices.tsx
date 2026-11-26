import { WarnIcon } from "./icons";

export function Notices({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <section role="note" className="panel flex items-start gap-3 border-status-amber/40 bg-status-amber/5 px-5 py-4">
      <WarnIcon size={18} className="mt-0.5 shrink-0 text-status-amber" />
      <ul className="space-y-1 text-sm">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
