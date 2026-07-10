"use client";

import { useEffect, useRef, useState } from "react";
import { getFound, uploadAndScan } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import type { PlaylistDetail, ScanResult } from "@/lib/types";
import RadialProgress from "./RadialProgress";
import TrackLists from "./TrackLists";

interface UploadStepProps {
  onScanned: (slug: string, playlistName: string, missingCount: number) => void;
}

export default function UploadStep({ onScanned }: UploadStepProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [rankCol, setRankCol] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [detail, setDetail] = useState<PlaylistDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const job = useJob(jobId);
  const result = job?.status === "done" ? (job.result as unknown as ScanResult | null) : null;

  useEffect(() => {
    if (!result) return;
    getFound(result.slug)
      .then(setDetail)
      .catch((err) => setDetailError(err instanceof Error ? err.message : "Failed to load track list."));
  }, [result]);

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
      });
      setJobId(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="flex w-full max-w-3xl flex-col items-center gap-6">
        <p className="text-lg font-medium text-[var(--color-text)]">Scan complete</p>
        <p className="text-sm text-[var(--color-muted)]">
          {result.found_count} already in your library, {result.missing_count} missing.
        </p>

        {detailError && <p className="text-sm text-[var(--color-error)]">{detailError}</p>}
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
          className="rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] hover:opacity-90"
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
        />
        <p className="max-w-xs truncate text-center text-sm text-[var(--color-muted)]">
          {job.message || "Scanning your Navidrome library..."}
        </p>
      </div>
    );
  }

  if (job?.status === "error") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-[var(--color-error)]">{job.error}</p>
        <button
          type="button"
          onClick={() => {
            setJobId(null);
            setSubmitting(false);
          }}
          className="rounded-full border border-[var(--color-border)] px-6 py-2 text-sm text-[var(--color-text)]"
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
          className="text-[var(--color-accent)] hover:underline"
        >
          Exportify
        </a>{" "}
        and upload the CSV here. Reaper checks every track against your Navidrome library and sorts them
        into what it already has and what it&rsquo;s missing.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
            Exportify CSV
          </label>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            required
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] file:mr-3 file:rounded-full file:border-0 file:bg-[var(--color-accent)] file:px-4 file:py-1.5 file:text-[var(--color-accent-contrast)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
            Playlist name <span className="text-[var(--color-muted)]">(optional)</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Defaults to the CSV filename"
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-muted)]"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--color-text)]">
            Rank column <span className="text-[var(--color-muted)]">(optional)</span>
          </label>
          <input
            type="text"
            value={rankCol}
            onChange={(e) => setRankCol(e.target.value)}
            placeholder="e.g. Rank — for countdown-style playlists"
            className="w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-muted)]"
          />
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            Only needed for countdown-style playlists — pick the CSV column that holds each track&rsquo;s rank
            (e.g. &ldquo;Rank&rdquo; or &ldquo;Position&rdquo;) so the final playlist keeps that order.
          </p>
        </div>
        {error && <p className="text-sm text-[var(--color-error)]">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-[var(--color-accent)] px-6 py-2 text-sm font-semibold text-[var(--color-accent-contrast)] hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Scanning..." : "Scan Navidrome"}
        </button>
      </form>
    </div>
  );
}
