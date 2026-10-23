/** Shared Tailwind class strings, so buttons/inputs stay consistent across
 * steps instead of drifting copy-by-copy. */

export const btnPrimary =
  "inline-flex min-h-10 items-center justify-center rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] transition-opacity hover:opacity-90 disabled:opacity-50";

export const btnSecondary =
  "inline-flex min-h-10 items-center justify-center rounded-full border border-[var(--color-control-border)] px-6 py-2 text-sm text-[var(--color-text)] transition-colors hover:border-[var(--color-accent-text)] disabled:opacity-50";

/** Text-only control (back links, disclosure toggles) — padded out to a
 * 44px touch target without changing how it looks. */
export const btnText =
  "inline-flex min-h-10 items-center text-sm transition-colors";

export const inputClass =
  "w-full rounded-md border border-[var(--color-control-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-muted)]";

export const labelClass = "mb-1 block text-sm font-medium text-[var(--color-text)]";
