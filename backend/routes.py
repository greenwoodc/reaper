"""Flask routes wiring the Next.js wizard to core/ and the Phase 2 shell scripts.

Assumes the process cwd is the repo root (app.py chdir()s there at startup),
matching how every existing Reaper script already assumes it's run from the
repo root.
"""

import csv
import json
import os
import re
import subprocess
import time
from pathlib import Path

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from core.config import load_config, slugify
from core.scan import run_scan
from core.cleanup import clean_missing_csv
from core.rescan import run_rescan
from core.create_playlist import create_or_update_playlist
from core.settings import get_settings, update_settings, read_media_root

from backend.jobs import jobs

api_bp = Blueprint("api", __name__, url_prefix="/api")

PLAYLISTS_DIR = Path("playlists")
UPLOADS_DIR = Path("uploads")

EXPECTED_UID_GID = 1000

# sockseek's actual log format (confirmed against a live run):
#   [core] Downloaded 14, Failed 11 of Total 28 (89.29 %)
#   [003] SongJob: searching: Nickelback - Bones For The Crows
#   [005] SongJob: downloading: SCATTERBRAIN - FAST LANE: <path>
#   [006] SongJob: succeeded: Evanescence - Who Will You Follow: <path>
#   [005] SongJob: failed [All downloads failed]: SCATTERBRAIN - FAST LANE
_CORE_PROGRESS_RE = re.compile(
    r'^\[core\]\s*Downloaded\s+(?P<downloaded>\d+),\s*Failed\s+(?P<failed>\d+)\s*of\s*Total\s+(?P<total>\d+)',
    re.IGNORECASE,
)
_SONG_STATUS_RE = re.compile(
    r'^\[(?P<id>\d+)\]\s*SongJob:\s*(?P<action>searching|downloading|succeeded|failed)\b.*?:\s*(?P<track>[^:]+)',
    re.IGNORECASE,
)
#   Search rate limit reached, resuming in 100s
_RATE_LIMIT_RE = re.compile(
    r'^Search rate limit reached,\s*resuming in\s*(?P<seconds>\d+)s',
    re.IGNORECASE,
)




def _read_meta(playlist_dir: Path) -> dict:
    meta_file = playlist_dir / "meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _write_meta(playlist_dir: Path, playlist_name: str) -> None:
    meta_file = playlist_dir / "meta.json"
    meta_file.write_text(json.dumps({"playlist_name": playlist_name}, indent=2))


# ── Playlist listing / detail ────────────────────────────────────────────────

@api_bp.get("/playlists")
def list_playlists():
    out = []
    if PLAYLISTS_DIR.exists():
        for d in sorted(PLAYLISTS_DIR.iterdir()):
            if not d.is_dir():
                continue
            found_file = d / "found_tracks.json"
            missing_file = d / "missing_tracks.csv"

            found_count = 0
            if found_file.exists():
                found_count = len(json.loads(found_file.read_text()))

            missing_count = 0
            if missing_file.exists():
                with open(missing_file, newline='', encoding='utf-8') as f:
                    missing_count = sum(1 for _ in csv.DictReader(f))

            meta = _read_meta(d)
            out.append({
                "slug": d.name,
                "playlist_name": meta.get("playlist_name", d.name.replace("_", " ").title()),
                "found_count": found_count,
                "missing_count": missing_count,
            })
    return jsonify(out)


@api_bp.get("/playlists/<slug>/found")
def get_found(slug):
    playlist_dir = PLAYLISTS_DIR / slug
    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    if not found_file.exists():
        return jsonify({"error": "playlist not found — run a scan first"}), 404

    found = json.loads(found_file.read_text())
    missing = []
    if missing_file.exists():
        with open(missing_file, newline='', encoding='utf-8') as f:
            missing = list(csv.DictReader(f))

    meta = _read_meta(playlist_dir)
    return jsonify({
        "slug": slug,
        "playlist_name": meta.get("playlist_name", slug.replace("_", " ").title()),
        "found": found,
        "missing": missing,
    })


