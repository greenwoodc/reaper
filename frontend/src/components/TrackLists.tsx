"use client";

interface TrackRow {
  artist: string;
  title: string;
}

interface TrackListsProps {
  found: TrackRow[];
  missing: TrackRow[];
}

function TrackList({ tracks, emptyLabel }: { tracks: TrackRow[]; emptyLabel: string }) {
  if (tracks.length === 0) {
    return <p className="px-3 py-4 text-center text-xs text-[var(--color-muted)]">{emptyLabel}</p>;
  }
  return (
    <ul className="max-h-80 divide-y divide-[var(--color-border)] overflow-y-auto">
      {tracks.map((t, i) => (
        <li key={i} className="px-3 py-2 text-xs text-[var(--color-text)]">
          <span className="font-medium">{t.artist}</span>
          <span className="text-[var(--color-muted)]"> · {t.title}</span>
        </li>
      ))}
    </ul>
  );
}

export default function TrackLists({ found, missing }: TrackListsProps) {
  return (
    <div className="grid w-full gap-4 sm:grid-cols-2">
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-[var(--color-success)]">Found ({found.length})</h2>
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
          <TrackList tracks={found} emptyLabel="Nothing matched yet." />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-semibold text-[var(--color-warning)]">Missing ({missing.length})</h2>
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
          <TrackList tracks={missing} emptyLabel="Nothing missing. Full house." />
        </div>
      </div>
    </div>
  );
}
