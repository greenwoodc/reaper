"use client";

import { useEffect, useRef, useState } from "react";
import { confirmJob, getCleanupPreview, startDownload } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import { useJobLog } from "@/lib/useJobLog";
import type { CleanupPreview } from "@/lib/types";
import RadialProgress from "./RadialProgress";
import DownloadFeed from "./DownloadFeed";
import RateLimitCountdown from "./RateLimitCountdown";

interface DownloadStepProps {
  slug: string;
  onDone: () => void;
}

const PHASE_LABELS: Record<string, string> = {
  cleaning: "Cleaning up search terms for Soulseek...",
  downloading: "Downloading missing tracks via Soulseek...",
  importing: "Importing downloaded files with beets...",
  uid_gid_check: "Waiting for confirmation...",
};

function LogPanel({ log, logEndRef }: { log: string[]; logEndRef: React.RefObject<HTMLDivElement | null> }) {
  if (log.length === 0) {
    return (
      <p className="text-xs text-[var(--color-muted)]">
        No output yet — this is normal while Docker builds the sockseek image on first run,
        which can take several minutes with no visible progress.
      </p>
    );
  }
  return (
    <div className="max-h-64 overflow-y-auto font-mono text-[11px] leading-relaxed text-[var(--color-muted)]">
      {log.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap">
          {line}
        </div>
      ))}
      <div ref={logEndRef} />
    </div>
  );
}

export default function DownloadStep({ slug, onDone }: DownloadStepProps) {
  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const job = useJob(jobId);
  const canShowLog = job?.status === "running" || job?.status === "queued" || job?.status === "error";
  const log = useJobLog(jobId, showLog && canShowLog);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "end" });
  }, [log]);

  useEffect(() => {
    getCleanupPreview(slug)
      .then(setPreview)
      .catch(() => setPreview(null));
  }, [slug]);

  async function handleStart() {
    setError(null);
    try {
      const j = await startDownload(slug);
      setJobId(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start download.");
    }
  }

  async function handleConfirm(confirm: boolean) {
    if (!jobId) return;
    setConfirming(true);
    try {
      const j = await confirmJob(jobId, confirm);
      setJobId(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm.");
    } finally {
      setConfirming(false);
    }
  }

  if (job?.status === "done") {
    const skipped = (job.result as { skipped?: boolean } | null)?.skipped;
    return (
      <div className="flex flex-col items-center gap-6 text-center">
        <p className="text-lg font-medium text-[var(--color-text)]">
          {skipped ? "Nothing to download" : "Download & import complete"}
        </p>
        <button
          type="button"
          onClick={onDone}
          className="rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] hover:opacity-90"
        >
          Continue to Finalize
        </button>
      </div>
    );
  }

  if (job?.status === "awaiting_confirmation") {
    return (
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <p className="text-[var(--color-warning)]">{job.message}</p>
        <div className="flex gap-3">
          <button
            type="button"
            disabled={confirming}
            onClick={() => handleConfirm(true)}
            className="rounded-full bg-[var(--color-accent)] px-5 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] disabled:opacity-50"
          >
            Continue anyway
          </button>
          <button
            type="button"
            disabled={confirming}
            onClick={() => handleConfirm(false)}
            className="rounded-full border border-[var(--color-border)] px-5 py-2 text-sm text-[var(--color-text)] disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (job?.status === "error") {
    return (
      <div className="flex w-full max-w-lg flex-col items-center gap-4 text-center">
        <p className="text-[var(--color-error)]">{job.error}</p>
        <button
          type="button"
          onClick={() => setJobId(null)}
          className="rounded-full border border-[var(--color-border)] px-6 py-2 text-sm text-[var(--color-text)]"
        >
          Try again
        </button>
        <button
          type="button"
          onClick={() => setShowLog((v) => !v)}
          className="text-xs text-[var(--color-accent)] hover:opacity-80"
        >
          {showLog ? "Hide" : "Show"} raw log
        </button>
        {showLog && (
          <div className="w-full rounded-md border border-[var(--color-border)] bg-black/40 p-3 text-left">
            <LogPanel log={log} logEndRef={logEndRef} />
          </div>
        )}
      </div>
    );
  }

  if (job && (job.status === "running" || job.status === "queued")) {
    return (
      <div className="flex w-full max-w-lg flex-col items-center gap-4">
        <RadialProgress
          current={job.current}
          total={job.total}
          indeterminate={job.total === 0}
          size={120}
        />
        <p className="max-w-xs truncate text-center text-sm text-[var(--color-muted)]">
          {PHASE_LABELS[job.phase] || job.message || "Working..."}
        </p>

        {job.rate_limit_seconds != null && (
          <RateLimitCountdown secondsRemaining={job.rate_limit_seconds} />
        )}

        {job.phase === "downloading" && <DownloadFeed tracks={job.tracks} />}

        <button
          type="button"
          onClick={() => setShowLog((v) => !v)}
          className="text-xs text-[var(--color-accent)] hover:opacity-80"
        >
          {showLog ? "Hide" : "Show"} raw log
        </button>
        {showLog && (
          <div className="w-full rounded-md border border-[var(--color-border)] bg-black/40 p-3">
            <LogPanel log={log} logEndRef={logEndRef} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-lg flex-col items-center gap-6">
      {preview && preview.changed.length > 0 && (
        <div className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="mb-2 text-sm font-medium text-[var(--color-text)]">
            {preview.changed.length} of {preview.total} search terms will be cleaned up for
            Soulseek:
          </p>
          <ul className="max-h-48 space-y-1 overflow-y-auto text-xs text-[var(--color-muted)]">
            {preview.changed.slice(0, 20).map((row, i) => (
              <li key={i}>
                <span className="line-through">
                  {row.orig_artist} — {row.orig_title}
                </span>
                {" → "}
                <span className="text-[var(--color-text)]">
                  {row.artist} — {row.title}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p className="text-sm text-[var(--color-error)]">{error}</p>}
      <button
        type="button"
        onClick={handleStart}
        className="rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] hover:opacity-90"
      >
        Start Download
      </button>
    </div>
  );
}