@api_bp.get("/playlists/<slug>/cleanup-preview")
def cleanup_preview(slug):
    csv_path = PLAYLISTS_DIR / slug / "missing_tracks.csv"
    if not csv_path.exists():
        return jsonify({"error": "missing_tracks.csv not found"}), 404

    diff = clean_missing_csv(csv_path, apply=False)
    changed = [
        {
            "rank": t.get("rank"),
            "orig_artist": t["_orig_artist"],
            "artist": t["artist"],
            "orig_title": t["_orig_title"],
            "title": t["title"],
        }
        for t in diff
        if t["_orig_artist"] != t["artist"] or t["_orig_title"] != t["title"]
    ]
    return jsonify({"total": len(diff), "changed": changed})


# ── Step 1: Upload & Scan ────────────────────────────────────────────────────

def _scan_job(job, csv_path: Path, playlist_name: str, config: dict, rank_col, dry_run: bool):
    def on_progress(current, total, track):
        job.phase = "scanning"
        job.current = current
        job.total = total
        job.message = f"{track['artist']} — {track['title']}"

    result = run_scan(
        csv_path, playlist_name, config,
        rank_col=rank_col, dry_run=dry_run, on_progress=on_progress, quiet=True,
    )
    job.playlist_slug = result.slug

    if not dry_run:
        _write_meta(result.playlist_dir, playlist_name)

    job.result = {
        "slug": result.slug,
        "playlist_name": playlist_name,
        "found_count": len(result.found),
        "missing_count": len(result.missing),
        "dry_run": dry_run,
    }


@api_bp.post("/playlists")
def upload_and_scan():
    file = request.files.get("csv")
    if not file or not file.filename:
        return jsonify({"error": "csv file is required"}), 400

    name = (request.form.get("name") or "").strip()
    rank_col = (request.form.get("rank_col") or "").strip() or None
    dry_run = (request.form.get("dry_run") or "false").lower() == "true"

    UPLOADS_DIR.mkdir(exist_ok=True)
    safe_name = secure_filename(file.filename) or "playlist.csv"
    csv_path = UPLOADS_DIR / safe_name
    file.save(csv_path)

    playlist_name = name or Path(safe_name).stem.replace("_", " ").replace("-", " ").strip()
    slug = slugify(playlist_name)

    config = load_config()
    job = jobs.create(kind="scan", playlist_slug=slug, playlist_name=playlist_name)
    jobs.run_in_background(job, _scan_job, csv_path, playlist_name, config, rank_col, dry_run)
    return jsonify(job.to_public_dict())


# ── Step 2: Download & Import ────────────────────────────────────────────────

def _check_uid_gid_mismatch():
    music_dir = Path(read_media_root()) / "Music"
    try:
        st = music_dir.stat()
    except FileNotFoundError:
        return False, None, None
    return (st.st_uid != EXPECTED_UID_GID or st.st_gid != EXPECTED_UID_GID), st.st_uid, st.st_gid


