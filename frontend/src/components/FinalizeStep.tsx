"use client";

import { useId, useState } from "react";
import { startFinalize } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import type { FinalizeResult } from "@/lib/types";
import { btnPrimary, btnSecondary, inputClass, labelClass } from "@/lib/ui";
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
  const id = useId();

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
      <div role="status" className="flex flex-col items-center gap-4 text-center">
        <p className="break-words text-lg font-medium text-[var(--color-text)]">
          &ldquo;{r.display_name}&rdquo; {r.created ? "created" : "updated"} in Navidrome
        </p>
        <p className="text-sm text-[var(--color-muted)]">
          {r.track_count} tracks · {r.coverage_pct.toFixed(1)}% coverage
        </p>
        {r.missing_ranks.length > 0 && (
          <p className="text-xs text-[var(--color-warning)]">
            {r.missing_ranks.length} track{r.missing_ranks.length === 1 ? "" : "s"} still missing
          </p>
        )}
      </div>
    );
  }

  if (job?.status === "error") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p role="alert" className="max-w-lg break-words text-[var(--color-error)]">
          {job.error}
        </p>
        <button type="button" onClick={() => setJobId(null)} className={btnSecondary}>
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
          label="Finalize progress"
        />
        <p role="status" className="max-w-sm break-words text-center text-sm text-[var(--color-muted)]">
          {PHASE_LABELS[job.phase] || job.message || "Working..."}
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col items-center gap-4">
      <div className="w-full">
        <label htmlFor={`${id}-title`} className={labelClass}>
          Navidrome playlist name <span className="text-[var(--color-muted)]">(optional)</span>
        </label>
        <input
          id={`${id}-title`}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={playlistName}
          className={inputClass}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-[var(--color-error)]">
          {error}
        </p>
      )}
      <button type="button" onClick={handleStart} className={btnPrimary}>
        Rescan & Create Playlist
      </button>
    </div>
  );
}
