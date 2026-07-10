# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reaper takes an Exportify CSV (a Spotify playlist export), matches each track against a Navidrome library over the Subsonic API, downloads anything missing via Soulseek (through a Dockerized `sockseek`/`sldl` binary), imports downloads with `beets`, then creates/updates the playlist in Navidrome. It's a personal automation tool for a single user on a trusted (Tailscale/LAN) network — no auth, no test suite, no CI.

It used to be a set of standalone numbered CLI scripts (`01_scan_navidrome.py`, `02_download_missing.sh`, etc.). That CLI layer has been retired — the webapp (`frontend/` + `backend/`) is now the only way this pipeline is run. The shared matching/scan/rescan/playlist logic that used to live in those scripts now lives in `core/`, imported directly (in-process) by the Flask backend.

## Running it

```bash
# Backend (Flask API)
python3 backend/app.py          # binds 0.0.0.0:5001 — see backend/app.py for the AirPlay/port-5000 gotcha on macOS

# Frontend (Next.js)
cd frontend && npm run dev      # needs NEXT_PUBLIC_API_URL if the backend isn't on localhost:5001
cd frontend && npm run build
cd frontend && npm run lint
```

There is no test suite — verify backend changes by running the Flask app and exercising the relevant endpoint (curl or the UI); verify frontend changes with `npm run lint && npm run build` plus a manual click-through.

## Architecture

**Three layers:**
- **`core/`** — the actual pipeline logic (config loading, Subsonic API client, fuzzy matching, scan/rescan/cleanup/create-playlist). No printing, no CLI concerns — every function takes an optional `on_progress` callback and returns a structured result object. This is the only place matching/scan/rescan logic lives.
- **`backend/`** — Flask API (`app.py`, `routes.py`, `jobs.py`) that drives `core/` directly for scan, cleanup-preview, rescan, and playlist creation (in-process function calls, not subprocess). Background work runs on a `threading.Thread` per job via `backend/jobs.py`'s in-memory `JobManager` — job state is lost if the process restarts, and there's no lock preventing two download jobs from running concurrently (Soulseek only supports one session at a time — don't start two downloads at once).
- **`frontend/`** — Next.js (App Router, TypeScript, Tailwind) wizard UI. Polls `/api/jobs/<id>` every second for progress rather than using websockets/SSE.

**`download_missing.sh` and `move_to_library.sh` are the one place bash still does real work** — Docker/Soulseek orchestration and the `beet import` call. The backend invokes them via `subprocess.Popen`, tailing stdout for progress (see the log-parsing regexes in `backend/routes.py` — they're matched against `sockseek`'s actual log format, not guessed). Two things that bit us building this, both now fixed but worth knowing if they resurface:
  - `docker compose run ... | tee` block-buffers when piped to a non-tty — needs `stdbuf -oL` on `tee` or output silently sits in a buffer for minutes.
  - `sockseek` exits non-zero whenever *any* individual track fails (completely normal for Soulseek P2P) — under `set -e` that aborts the whole script before cleanup/cooldown run. `download_missing.sh` captures the real exit code via `${PIPESTATUS[0]}` inside a `set +e`/`set -e` bracket instead of letting it propagate.

**Per-playlist state lives in `playlists/<slug>/`** (slug = lowercased, non-alphanumerics → `_`, gitignored):
- `found_tracks.json` — tracks matched in Navidrome, each carrying the Navidrome song id (`nd_id`) plus original CSV metadata and optional `rank`
- `missing_tracks.csv` — tracks still to source, columns `artist,title,album[,rank]`
- `meta.json` — `{"playlist_name": "..."}`, written by the backend on scan so the dashboard can resume a playlist and show its real display name (the CSV filename/slug alone can't recover this)
- `download_log.txt`, `not_found.txt` — produced by `download_missing.sh`

**Matching** (`core/matching.py`): `normalise()`, `fuzzy()`, `score_song()`, `search_navidrome()` — single source of truth, used by both scan and rescan. Scoring formula is `title_score * 0.60 + artist_score * 0.40` with hardcoded boosts (a `shihad`/`pacifier` band-alias special case, a "various artists" title-embeds-artist case). This used to be duplicated between two scripts and had already silently drifted (different tie-breaking behavior) before being consolidated — if you touch this file, that's the whole reason it's one file now.

**Config precedence**: `core/config.py`'s `load_config()` reads `config.yml` (gitignored, real credentials) merged over a `DEFAULTS` dict. Auth against Navidrome is Subsonic-style: `md5(password + salt)` with a hardcoded salt (`"reaper"`). The webapp's Settings page (`core/settings.py`) reads/writes `config.yml` and `config/sldl.conf` directly — it only touches the specific keys it manages and preserves everything else (comments in `sldl.conf`, unmanaged keys) untouched on save, except `config.yml` itself loses its comments on save (plain `yaml.safe_dump`, not comment-preserving).

**Media root**: `download_missing.sh`/`move_to_library.sh` derive `MUSIC_DIR`/`INCOMING_DIR` from `REAPER_MEDIA_ROOT` in a gitignored `.env` file (default `/mnt/4TBExt/Media` if unset), which also feeds `docker-compose.yml`'s volume mount (`${REAPER_MEDIA_ROOT:-/mnt/4TBExt/Media}:/data`). Settable via the webapp's Settings page or by hand-editing `.env`.

**`sockseek` naming churn**: the upstream project has been renamed twice (`slsk-batchdl` → `sldl` → `sockseek`). The `Dockerfile` clones a pinned release tag rather than `master` specifically to survive this — when upgrading, update the `--branch` tag and the `.csproj` path together.

**Rank/order handling**: `rank` is optional throughout (absent when no rank column is picked during upload). Playlist ordering (`playlist_order: asc|desc` in `config.yml`, editable via Settings) and the coverage report only make sense when ranks are dense 1..N integers (e.g. a countdown-style playlist) — sparse or absent ranks make the "missing ranks" report meaningless.

**Navidrome playlists are marked public automatically** (`core/create_playlist.py`'s `set_playlist_public`) — Navidrome defaults new playlists to private, which used to require a manual per-playlist toggle.

## Secrets

`config.yml`, `config/sldl.conf`, `.env`, and `github_token.txt` hold live credentials and are gitignored — never commit them. `config/sldl.conf.example` is the checked-in placeholder template.

## Git workflow

This repo hit the classic squash-merge trap repeatedly (squash-merging a PR breaks the branch's ancestry link to `main`, so continuing to commit on that same branch and merging again produces phantom conflicts on files that didn't actually change). Fixed at the repo level: squash merging is disabled and branches auto-delete on merge — always branch fresh off `origin/main` for new work rather than reusing an already-merged branch.
