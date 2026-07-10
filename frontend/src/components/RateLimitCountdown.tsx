"use client";

import { useEffect, useState } from "react";

interface RateLimitCountdownProps {
  /** Seconds remaining, as computed fresh by the backend on the most recent
   * poll (using only its own clock). */
  secondsRemaining: number;
}

export default function RateLimitCountdown({ secondsRemaining }: RateLimitCountdownProps) {
  const [displayed, setDisplayed] = useState(secondsRemaining);
  const [prevProp, setPrevProp] = useState(secondsRemaining);

  // Resync to the server's fresh value whenever a new poll arrives, rather
  // than ever comparing timestamps across the two machines' clocks — see
  // the note on Job.rate_limit_seconds for why that broke intermittently.
  if (secondsRemaining !== prevProp) {
    setPrevProp(secondsRemaining);
    setDisplayed(secondsRemaining);
  }

  // Between polls, tick down locally using only this machine's own clock.
  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayed((d) => Math.max(0, d - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (displayed <= 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-3 py-2 text-xs text-[var(--color-warning)]">
      <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-[var(--color-warning)]" />
      Soulseek search rate limit hit — resuming in {displayed}s
    </div>
  );
}
