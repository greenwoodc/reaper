"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ApiError, cancelJob, getFound, uploadAndScan } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import type { PlaylistDetail, ScanResult } from "@/lib/types";
import { btnPrimary, btnSecondary, inputClass, labelClass } from "@/lib/ui";
import RadialProgress from "./RadialProgress";
import TrackLists from "./TrackLists";

interface UploadStepProps {
  /** Fires as soon as the scan starts, with the name the backend settled on. */
  onStarted: (playlistName: string) => void;
  onScanned: (slug: string, playlistName: string, missingCount: number) => void;
}

export default function UploadStep({ onStarted, onScanned }: UploadStepProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [rankCol, setRankCol] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Set when the backend says the name is taken; the next submit replaces it.
  const [confirmReplace, setConfirmReplace] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [detail, setDetail] = useState<PlaylistDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const id = useId();

  const job = useJob(jobId);
  const result = job?.status === "done" ? (job.result as unknown as ScanResult | null) : null;

  useEffect(() => {
    if (!result) return;
    getFound(result.slug)
      .then(setDetail)
      .catch((err) => setDetailError(err instanceof Error ? err.message : "Failed to load track list."));
  }, [result]);

  async function handleCancel() {
    if (!jobId) return;
    setCancelling(true);
    try {
      await cancelJob(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel.");
      setCancelling(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose an Exportify CSV file first.");
      return;
    }
    setSubmitting(true);
    try {
      const j = await uploadAndScan({
        file,
        name: name.trim() || undefined,
        rankCol: rankCol.trim() || undefined,
        replace: confirmReplace,
      });
      setConfirmReplace(false);
      setCancelling(false);
      setJobId(j.id);
      onStarted(j.playlist_name);
    } catch (err) {
      setConfirmReplace(err instanceof ApiError && err.code === "playlist_exists");
      setError(err instanceof Error ? err.message : "Upload failed.");
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="flex w-full max-w-3xl flex-col items-center gap-6">
        <div role="status" className="flex flex-col items-center gap-1 text-center">
          <p className="text-lg font-medium text-[var(--color-text)]">Scan complete</p>
          <p className="text-sm text-[var(--color-muted)]">
            {result.found_count} already in your library, {result.missing_count} missing.
          </p>
        </div>

        {detailError && (
          <p role="alert" className="text-sm text-[var(--color-error)]">
            {detailError}
          </p>
        )}
        {!detail && !detailError && (
          <p className="text-sm text-[var(--color-muted)]">Loading track list...</p>
        )}
        {detail && (
          <TrackLists
            found={detail.found.map((t) => ({ artist: t.artist, title: t.title }))}
            missing={detail.missing.map((t) => ({ artist: t.artist, title: t.title }))}
          />
        )}

        <button
          type="button"
          onClick={() => onScanned(result.slug, result.playlist_name, result.missing_count)}
          className={btnPrimary}
        >
          Continue
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
          label="Scan progress"
        />
        <p role="status" className="max-w-sm break-words text-center text-sm text-[var(--color-muted)]">
          {cancelling ? "Cancelling..." : job.message || "Scanning your Navidrome library..."}
        </p>
        <button type="button" onClick={handleCancel} disabled={cancelling} className={btnSecondary}>
          Cancel scan
        </button>
      </div>
    );
  }

  if (job?.status === "error") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p role="alert" className="max-w-lg break-words text-[var(--color-error)]">
          {job.error}
        </p>
        <button
          type="button"
          onClick={() => {
            setJobId(null);
            setSubmitting(false);
          }}
          className={btnSecondary}
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-6">
      <p className="text-sm text-[var(--color-muted)]">
        Export a playlist from Spotify with{" "}
        <a
          href="https://exportify.net"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--color-accent-text)] underline-offset-2 hover:underline"
        >
          Exportify
        </a>{" "}
        and upload the CSV here.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label htmlFor={`${id}-file`} className={labelClass}>
            Exportify CSV
          </label>
          <input
            id={`${id}-file`}
            ref={fileRef}
            type="file"
            accept=".csv"
            required
            className={`${inputClass} file:mr-3 file:rounded-full file:border-0 file:bg-[var(--color-accent)] file:px-4 file:py-1.5 file:text-[var(--color-accent-contrast)]`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-name`} className={labelClass}>
            Playlist name <span className="text-[var(--color-muted)]">(optional)</span>
          </label>
          <input
            id={`${id}-name`}
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setConfirmReplace(false);
            }}
            placeholder="Defaults to the CSV filename"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor={`${id}-rank`} className={labelClass}>
            Rank column <span className="text-[var(--color-muted)]">(optional)</span>
          </label>
          <input
            id={`${id}-rank`}
            type="text"
            value={rankCol}
            onChange={(e) => setRankCol(e.target.value)}
            placeholder="e.g. Rank"
            aria-describedby={`${id}-rank-hint`}
            className={inputClass}
          />
          <p id={`${id}-rank-hint`} className="mt-1 text-xs text-[var(--color-muted)]">
            For countdown-style playlists: the CSV column holding each track&rsquo;s rank (e.g.
            &ldquo;Rank&rdquo; or &ldquo;Position&rdquo;), so the final playlist keeps that order.
          </p>
        </div>
        {error && (
          <p role="alert" className="text-sm text-[var(--color-error)]">
            {error}
            {confirmReplace && " Change the name above to keep both, or replace it."}
          </p>
        )}
        <button type="submit" disabled={submitting} className={btnPrimary}>
          {submitting ? "Scanning..." : confirmReplace ? "Replace and rescan" : "Scan Navidrome"}
        </button>
      </form>
    </div>
  );
}
