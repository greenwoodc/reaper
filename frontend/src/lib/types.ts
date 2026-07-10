export type JobStatus =
  | "queued"
  | "running"
  | "awaiting_confirmation"
  | "done"
  | "error";

export type JobKind = "scan" | "download" | "finalize";

export type TrackJobStatus = "searching" | "downloading" | "succeeded" | "failed";

export interface TrackEvent {
  id: string;
  track: string;
  status: TrackJobStatus;
  seq: number;
}

export interface Job {
  id: string;
  kind: JobKind;
  playlist_slug: string;
  playlist_name: string;
  status: JobStatus;
  phase: string;
  current: number;
  total: number;
  message: string;
  result: Record<string, unknown> | null;
  error: string | null;
  tracks: TrackEvent[];
  /** Seconds remaining until a Soulseek search rate limit clears, computed
   * fresh by the backend on every poll — never a raw timestamp, so there's
   * no cross-machine clock comparison. Null when not currently rate-limited. */
  rate_limit_seconds: number | null;
}

export interface ScanResult {
  slug: string;
  playlist_name: string;
  found_count: number;
  missing_count: number;
  dry_run: boolean;
}

export interface DownloadResult {
  total_tracks: number;
  skipped?: boolean;
}

export interface FinalizeResult {
  playlist_id: string;
  display_name: string;
  created: boolean;
  track_count: number;
  coverage_pct: number;
  missing_ranks: number[];
  rescan: { newly_found: number; still_missing: number } | null;
}

export interface PlaylistSummary {
  slug: string;
  playlist_name: string;
  found_count: number;
  missing_count: number;
  /** Whether a matching playlist currently exists in Navidrome, checked live
   * against getPlaylists.view. Null if Navidrome couldn't be reached. */
  in_navidrome: boolean | null;
}

export interface FoundTrack {
  title: string;
  artist: string;
  uri?: string;
  nd_id: string;
  nd_title: string;
  nd_artist: string;
  rank?: number;
}

export interface MissingTrack {
  artist: string;
  title: string;
  album: string;
  rank?: string;
}

export interface PlaylistDetail {
  slug: string;
  playlist_name: string;
  found: FoundTrack[];
  missing: MissingTrack[];
}

export interface CleanupDiffRow {
  rank: string | null;
  orig_artist: string;
  artist: string;
  orig_title: string;
  title: string;
}

export interface CleanupPreview {
  total: number;
  changed: CleanupDiffRow[];
}

export interface Settings {
  navidrome: {
    url: string;
    user: string;
    password_set: boolean;
  };
  matching: {
    match_threshold: number;
    playlist_order: "asc" | "desc";
  };
  soulseek: {
    username: string;
    password_set: boolean;
  };
  download: {
    format: string;
    pref_format: string;
    pref_min_bitrate: string;
    desperate: boolean;
    skip_existing: boolean;
  };
  advanced: {
    concurrent_jobs: string;
    concurrent_searches: string;
    searches_per_time: string;
    searches_renew_time: string;
    search_timeout: string;
    max_stale_time: string;
    fast_search: boolean;
  };
  paths: {
    media_root: string;
  };
}

/** Partial update payload — password fields are omitted entirely unless the
 * user typed a new one, so saving never overwrites a stored secret with blank. */
export interface SettingsUpdate {
  navidrome?: Partial<{ url: string; user: string; password: string }>;
  matching?: Partial<{ match_threshold: number; playlist_order: "asc" | "desc" }>;
  soulseek?: Partial<{ username: string; password: string }>;
  download?: Partial<{
    format: string;
    pref_format: string;
    pref_min_bitrate: number;
    desperate: boolean;
    skip_existing: boolean;
  }>;
  advanced?: Partial<{
    concurrent_jobs: number;
    concurrent_searches: number;
    searches_per_time: number;
    searches_renew_time: number;
    search_timeout: number;
    max_stale_time: number;
    fast_search: boolean;
  }>;
  paths?: Partial<{ media_root: string }>;
}
