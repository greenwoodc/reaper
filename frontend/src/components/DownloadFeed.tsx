"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { TrackEvent } from "@/lib/types";

interface DownloadFeedProps {
  tracks: TrackEvent[];
  maxVisible?: number;
}

const STATUS_ICON: Record<TrackEvent["status"], ReactNode> = {
  searching: (
    <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]" />
  ),
  downloading: (
    <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]" />
  ),
  succeeded: (
    <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--color-success)] text-[10px] font-bold text-black">
      ✓
    </span>
  ),
  failed: (
    <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--color-error)] text-[10px] font-bold text-black">
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

export default function DownloadFeed({ tracks, maxVisible = 8 }: DownloadFeedProps) {
  const visible = tracks.slice(-maxVisible);

  if (visible.length === 0) {
    return (
      <p className="text-center text-xs text-[var(--color-muted)]">
        Waiting for the first search to start...
      </p>
    );
  }

  return (
    <div className="flex w-full flex-col gap-1.5 overflow-hidden">
      <AnimatePresence initial={false} mode="popLayout">
        {visible.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="flex items-center gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
          >
            {STATUS_ICON[t.status]}
            <span className="min-w-0 flex-1 truncate text-xs text-[var(--color-text)]">{t.track}</span>
            <span className="shrink-0 text-[10px] uppercase tracking-wide text-[var(--color-muted)]">
              {STATUS_LABEL[t.status]}
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
