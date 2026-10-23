"use client";

import { useEffect, useRef, useState } from "react";
import { cancelJob, confirmJob, getCleanupPreview, startDownload } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import { useJobLog } from "@/lib/useJobLog";
import type { CleanupPreview } from "@/lib/types";
import { btnPrimary, btnSecondary, btnText } from "@/lib/ui";
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
        No output yet. That&rsquo;s normal while Docker builds the sockseek image on first run,
        which can take several minutes with no visible progress.
      </p>
    );
  }
  return (
    <div className="max-h-64 overflow-y-auto font-mono text-xs leading-relaxed text-[var(--color-muted)]">
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
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
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
    setStarting(true);
    try {
      const j = await startDownload(slug);
      setCancelling(false);
      setJobId(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start download.");
    } finally {
      setStarting(false);
    }
  }

  async function handleCancel() {
    if (!jobId) return;
    setCancelling(true);
    setError(null);
    try {
      await cancelJob(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel.");
      setCancelling(false);
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
        <p role="status" className="text-lg font-medium text-[var(--color-text)]">
          {skipped ? "Nothing to download" : "Download & import complete"}
        </p>
        <button type="button" onClick={onDone} className={btnPrimary}>
          Continue to Finalize
        </button>
      </div>
    );
  }

  if (job?.status === "awaiting_confirmation") {
    return (
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <p role="alert" className="break-words text-[var(--color-warning)]">
          {job.message}
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            disabled={confirming}
            onClick={() => handleConfirm(true)}
            className={btnPrimary}
          >
            Continue anyway
          </button>
          <button
            type="button"
            disabled={confirming}
            onClick={() => handleConfirm(false)}
            className={btnSecondary}
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
        <p role="alert" className="break-words text-[var(--color-error)]">
          {job.error}
        </p>
        <button type="button" onClick={() => setJobId(null)} className={btnSecondary}>
          Try again
        </button>
        <button
          type="button"
          onClick={() => setShowLog((v) => !v)}
          aria-expanded={showLog}
          className={`${btnText} text-[var(--color-accent-text)] hover:opacity-80`}
        >
          {showLog ? "Hide" : "Show"} raw log
        </button>
        {showLog && (
          <div className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)]/60 p-3 text-left">
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
          label="Download progress"
        />
        <p role="status" className="max-w-sm break-words text-center text-sm text-[var(--color-muted)]">
          {PHASE_LABELS[job.phase] || job.message || "Working..."}
        </p>

        {job.rate_limit_seconds != null && (
          <RateLimitCountdown secondsRemaining={job.rate_limit_seconds} />
        )}

        {job.phase === "downloading" && <DownloadFeed tracks={job.tracks} />}

        {error && (
          <p role="alert" className="text-sm text-[var(--color-error)]">
            {error}
          </p>
        )}
        {/* Not offered during import: killing beets mid-move can strand files. */}
        {job.phase !== "importing" && (
          <button type="button" onClick={handleCancel} disabled={cancelling} className={btnSecondary}>
            {cancelling ? "Cancelling..." : "Cancel download"}
          </button>
        )}

        <button
          type="button"
          onClick={() => setShowLog((v) => !v)}
          aria-expanded={showLog}
          className={`${btnText} text-[var(--color-accent-text)] hover:opacity-80`}
        >
          {showLog ? "Hide" : "Show"} raw log
        </button>
        {showLog && (
          <div className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)]/60 p-3">
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
                <del className="decoration-[var(--color-muted)]">
                  {row.orig_artist} · {row.orig_title}
                </del>
                <span aria-hidden="true">{" → "}</span>
                <span className="sr-only"> becomes </span>
                <ins className="text-[var(--color-text)] no-underline">
                  {row.artist} · {row.title}
                </ins>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-[var(--color-error)]">
          {error}
        </p>
      )}
      <button type="button" onClick={handleStart} disabled={starting} className={btnPrimary}>
        {starting ? "Starting..." : "Start Download"}
      </button>
    </div>
  );
}