def _stream_subprocess(job, args, cwd, extra_env=None, total_tracks=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        args, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    for line in proc.stdout:
        line = line.rstrip("\n")
        job.append_log(line)

        core_m = _CORE_PROGRESS_RE.match(line)
        song_m = _SONG_STATUS_RE.match(line) if not core_m else None
        rate_limit_m = _RATE_LIMIT_RE.match(line) if not core_m and not song_m else None

        if core_m and total_tracks:
            # sockseek's own summary line — fires infrequently (not once per
            # track), so it's only used for the message text. current/total
            # below are derived from per-track state instead, which updates
            # on every SongJob line and stays in sync with the DownloadFeed.
            downloaded = int(core_m.group("downloaded"))
            failed = int(core_m.group("failed"))
            job.message = f"Downloaded {downloaded}, failed {failed} of {total_tracks}"
            job.rate_limit_until = None
        elif song_m:
            action = song_m.group("action").lower()
            track = song_m.group("track").strip()
            job.upsert_track(song_m.group("id"), track, action)
            job.message = f"{action.capitalize()}: {track}"
            job.rate_limit_until = None
        elif rate_limit_m:
            seconds = int(rate_limit_m.group("seconds"))
            job.rate_limit_until = time.time() + seconds
            job.message = f"Soulseek search rate limit hit — resuming in {seconds}s"
        elif line.strip():
            job.message = line[:200]

        if total_tracks:
            completed = sum(1 for t in job.tracks.values() if t["status"] in ("succeeded", "failed"))
            job.current = min(completed, total_tracks)
            job.total = total_tracks

    proc.wait()
    return proc.returncode


def _download_job(job, slug: str, playlist_name: str, assume_yes: bool):
    playlist_dir = PLAYLISTS_DIR / slug
    missing_file = playlist_dir / "missing_tracks.csv"

    job.phase = "cleaning"
    job.message = "Cleaning up search terms for Soulseek..."
    clean_missing_csv(missing_file, apply=True)

    with open(missing_file, newline='', encoding='utf-8') as f:
        total_tracks = sum(1 for _ in csv.DictReader(f))

    if total_tracks == 0:
        job.phase = "done"
        job.message = "No missing tracks — nothing to download."
        job.result = {"skipped": True, "total_tracks": 0}
        return

    mismatch, uid, gid = _check_uid_gid_mismatch()
    if mismatch and not assume_yes:
        job.status = "awaiting_confirmation"
        job.phase = "uid_gid_check"
        job.message = (
            f"Music folder owned by UID={uid} GID={gid} (expected "
            f"{EXPECTED_UID_GID}:{EXPECTED_UID_GID}). Downloaded files may be "
            "unreadable by beets. Continue anyway?"
        )
        return

    job.phase = "downloading"
    job.total = total_tracks
    job.current = 0
    job.message = "Starting Soulseek download session..."

    extra_env = {"REAPER_ASSUME_YES": "1"} if assume_yes else {}
    rc = _stream_subprocess(
        job, ["./02_download_missing.sh", "--playlist", playlist_name],
        cwd=".", extra_env=extra_env, total_tracks=total_tracks,
    )
    if rc != 0:
        raise RuntimeError(f"02_download_missing.sh exited with code {rc}")

    job.phase = "importing"
    job.current = 0
    job.total = 0
    job.message = "Importing downloaded files with beets..."

    rc = _stream_subprocess(job, ["./02b_move_to_library.sh"], cwd=".")
    if rc != 0:
        raise RuntimeError(f"02b_move_to_library.sh exited with code {rc}")

    job.phase = "done"
    job.message = "Download and import complete."
    job.result = {"total_tracks": total_tracks}


@api_bp.post("/playlists/<slug>/download")
def start_download(slug):
    playlist_dir = PLAYLISTS_DIR / slug
    if not (playlist_dir / "missing_tracks.csv").exists():
        return jsonify({"error": "missing_tracks.csv not found — run a scan first"}), 404

    meta = _read_meta(playlist_dir)
    playlist_name = meta.get("playlist_name", slug)

    job = jobs.create(kind="download", playlist_slug=slug, playlist_name=playlist_name)
    jobs.run_in_background(job, _download_job, slug, playlist_name, False)
    return jsonify(job.to_public_dict())


@api_bp.post("/jobs/<job_id>/confirm")
def confirm_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    if job.status != "awaiting_confirmation":
        return jsonify({"error": "job is not awaiting confirmation"}), 400

    body = request.get_json(silent=True) or {}
    if not body.get("confirm"):
        job.status = "error"
        job.error = "Cancelled by user."
        return jsonify(job.to_public_dict())

    new_job = jobs.create(kind=job.kind, playlist_slug=job.playlist_slug, playlist_name=job.playlist_name)
    jobs.run_in_background(new_job, _download_job, job.playlist_slug, job.playlist_name, True)
    return jsonify(new_job.to_public_dict())


# ── Step 3: Finalize (rescan + create/update playlist) ───────────────────────

def _finalize_job(job, slug: str, playlist_name: str, title):
    config = load_config()

    def on_progress(current, total, track):
        job.phase = "rescanning"
        job.current = current
        job.total = total
        job.message = f"{track['artist']} — {track['title']}"

    def on_scan_tick(status):
        job.phase = "waiting_for_navidrome_scan"
        job.message = f"Navidrome indexing... ({status.get('count', '?')} files so far)"

    job.phase = "rescanning"
    job.message = "Triggering Navidrome library rescan..."
    rescan_result = run_rescan(
        playlist_name, config, on_progress=on_progress, on_scan_tick=on_scan_tick, quiet=True,
    )

    job.phase = "creating_playlist"
    job.current = 0
    job.total = 0
    job.message = "Creating/updating Navidrome playlist..."

    def on_playlist_progress(added, total):
        job.current = added
        job.total = total

    playlist_result = create_or_update_playlist(
        playlist_name, config, title=title, quiet=True, on_progress=on_playlist_progress,
    )

    job.phase = "done"
    job.message = "Playlist ready in Navidrome."
    job.result = {
        "playlist_id": playlist_result.playlist_id,
        "display_name": playlist_result.display_name,
        "created": playlist_result.created,
        "track_count": playlist_result.track_count,
        "coverage_pct": playlist_result.coverage_pct,
        "missing_ranks": playlist_result.missing_ranks,
        "rescan": {
            "newly_found": len(rescan_result.newly_found),
            "still_missing": len(rescan_result.still_missing),
        } if rescan_result else None,
    }


@api_bp.post("/playlists/<slug>/finalize")
def start_finalize(slug):
    playlist_dir = PLAYLISTS_DIR / slug
    if not (playlist_dir / "found_tracks.json").exists():
        return jsonify({"error": "found_tracks.json not found — run a scan first"}), 404

    meta = _read_meta(playlist_dir)
    playlist_name = meta.get("playlist_name", slug)

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip() or None

    job = jobs.create(kind="finalize", playlist_slug=slug, playlist_name=playlist_name)
    jobs.run_in_background(job, _finalize_job, slug, playlist_name, title)
    return jsonify(job.to_public_dict())


# ── Job polling ───────────────────────────────────────────────────────────────

@api_bp.get("/jobs/<job_id>")
def get_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job.to_public_dict())


@api_bp.get("/jobs/<job_id>/log")
def get_job_log(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"log": job.log})


# ── Settings ──────────────────────────────────────────────────────────────────

@api_bp.get("/settings")
def get_settings_route():
    return jsonify(get_settings())


@api_bp.post("/settings")
def update_settings_route():
    payload = request.get_json(silent=True) or {}

    matching = payload.get("matching") or {}
    if "match_threshold" in matching:
        try:
            threshold = float(matching["match_threshold"])
        except (TypeError, ValueError):
            return jsonify({"error": "match_threshold must be a number"}), 400
        if not 0 <= threshold <= 1:
            return jsonify({"error": "match_threshold must be between 0 and 1"}), 400

    if matching.get("playlist_order") not in (None, "asc", "desc"):
        return jsonify({"error": "playlist_order must be 'asc' or 'desc'"}), 400

    download = payload.get("download") or {}
    if "pref_min_bitrate" in download:
        try:
            int(download["pref_min_bitrate"])
        except (TypeError, ValueError):
            return jsonify({"error": "pref_min_bitrate must be a whole number"}), 400

    try:
        update_settings(payload)
    except OSError as exc:
        return jsonify({"error": f"Failed to save settings: {exc}"}), 500

    return jsonify(get_settings())
