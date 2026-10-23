import type {
  CleanupPreview,
  Job,
  PlaylistDetail,
  PlaylistSummary,
  Settings,
  SettingsUpdate,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

// Every endpoint either answers quickly or hands back a job id to poll, so
// anything slower than this means the backend is wedged or unreachable.
const REQUEST_TIMEOUT_MS = 30_000;

/** An error from the backend, carrying its HTTP status and optional `code`
 * (e.g. "playlist_exists") so callers can offer a specific recovery. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "TimeoutError";
    throw new ApiError(
      timedOut
        ? `The Reaper backend at ${API_BASE} didn't respond in time.`
        : `Can't reach the Reaper backend at ${API_BASE}. Is it running?`,
      0,
    );
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const body = (data ?? {}) as { error?: string; code?: string };
    throw new ApiError(body.error || `Request failed (${res.status})`, res.status, body.code);
  }
  return data as T;
}

const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export function listPlaylists(): Promise<PlaylistSummary[]> {
  return request("/api/playlists");
}

export async function deletePlaylist(slug: string): Promise<void> {
  await request(`/api/playlists/${slug}`, { method: "DELETE" });
}

export function uploadAndScan(opts: {
  file: File;
  name?: string;
  rankCol?: string;
  /** Overwrite an existing playlist with the same name. */
  replace?: boolean;
}): Promise<Job> {
  const form = new FormData();
  form.append("csv", opts.file);
  if (opts.name) form.append("name", opts.name);
  if (opts.rankCol) form.append("rank_col", opts.rankCol);
  if (opts.replace) form.append("replace", "1");
  return request("/api/playlists", { method: "POST", body: form });
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/api/jobs/${jobId}`);
}

export function getJobLog(jobId: string): Promise<{ log: string[] }> {
  return request(`/api/jobs/${jobId}/log`);
}

export function confirmJob(jobId: string, confirm: boolean): Promise<Job> {
  return request(`/api/jobs/${jobId}/confirm`, postJson({ confirm }));
}

export function cancelJob(jobId: string): Promise<Job> {
  return request(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}

export function getFound(slug: string): Promise<PlaylistDetail> {
  return request(`/api/playlists/${slug}/found`);
}

export function getCleanupPreview(slug: string): Promise<CleanupPreview> {
  return request(`/api/playlists/${slug}/cleanup-preview`);
}

export function startDownload(slug: string): Promise<Job> {
  return request(`/api/playlists/${slug}/download`, { method: "POST" });
}

export function startFinalize(slug: string, title?: string): Promise<Job> {
  return request(`/api/playlists/${slug}/finalize`, postJson({ title: title || undefined }));
}

export function getSettings(): Promise<Settings> {
  return request("/api/settings");
}

export function updateSettings(update: SettingsUpdate): Promise<Settings> {
  return request("/api/settings", postJson(update));
}
