import { CheckIcon, UndoIcon } from "./icons";

export type StepState = "done" | "active" | "todo" | "off";

type Props = { steps: { label: string; state: StepState }[] };

export function Stepper({ steps }: Props) {
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {steps.map((step, index) => {
        const tone =
          step.state === "done"
            ? "border-status-green/50 bg-status-green/10 text-status-green"
            : step.state === "active"
              ? "border-ink-primary/70 bg-subtle text-ink-primary"
              : step.state === "off"
                ? "border-dashed border-border-strong text-ink-muted/60"
                : "border-border-strong text-ink-muted";
        return (
          <li key={step.label} className="flex items-center gap-2">
            <span className={`pill ${tone}`}>
              {step.state === "done" ? (
                <CheckIcon size={14} />
              ) : step.label.startsWith("Undo") ? (
                <UndoIcon size={14} />
              ) : (
                <span className="grid size-5 place-items-center rounded-full border border-current text-[11px]">{index + 1}</span>
              )}
              {step.label}
            </span>
            {index < steps.length - 1 && <span className="h-px w-6 bg-border-strong" />}
          </li>
        );
      })}
    </ol>
  );
}
