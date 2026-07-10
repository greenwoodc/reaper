# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reaper is a 4-phase pipeline that takes an Exportify CSV (a Spotify playlist export), matches each track against a Navidrome library over the Subsonic API, downloads anything missing via Soulseek (through a Dockerized `sockseek`/`sldl` binary), imports downloads with `beets`, then creates/updates the playlist in Navidrome. It's a personal automation tool, not a service — there's no test suite, no CI, and no package manifest (stdlib + PyYAML only).

A Next.js frontend is planned as a new addition on top of this pipeline — see "Frontend (planned)" below.

## Commands

```bash
python3 01_scan_navidrome.py --csv path/to/export.csv [--name "Name"] [--rank-col Rank] [--dry-run]
python3 01b_cleanup_missing_csv.py --playlist "Name"      # or --csv path/to/missing_tracks.csv
./02_download_missing.sh --playlist "Name"                # runs 01b automatically, then Docker sockseek
./02b_move_to_library.sh                                  # beets import of /mnt/4TBExt/Media/incoming
python3 03_rescan_and_merge.py --playlist "Name"
python3 04_create_playlist.py --playlist "Name" [--title "Display Name"]
```

There is no lint/test/build step — verify changes by running the relevant phase against a real (or `--dry-run`) config.

## Architecture

**Per-playlist state lives in `playlists/<slug>/`** (slug = lowercased, non-alphanumerics → `_`), not in the repo root. Each phase reads/writes this directory:
- `found_tracks.json` — tracks matched in Navidrome, each carrying the Navidrome song id (`nd_id`) plus original CSV metadata and optional `rank`
- `missing_tracks.csv` — tracks still to source, columns `artist,title,album[,rank]`
- `download_log.txt`, `not_found.txt` — produced during Phase 2

**Matching logic is duplicated, not shared**, between `01_scan_navidrome.py` and `03_rescan_and_merge.py`: `normalise()`, `fuzzy()`, and `score_song()` are copy-pasted identically in both files (Phase 3's docstring says it must match Phase 1 "precisely"). If you change matching behavior, update both files or they will silently diverge. The scoring formula is `title_score * 0.60 + artist_score * 0.40` with several hardcoded boosts (e.g. a `shihad`/`pacifier` band-alias special case, a "various artists" title-embeds-artist case).

**Config precedence**: all phases call a local `load_config()` that reads `config.yml` (gitignored, real credentials live there) merged over an in-file `DEFAULTS` dict — never assume a key is present without checking the `DEFAULTS` block at the top of the script. Auth against Navidrome is Subsonic-style: `md5(password + salt)` with a hardcoded salt (`"reaper"`).

**Phase 1b (`01b_cleanup_missing_csv.py`) rewrites `missing_tracks.csv` in place**, replacing artist/title with Soulseek-friendly versions (strips `feat.`/`&`/backing-band noise, parenthetical remaster/live/year metadata, diacritics, punctuation that breaks P2P search). Original values are only kept transiently for the diff preview printed to stdout — not persisted. Phase 2 always runs this before downloading; running it standalone lets you preview the diff first.

**Phase 2 (`02_download_missing.sh`) is a bash orchestrator**, not a thin wrapper: it builds the Docker image, validates `config/sldl.conf` is filled in, runs Phase 1b, stages the CSV into `config/active_search.csv` (the only path the Docker volume mount exposes to the container), runs `sockseek` via `docker compose run`, then tears the container down with an explicit 30s cooldown before it's safe to log into Soulseek locally again (the container holds an exclusive session). Hardcoded paths (`/mnt/4TBExt/Media/...`) assume the current host layout.

**`sockseek` naming churn**: the upstream project has been renamed twice (`slsk-batchdl` → `sldl` → `sockseek`). The `Dockerfile` clones a pinned release tag rather than `master` specifically to survive this — when upgrading, update the `--branch` tag and the `.csproj` path together.

**Rank/order handling**: `rank` is optional throughout (absent when `--rank-col` isn't passed to Phase 1). Phase 4's playlist ordering (`playlist_order: asc|desc` in `config.yml`) and its coverage report only make sense when ranks are dense 1..N integers (e.g. a countdown-style playlist) — sparse or absent ranks make the "missing ranks" report meaningless.

## Secrets

`config.yml`, `config/sldl.conf`, and `github_token.txt` hold live credentials and are gitignored — never commit them, and be careful not to echo their contents into logs or commit messages. `config/sldl.conf.example` is the checked-in placeholder template — copy it to `config/sldl.conf` and fill in real values for first-time setup.

## Frontend

`frontend/` is a Next.js app (App Router, TypeScript, Tailwind) scaffolded via `create-next-app`, meant to sit in front of this pipeline (e.g. triggering phases, viewing playlist/match status). It currently has no connection to the Python pipeline — that integration (direct subprocess invocation vs. a thin API layer) is still to be designed.

```bash
cd frontend && npm run dev      # http://localhost:3000 (or next available port)
cd frontend && npm run build
cd frontend && npm run lint
```
