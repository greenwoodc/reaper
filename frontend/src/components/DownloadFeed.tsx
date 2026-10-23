"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import type { TrackEvent } from "@/lib/types";

interface DownloadFeedProps {
  tracks: TrackEvent[];
  maxVisible?: number;
  /** How long a finished (succeeded/failed) track stays visible before it
   * fades out, in ms. */
  completedTtlMs?: number;
}

const STATUS_ICON: Record<TrackEvent["status"], ReactNode> = {
  searching: (
    <span aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]" />
  ),
  downloading: (
    <span aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]" />
  ),
  succeeded: (
    <span aria-hidden="true" className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--color-success)] text-[0.6rem] font-bold text-[var(--color-bg)]">
      ✓
    </span>
  ),
  failed: (
    <span aria-hidden="true" className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--color-error)] text-[0.6rem] font-bold text-[var(--color-bg)]">
      ✕
    </span>
  ),
};

const STATUS_LABEL: Record<TrackEvent["status"], string> = {
  searching: "Searching",
  downloading: "Downloading",
  succeeded: "Downloaded",
  failed: "Failed",
};

export default function DownloadFeed({ tracks, maxVisible = 8, completedTtlMs = 5000 }: DownloadFeedProps) {
  const [completedAt, setCompletedAt] = useState<Record<string, number>>({});
  const [prevTracks, setPrevTracks] = useState(tracks);
  const [now, setNow] = useState(() => Date.now());

  // Stamp the moment each track first reaches a terminal status. Adjusting
  // state directly during render (guarded by the prevTracks comparison) per
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  // rather than in a useEffect, which would double-render every update.
  if (tracks !== prevTracks) {
    setPrevTracks(tracks);
    const updates: Record<string, number> = {};
    for (const t of tracks) {
      if ((t.status === "succeeded" || t.status === "failed") && !(t.id in completedAt)) {
        // Reuse the already-ticked `now` state rather than calling Date.now()
        // fresh here — render must stay pure. `now` lags real time by at
        // most the 500ms tick interval, which is irrelevant for a 5s TTL.
        updates[t.id] = now;
      }
    }
    if (Object.keys(updates).length > 0) {
      setCompletedAt((prev) => ({ ...prev, ...updates }));
    }
  }

  // Re-render periodically so completed tracks age out even if no new
  // track events arrive in the meantime.
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(interval);
  }, []);

  const visible = tracks
    .filter((t) => {
      const at = completedAt[t.id];
      return at === undefined || now - at < completedTtlMs;
    })
    .slice(-maxVisible);

  if (visible.length === 0) {
    return (
      <p className="text-center text-xs text-[var(--color-muted)]">
        {tracks.length === 0
          ? "Waiting for the first search to start..."
          : "All caught up. Waiting for the next search..."}
      </p>
    );
  }

  // reducedMotion="user" drops the slide-in/out for prefers-reduced-motion
  // users while keeping the opacity fade.
  return (
    <MotionConfig reducedMotion="user">
      <div className="flex w-full flex-col gap-1.5 overflow-hidden">
        <AnimatePresence initial={false} mode="popLayout">
          {visible.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35, ease: [0.25, 1, 0.5, 1] }}
              className="flex items-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
            >
              {STATUS_ICON[t.status]}
              <span className="min-w-0 flex-1 truncate text-xs text-[var(--color-text)]">{t.track}</span>
              <span className="shrink-0 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                {STATUS_LABEL[t.status]}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
