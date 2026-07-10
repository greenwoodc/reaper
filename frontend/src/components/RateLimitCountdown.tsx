"use client";

import { useEffect, useState } from "react";

interface RateLimitCountdownProps {
  /** Unix ms timestamp when the rate limit is expected to clear. */
  resumeAt: number;
}

export default function RateLimitCountdown({ resumeAt }: RateLimitCountdownProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const remaining = Math.max(0, Math.ceil((resumeAt - now) / 1000));

  if (remaining <= 0) {
    // Hide once the countdown reaches zero rather than lingering on "0s"
    // until the next job poll confirms the backend cleared rate_limit_until.
    return null;
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-3 py-2 text-xs text-[var(--color-warning)]">
      <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-[var(--color-warning)]" />
      Soulseek search rate limit hit — resuming in {remaining}s
    </div>
  );
}
