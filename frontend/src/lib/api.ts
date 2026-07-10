import type {
  CleanupPreview,
  Job,
  PlaylistDetail,
  PlaylistSummary,
  Settings,
  SettingsUpdate,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

async function handle<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (data && (data as { error?: string }).error) || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data as T;
}

export async function listPlaylists(): Promise<PlaylistSummary[]> {
  const res = await fetch(`${API_BASE}/api/playlists`, { cache: "no-store" });
  return handle(res);
}

export async function deletePlaylist(slug: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/playlists/${slug}`, { method: "DELETE" });
  await handle(res);
}

export async function uploadAndScan(opts: {
  file: File;
  name?: string;
  rankCol?: string;
}): Promise<Job> {
  const form = new FormData();
  form.append("csv", opts.file);
  if (opts.name) form.append("name", opts.name);
  if (opts.rankCol) form.append("rank_col", opts.rankCol);

  const res = await fetch(`${API_BASE}/api/playlists`, {
    method: "POST",
    body: form,
  });
  return handle(res);
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  return handle(res);
}

export async function getJobLog(jobId: string): Promise<{ log: string[] }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/log`, { cache: "no-store" });
  return handle(res);
}

export async function confirmJob(jobId: string, confirm: boolean): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
  });
  return handle(res);
}

export async function getFound(slug: string): Promise<PlaylistDetail> {
  const res = await fetch(`${API_BASE}/api/playlists/${slug}/found`, { cache: "no-store" });
  return handle(res);
}

export async function getCleanupPreview(slug: string): Promise<CleanupPreview> {
  const res = await fetch(`${API_BASE}/api/playlists/${slug}/cleanup-preview`, { cache: "no-store" });
  return handle(res);
}

export async function startDownload(slug: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/playlists/${slug}/download`, { method: "POST" });
  return handle(res);
}

export async function startFinalize(slug: string, title?: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/playlists/${slug}/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title || undefined }),
  });
  return handle(res);
}

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, { cache: "no-store" });
  return handle(res);
}

export async function updateSettings(update: SettingsUpdate): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  return handle(res);
}
