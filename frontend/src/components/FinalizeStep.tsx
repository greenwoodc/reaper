"use client";

import { useState } from "react";
import { startFinalize } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import type { FinalizeResult } from "@/lib/types";
import RadialProgress from "./RadialProgress";

interface FinalizeStepProps {
  slug: string;
  playlistName: string;
}

const PHASE_LABELS: Record<string, string> = {
  rescanning: "Re-matching previously missing tracks...",
  waiting_for_navidrome_scan: "Waiting for Navidrome to finish indexing...",
  creating_playlist: "Creating/updating the Navidrome playlist...",
};

export default function FinalizeStep({ slug, playlistName }: FinalizeStepProps) {
  const [title, setTitle] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job = useJob(jobId);

  async function handleStart() {
    setError(null);
    try {
      const j = await startFinalize(slug, title.trim() || undefined);
      setJobId(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finalize.");
    }
  }

  if (job?.status === "done" && job.result) {
    const r = job.result as unknown as FinalizeResult;
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-lg font-medium text-[var(--color-text)]">
          &ldquo;{r.display_name}&rdquo; {r.created ? "created" : "updated"} in Navidrome
        </p>
        <p className="text-sm text-[var(--color-muted)]">
          {r.track_count} tracks — {r.coverage_pct.toFixed(1)}% coverage
        </p>
        {r.missing_ranks.length > 0 && (
          <p className="text-xs text-[var(--color-warning)]">
            {r.missing_ranks.length} ranks still missing
          </p>
        )}
      </div>
    );
  }

  if (job?.status === "error") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-[var(--color-error)]">{job.error}</p>
        <button
          type="button"
          onClick={() => setJobId(null)}
          className="rounded-full border border-[var(--color-border)] px-6 py-2 text-sm text-[var(--color-text)]"
        >
          Try again
        </button>
      </div>
    );
  }

  if (job && (job.status === "running" || job.status === "queued")) {
    return (
      <div className="flex flex-col items-center gap-4">
        <RadialProgress
          current={job.current}
          total={job.total}
          indeterminate={job.total === 0}
          size={120}
        />
        <p className="max-w-xs truncate text-center text-sm text-[var(--color-muted)]">
          {PHASE_LABELS[job.phase] || job.message || "Working..."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-4">
      <div className="w-full">
        <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
          Navidrome playlist name <span className="text-[var(--color-muted)]">(optional)</span>
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={playlistName}
          className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-muted)]"
        />
      </div>
      {error && <p className="text-sm text-[var(--color-error)]">{error}</p>}
      <button
        type="button"
        onClick={handleStart}
        className="rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] hover:opacity-90"
      >
        Rescan & Create Playlist
      </button>
    </div>
  );
}
