# Reaper — Automated Music Pipeline

Scans your Navidrome library, downloads missing tracks via Soulseek, imports them with beets, and creates or updates playlists — fully automated and playlist-agnostic. Driven by a Next.js + Flask webapp; no CLI required.

---

## Directory layout

```
reaper/
├── core/                           ← shared pipeline logic (config, matching, scan, rescan, cleanup, playlist creation)
├── backend/                        ← Flask API, drives core/ + the two shell scripts below
├── frontend/                       ← Next.js wizard UI
├── config/
│   ├── sldl.conf                  ← Soulseek credentials & download settings
│   └── active_search.csv          ← staging file used during downloads (auto-managed)
├── playlists/
│   └── <playlist_slug>/
│       ├── found_tracks.json      ← tracks matched in Navidrome
│       ├── missing_tracks.csv     ← tracks to download
│       ├── meta.json              ← display name, for resuming from the dashboard
│       ├── download_log.txt       ← sockseek output log
│       └── not_found.txt          ← tracks Soulseek couldn't source
├── Dockerfile                     ← builds sockseek image (pinned to release tag)
├── docker-compose.yml
├── config.yml                     ← Navidrome credentials & pipeline settings
├── .env                           ← REAPER_MEDIA_ROOT (host path Docker mounts as /data)
├── download_missing.sh            ← Soulseek download via sockseek (Docker)
└── move_to_library.sh             ← beets import into the Music library
```

---

## Setup

### 1 — config.yml

