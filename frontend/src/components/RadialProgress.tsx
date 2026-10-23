"use client";

interface RadialProgressProps {
  current?: number;
  total?: number;
  indeterminate?: boolean;
  size?: number;
  label?: string;
}

export default function RadialProgress({
  current = 0,
  total = 0,
  indeterminate = false,
  size = 120,
  label,
}: RadialProgressProps) {
  const stroke = Math.max(6, Math.round(size / 15));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = total > 0 ? Math.min(current / total, 1) : 0;
  const offset = indeterminate ? circumference * 0.7 : circumference * (1 - pct);

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        role="progressbar"
        aria-label={label || "Progress"}
        aria-valuemin={indeterminate ? undefined : 0}
        aria-valuemax={indeterminate ? undefined : total}
        aria-valuenow={indeterminate ? undefined : current}
        style={{ width: size, height: size }}
        className={indeterminate ? "animate-spin" : undefined}
      >
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }} aria-hidden="true">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="var(--color-border)"
            strokeWidth={stroke}
            fill="none"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="var(--color-accent)"
            strokeWidth={stroke}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={
              !indeterminate
                ? { transition: "stroke-dashoffset 0.4s cubic-bezier(0.25, 1, 0.5, 1)" }
                : undefined
            }
          />
        </svg>
      </div>
      {!indeterminate && total > 0 && (
        <span className="text-sm tabular-nums text-[var(--color-muted)]">
          {current}/{total}
        </span>
      )}
    </div>
  );
}
