# Reaper — Automated Music Pipeline

Scans your Navidrome library, downloads missing tracks via Soulseek, imports them with beets, and creates or updates playlists — fully automated and playlist-agnostic.

---

## Directory layout

```
reaper/
├── config/
│   ├── sldl.conf                  ← Soulseek credentials & download settings
│   └── active_search.csv          ← staging file used during downloads (auto-managed)
├── playlists/
│   └── <playlist_slug>/
│       ├── found_tracks.json      ← tracks matched in Navidrome
│       ├── missing_tracks.csv     ← tracks to download
│       ├── download_log.txt       ← sldl output log
│       └── not_found.txt          ← tracks Soulseek couldn't source
├── docker-compose.yml
├── config.yml                     ← Navidrome credentials & pipeline settings
├── 01_scan_navidrome.py
├── 01b_cleanup_missing_csv.py     ← auto-run by Phase 2
├── 02_download_missing.sh
├── 02b_move_to_library.sh
├── 03_rescan_and_merge.py
└── 04_create_playlist.py
```

---

## Setup

### 1 — config.yml

Create `config.yml` in the project root:

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

Set your Soulseek credentials and tuning:

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

### 3 — Docker user permissions

The sldl container must write files as your user to avoid beets permission errors. Verify `docker-compose.yml` has:

```yaml
user: "1000:1000"
```

Check your UID/GID with `id -u && id -g`. If not 1000:1000, update accordingly.

### 4 — Beets config

Beets handles importing downloaded tracks into your library. Key settings in `~/.config/beets/config.yaml`:

```yaml
directory: /mnt/4TBExt/Media/Music
move: yes
overwrite: yes

replace:
    '[\u2010\u2011\u2012\u2013\u2014\u2212]': '-'
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

plugins: fetchart duplicates chroma

acoustid:
    apikey: your_acoustid_key

match:
    strong_rec_thresh: 0.80
    medium_rec_thresh: 0.30

fetchart:
    auto: yes

chroma:
    auto: yes
```

### 5 — Script permissions

```bash
chmod +x 02_download_missing.sh 02b_move_to_library.sh
```

---

## Pipeline

```
01_scan_navidrome.py
        │  Searches Navidrome for all playlist tracks
        │  → found_tracks.json
        │  → playlists/<slug>/missing_tracks.csv
        ▼
02_download_missing.sh
        │  Cleans CSV (01b), downloads via Soulseek (sldl Docker)
        │  → /mnt/4TBExt/Media/incoming/
        ▼
02b_move_to_library.sh
        │  Imports incoming files into Music library via beets
        │  Moves matched files, skips & cleans duplicates
        ▼
03_rescan_and_merge.py
        │  Triggers Navidrome rescan, waits for completion
        │  Re-searches for newly imported tracks
        │  → updates found_tracks.json and missing_tracks.csv
        ▼
04_create_playlist.py
           Creates or updates the playlist in Navidrome
```

---

## Running the pipeline

### Phase 1 — Scan your collection

```bash
python3 01_scan_navidrome.py --playlist "Hauraki Top 25"
```

Searches Navidrome for every track in your source CSV. Produces `found_tracks.json` and `missing_tracks.csv`.

```
Playlist : Hauraki Top 25
  [  25/  25] Crowded House              — Don't Dream It's Over

──────────────────────────────────────────────────────────────
  Found in collection :   18
  Missing             :    7
──────────────────────────────────────────────────────────────
```

### Phase 2 — Download missing tracks

```bash
./02_download_missing.sh --playlist "Hauraki Top 25"
```

Automatically runs Phase 1b cleanup on the CSV, then downloads missing tracks via Soulseek. Downloads land in `/mnt/4TBExt/Media/incoming/`.

> **Do not** log into Soulseek locally while this script is running. The container holds the session exclusively. Wait for the script to finish and the 30-second cooldown to complete before logging in.

### Phase 2b — Import into library

```bash
./02b_move_to_library.sh
```

Runs beets import on the incoming directory in singleton mode. Matched files are moved to your Music library, tagged against MusicBrainz, and cleaned up from incoming. Duplicates are skipped and removed automatically.

### Phase 3 — Rescan & merge

```bash
python3 03_rescan_and_merge.py --playlist "Hauraki Top 25"
```

Triggers a Navidrome library rescan and waits for it to complete, then re-searches for the newly imported tracks and merges them into `found_tracks.json`.

### Phase 4 — Create the playlist

```bash
python3 04_create_playlist.py --playlist "Hauraki Top 25"
```

Creates or updates the playlist in Navidrome. Re-running updates rather than duplicating.

To override the display name in Navidrome:

```bash
python3 04_create_playlist.py --playlist "Hauraki Top 25" --title "Hauraki Top 25 (2025)"
```

---

## Running in tmux (recommended)

For long-running phases, use tmux so the process survives disconnection:

```bash
tmux new-session -d -s reaper './02_download_missing.sh --playlist "Hauraki Top 25"' && tmux attach -t reaper
```

---

## Troubleshooting

**Soulseek finds nothing**
Make sure `desperate = true` is set in `sldl.conf`. Without it, sldl searches by combined artist+title string which often returns zero results, especially behind CGNAT.

**Search rate limit hit mid-run**
Reduce `searches-per-time` and `concurrent-searches` in `sldl.conf`. The pipeline will pause and resume automatically — this is normal behaviour.

**Files not moving from incoming after beets import**
Check file ownership — sldl must run as your user (`user: "1000:1000"` in docker-compose.yml). Files written as root cannot be moved by beets. Fix existing files with:
```bash
sudo chown -R chris:chris /mnt/4TBExt/Media/incoming/
```

**Beets skipping everything**
Clear the incremental state and retry:
```bash
rm -f ~/.config/beets/state.pickle
./02b_move_to_library.sh
```

**Tracks downloaded but not appearing in Navidrome after Phase 3**
Check that Navidrome's music folder path covers `/mnt/4TBExt/Media/Music`. Phase 3 triggers a rescan automatically — if tracks still don't appear, trigger a manual scan in Navidrome → Settings → Library → Scan now.

**Bad artist tags in source CSV**
Phase 1b cleans common issues automatically, but some require manual correction. Known examples:
- `AC DC Tribute Band` → `AC/DC`
- `BushidoSensei` → `Bush`

Edit the CSV directly before running Phase 2.

**Tracks not found on Soulseek**
Check `playlists/<slug>/not_found.txt` after a run. Options for manual sourcing:
- **yt-dlp**: `yt-dlp -x --audio-format flac "ytsearch1:Artist - Title"`
- **Bandcamp**: good for NZ/indie artists
- **CD ripping**: if you own the album