Create `config.yml` in the project root (or fill these in from the webapp's Settings page after first run):

```yaml
navidrome_url: "http://localhost:4533/"
navidrome_user: "admin"
navidrome_password: "yourpassword"
navidrome_client: "reaper"
navidrome_version: "1.16.1"
match_threshold: 0.80
playlist_order: "asc"   # "asc" = #1 first, "desc" = countdown (#N → #1)
```

### 2 — config/sldl.conf

Copy `config/sldl.conf.example` to `config/sldl.conf` and set your Soulseek credentials and tuning:

```properties
username = your_username
password = your_password
path = /data/incoming
format = mp3,flac,ogg
pref-format = flac
pref-min-bitrate = 128
name-format = {artist}/{album}/{artist} - {title}
concurrent-jobs = 3
concurrent-searches = 3
skip-existing = true
search-timeout = 30000
max-stale-time = 30000
fast-search = false
searches-per-time = 4
searches-renew-time = 120
desperate = true
```

> **Note:** `desperate = true` is required for reliable results, especially behind CGNAT. It searches by title only and filters by artist on results, which significantly improves hit rate.

Most of these are also editable from the webapp's Settings page, which reads/writes this file directly.

### 3 — Docker image

The pipeline builds its own sockseek image from the `Dockerfile` in the project root. The image is built automatically the first time a download runs, and rebuilt only when the `Dockerfile` changes.

The `Dockerfile` clones sockseek pinned to a specific release tag. When upgrading sockseek, update the tag in the `Dockerfile` and run:

```bash
docker compose build
```

> **Background:** sockseek was formerly known as `sldl` and before that `slsk-batchdl`. The project has been renamed and restructured twice. Pinning to a release tag prevents upstream restructures from silently breaking the build between runs.

### 4 — Docker user permissions

The sockseek container must write files as your user to avoid beets permission errors. Verify `docker-compose.yml` has:

```yaml
user: "1000:1000"
```

Check your UID/GID with `id -u && id -g`. If not 1000:1000, update accordingly. The webapp warns and asks for confirmation before downloading if it detects a mismatch on the media root.

### 5 — Media root

Set `REAPER_MEDIA_ROOT` in a `.env` file in the project root (defaults to `/mnt/4TBExt/Media` if unset). This is the host directory Docker mounts as `/data`, containing `Music/` (the library) and `incoming/` (fresh downloads awaiting beets import). Also settable from the webapp's Settings page.

### 6 — Beets config

Beets handles importing downloaded tracks into your library. Key settings in `~/.config/beets/config.yaml`:

```yaml
directory: /mnt/4TBExt/Media/Music
move: yes
overwrite: yes

replace:
    '[‐‑‒–—−]': '-'
    (\s*\.\s*)+$: ''

paths:
    singleton: Non-Album/$albumartist/$album/$title
    default: $albumartist/$album/$title
    comp: Compilations/$album/$title

import:
    write: yes
    move: yes
    log: ~/beets-import.log
    duplicate_action: skip
    timid: no
    quiet: yes
    autotag: yes
    resume: no
    incremental: yes
    clean: yes

plugins: fetchart duplicates
#plugins: fetchart duplicates chroma
#chroma disabled to improve matching during import

#acoustid:
#    apikey: your_acoustid_key
#not needed when not using chroma

match:
    strong_rec_thresh: 0.80
    medium_rec_thresh: 0.30

fetchart:
    auto: yes

chroma:
    auto: yes
```

### 7 — Script permissions

```bash
chmod +x download_missing.sh move_to_library.sh
```

### 8 — Run it

```bash
python3 backend/app.py          # Flask API on :5001
cd frontend && npm run dev      # wizard UI on :3000
```

### 9 — Persistent deployment on the server (optional)

To run the frontend as a systemd service on the homelab box instead of a
manual `npm run dev` in a terminal, use the scripts in `deploy/`:

```bash
bash deploy/setup_frontend.sh              # installs Node 20 via nvm (Next.js 16 needs >=20.9.0), builds
./deploy/install_frontend_service.sh       # installs + starts the reaper-frontend systemd service (needs sudo)
```

The service listens on port **3002**, not 3000 — the server already has other
Docker containers bound to 3000 and 3001. `NEXT_PUBLIC_API_URL` is baked into
the build at compile time (`frontend/.env.production`, gitignored), so
`setup_frontend.sh` must be re-run (not just the systemd service restarted)
whenever the backend's address changes.

---

## The wizard

The frontend walks through three steps per playlist:

```
1. Upload & Scan
        │  Upload an Exportify CSV, optionally pick a rank column
        │  Searches Navidrome for every track (core/scan.py)
        │  → found_tracks.json, playlists/<slug>/missing_tracks.csv
        ▼
2. Download & Import
        │  Cleans up artist/title strings for Soulseek search hits (core/cleanup.py)
        │  Downloads missing tracks via Soulseek (download_missing.sh → sockseek/Docker)
        │  Imports into the Music library via beets (move_to_library.sh)
        ▼
3. Finalize
        │  Triggers a Navidrome rescan, waits for completion
        │  Re-searches for newly imported tracks (core/rescan.py)
        │  Creates or updates the playlist in Navidrome (core/create_playlist.py)
```

Each step streams live progress (per-track status, download log tail, rate-limit countdowns) to the UI. The dashboard also lists existing `playlists/<slug>/` directories so you can resume a playlist partway through, or delete one that hasn't been imported to Navidrome yet.

**Do not** log into Soulseek locally while a download is running. The Docker container holds the session exclusively; it releases it with a 30-second cooldown after the download step finishes.

---

## Running scripts directly

`download_missing.sh` and `move_to_library.sh` are also runnable standalone (useful in tmux for a long unattended run), independent of the webapp:

```bash
./download_missing.sh --playlist "Hauraki Top 25"
./move_to_library.sh
```

`download_missing.sh` runs its own search-term cleanup pass and `docker compose build` at the start of every run (fast when nothing's changed, thanks to Docker layer cache). Everything else in the pipeline (scanning, rescanning, playlist creation) lives in `core/` and currently has no standalone entry point outside the webapp — trigger those steps from the UI.

```bash
tmux new-session -d -s reaper './download_missing.sh --playlist "Hauraki Top 25"' && tmux attach -t reaper
```

---

## Upgrading sockseek

The `Dockerfile` pins sockseek to a specific release tag. To upgrade:

1. Check the [sockseek releases page](https://github.com/fiso64/sockseek/releases) for the latest tag.
2. Update the `--branch` value in the `Dockerfile`.
3. Rebuild the image:

```bash
cd /opt/reaper
docker compose build --no-cache
```

> **Note:** sockseek was previously named `sldl` and `slsk-batchdl`. GitHub redirects the old URLs to the current repo, but the project structure changed with each rename. Always pin to a release tag rather than `master` to avoid silent breakage between runs.

---

## Troubleshooting

**Soulseek finds nothing**
Make sure `desperate = true` is set in `sldl.conf`. Without it, sockseek searches by combined artist+title string which often returns zero results, especially behind CGNAT.

**Search rate limit hit mid-run**
Reduce `searches-per-time` and `concurrent-searches` in `sldl.conf`. The pipeline will pause and resume automatically — the webapp shows a live countdown — this is normal behaviour.

**Files not moving from incoming after beets import**
Check file ownership — sockseek must run as your user (`user: "1000:1000"` in docker-compose.yml). Files written as root cannot be moved by beets. Fix existing files with:
```bash
sudo chown -R chris:chris /mnt/4TBExt/Media/incoming/
```

**Beets skipping everything**
Clear the incremental state and retry:
```bash
rm -f ~/.config/beets/state.pickle
./move_to_library.sh
```

**Tracks downloaded but not appearing in Navidrome after Finalize**
Check that Navidrome's music folder path covers `/mnt/4TBExt/Media/Music`. The Finalize step triggers a rescan automatically — if tracks still don't appear, trigger a manual scan in Navidrome → Settings → Library → Scan now.

**Bad artist tags in source CSV**
The cleanup pass automatically handles most common issues: featured artist suffixes, `& The ...` backing band noise, collab separators (`;`, `,`, `feat.`, `with`), and unicode/punctuation hazards. For values that survive cleaning unchanged — typically where the source CSV itself has a genuinely wrong artist name — manual correction is still needed before downloading. Edit `missing_tracks.csv` directly, or fix the source CSV and re-scan.

**Tracks not found on Soulseek**
Check `playlists/<slug>/not_found.txt` after a run. Options for manual sourcing:
- **yt-dlp**: `yt-dlp -x --audio-format flac "ytsearch1:Artist - Title"`
- **Bandcamp**: good for NZ/indie artists
- **CD ripping**: if you own the album

**Docker build fails with `Project file does not exist`**
sockseek has been renamed and restructured twice (formerly `slsk-batchdl` → `sldl` → `sockseek`). If the build breaks after a period of inactivity, check the [sockseek releases page](https://github.com/fiso64/sockseek/releases) and update the `--branch` tag and `.csproj` path in the `Dockerfile` to match the current repo structure, then rebuild with `docker compose build --no-cache`.
