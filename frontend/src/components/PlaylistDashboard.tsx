"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { deletePlaylist, listPlaylists } from "@/lib/api";
import type { PlaylistSummary } from "@/lib/types";
import { btnSecondary } from "@/lib/ui";

interface PlaylistDashboardProps {
  onSelect: (slug: string, playlistName: string, step: 1 | 2 | 3) => void;
  onNew: () => void;
}

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function PlaylistRow({
  playlist,
  onSelect,
  onDeleted,
}: {
  playlist: PlaylistSummary;
  onSelect: (slug: string, playlistName: string, step: 1 | 2 | 3) => void;
  onDeleted: (slug: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trashRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const wasConfirming = useRef(false);
  const step = playlist.missing_count > 0 ? 2 : 3;

  // The trash button and the confirm row swap places, so keep focus with
  // the user: onto Cancel when confirming opens, back to trash when it closes.
  useEffect(() => {
    if (confirming) {
      cancelRef.current?.focus();
    } else if (wasConfirming.current) {
      trashRef.current?.focus();
    }
    wasConfirming.current = confirming;
  }, [confirming]);

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deletePlaylist(playlist.slug);
      onDeleted(playlist.slug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete.");
      setDeleting(false);
    }
  }

  if (confirming) {
    return (
      <li
        role="group"
        aria-label={`Confirm deleting ${playlist.playlist_name}`}
        className="rounded-lg border border-[var(--color-error)]/50 bg-[var(--color-surface)] px-4 py-3"
      >
        <p className="break-words text-sm text-[var(--color-text)]">
          Delete &ldquo;{playlist.playlist_name}&rdquo;?
        </p>
        {playlist.in_navidrome === false && (
          <p className="mt-1 text-xs text-[var(--color-warning)]">
            This playlist hasn&rsquo;t been created in Navidrome yet. Deleting it now loses all scan and
            download progress, with nothing saved anywhere else.
          </p>
        )}
        {error && (
          <p role="alert" className="mt-1 text-xs text-[var(--color-error)]">
            {error}
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="inline-flex min-h-10 items-center rounded-full bg-[var(--color-error)] px-5 text-sm font-semibold text-[var(--color-bg)] hover:opacity-90 disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
          <button
            ref={cancelRef}
            type="button"
            onClick={() => setConfirming(false)}
            disabled={deleting}
            className={`${btnSecondary} px-5`}
          >
            Cancel
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onSelect(playlist.slug, playlist.playlist_name, step)}
        className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-left transition-colors hover:border-[var(--color-accent)]"
      >
        <span className="min-w-0 break-words font-medium text-[var(--color-text)]">{playlist.playlist_name}</span>
        <span className="shrink-0 text-xs text-[var(--color-muted)]">
          {playlist.found_count} found · {playlist.missing_count} missing
        </span>
      </button>
      <button
        ref={trashRef}
        type="button"
        onClick={() => setConfirming(true)}
        aria-label={`Delete ${playlist.playlist_name}`}
        className="shrink-0 rounded-md p-2.5 text-[var(--color-muted)] transition-colors hover:text-[var(--color-error)]"
      >
        <TrashIcon />
      </button>
    </li>
  );
}

export default function PlaylistDashboard({ onSelect, onNew }: PlaylistDashboardProps) {
  const [playlists, setPlaylists] = useState<PlaylistSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    listPlaylists()
      .then((list) => {
        setPlaylists(list);
        setLoadError(null);
      })
      // Not setPlaylists([]): an unreachable backend must not read as
      // "No playlists yet", which looks like all progress was lost.
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load playlists."));
  }, [reloadKey]);

  function handleDeleted(slug: string) {
    setPlaylists((prev) => prev && prev.filter((p) => p.slug !== slug));
  }

  return (
    <div className="flex w-full max-w-2xl flex-col items-center gap-8">
      {/* The mascot art is the wordmark, so it doubles as the page heading. */}
      <h1>
        <Image
          src="/reaper-hero.png"
          alt="Reaper"
          width={643}
          height={668}
          priority
          sizes="(min-width: 640px) 346px, 269px"
          className="w-56 drop-shadow-[0_0_40px_color-mix(in_oklch,var(--color-accent)_25%,transparent)] sm:w-72"
        />
      </h1>

      <p className="max-w-md text-center text-sm text-[var(--color-muted)]">
        Reaper checks a Spotify playlist against your Navidrome library, downloads whatever&rsquo;s missing via
        Soulseek, and builds the playlist for you. Upload a CSV to start a new one, or pick up where you left
        off&nbsp;below.
      </p>

      <div className="flex w-full flex-col gap-6">
        <button
          type="button"
          onClick={onNew}
          className="w-full rounded-lg border border-dashed border-[var(--color-control-border)] py-6 text-sm font-medium text-[var(--color-muted)] transition-colors hover:border-[var(--color-accent-text)] hover:text-[var(--color-accent-text)]"
        >
          + New playlist from Exportify CSV
        </button>

        <div role="status" className="empty:hidden">
          {playlists === null && !loadError && (
            <p className="text-center text-sm text-[var(--color-muted)]">Loading playlists...</p>
          )}

          {playlists && playlists.length === 0 && (
            <p className="text-center text-sm text-[var(--color-muted)]">
              No playlists yet. Upload a CSV to get started.
            </p>
          )}
        </div>

        {loadError && (
          <div className="flex flex-col items-center gap-3 text-center">
            <p role="alert" className="text-sm text-[var(--color-error)]">
              {loadError}
            </p>
            <button type="button" onClick={() => setReloadKey((k) => k + 1)} className={btnSecondary}>
              Retry
            </button>
          </div>
        )}

        {playlists && playlists.length > 0 && (
          <section aria-labelledby="playlists-heading" className="flex flex-col gap-3">
            <h2 id="playlists-heading" className="sr-only">
              Your playlists
            </h2>
            <ul className="flex flex-col gap-3">
              {playlists.map((p) => (
                <PlaylistRow key={p.slug} playlist={p} onSelect={onSelect} onDeleted={handleDeleted} />
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
