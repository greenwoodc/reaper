"use client";

const STEPS = [
  { id: 1, label: "Upload & Scan" },
  { id: 2, label: "Download & Import" },
  { id: 3, label: "Finalize" },
] as const;

interface StepperProps {
  activeStep: 1 | 2 | 3;
  clickable: boolean;
  onStepClick?: (step: 1 | 2 | 3) => void;
}

export default function Stepper({ activeStep, clickable, onStepClick }: StepperProps) {
  return (
    <ol className="flex items-center justify-center gap-3 sm:gap-6">
      {STEPS.map((step, idx) => {
        const isActive = step.id === activeStep;
        const isDone = step.id < activeStep;
        return (
          <li key={step.id} className="flex items-center gap-3 sm:gap-6">
            <button
              type="button"
              disabled={!clickable}
              onClick={() => onStepClick?.(step.id)}
              className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-[var(--color-accent)] text-[var(--color-accent-contrast)]"
                  : isDone
                    ? "text-[var(--color-accent)]"
                    : "text-[var(--color-muted)]"
              } ${clickable ? "cursor-pointer hover:opacity-80" : "cursor-default"}`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs ${
                  isActive ? "border-[var(--color-accent-contrast)]" : "border-current"
                }`}
              >
                {step.id}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {idx < STEPS.length - 1 && (
              <span className="h-px w-6 bg-[var(--color-border)] sm:w-12" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
