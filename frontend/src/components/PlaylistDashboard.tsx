"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { listPlaylists } from "@/lib/api";
import type { PlaylistSummary } from "@/lib/types";

interface PlaylistDashboardProps {
  onSelect: (slug: string, playlistName: string, step: 1 | 2 | 3) => void;
  onNew: () => void;
}

export default function PlaylistDashboard({ onSelect, onNew }: PlaylistDashboardProps) {
  const [playlists, setPlaylists] = useState<PlaylistSummary[] | null>(null);

  useEffect(() => {
    listPlaylists()
      .then(setPlaylists)
      .catch(() => setPlaylists([]));
  }, []);

  return (
    <div className="flex w-full max-w-2xl flex-col items-center gap-8">
      <Image
        src="/reaper-hero.png"
        alt="Reaper"
        width={643}
        height={668}
        priority
        className="w-56 drop-shadow-[0_0_40px_rgba(179,66,58,0.25)] sm:w-72"
      />

      <div className="flex w-full flex-col gap-6">
        <button
          type="button"
          onClick={onNew}
          className="w-full rounded-lg border border-dashed border-[var(--color-border)] py-6 text-sm font-medium text-[var(--color-muted)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          + New playlist from Exportify CSV
        </button>

        {playlists === null && (
          <p className="text-center text-sm text-[var(--color-muted)]">Loading playlists...</p>
        )}

        {playlists && playlists.length === 0 && (
          <p className="text-center text-sm text-[var(--color-muted)]">
            No playlists yet — upload a CSV to get started.
          </p>
        )}

        {playlists && playlists.length > 0 && (
          <ul className="flex flex-col gap-3">
            {playlists.map((p) => {
              const step = p.missing_count > 0 ? 2 : 3;
              return (
                <li key={p.slug}>
                  <button
                    type="button"
                    onClick={() => onSelect(p.slug, p.playlist_name, step)}
                    className="flex w-full items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-left transition-colors hover:border-[var(--color-accent)]"
                  >
                    <span className="font-medium text-[var(--color-text)]">{p.playlist_name}</span>
                    <span className="text-xs text-[var(--color-muted)]">
                      {p.found_count} found · {p.missing_count} missing
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
