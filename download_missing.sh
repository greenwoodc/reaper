#!/usr/bin/env bash
# Reaper — download missing tracks via sockseek (Docker). Invoked by the
# webapp backend (backend/routes.py); also runnable directly.
#
# Usage:
#   ./download_missing.sh --playlist "Hauraki Top 25"
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Media root (host path Docker mounts as /data — set via the webapp's
# Settings page, or REAPER_MEDIA_ROOT in .env) ───────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi
MEDIA_ROOT="${REAPER_MEDIA_ROOT:-/mnt/media}"
MUSIC_DIR="$MEDIA_ROOT/Music"
# Staging area for fresh downloads awaiting beets import. Usually a subfolder
# of the media root, but overridable (e.g. to a different disk) via
# REAPER_INCOMING_DIR in .env or the webapp's Settings page. Exported so
# docker-compose.yml's volume mount can reference it directly.
INCOMING_DIR="${REAPER_INCOMING_DIR:-$MEDIA_ROOT/incoming}"
export INCOMING_DIR

# ── STEP 0: Parse Arguments ──────────────────────────────────────────────────
PLAYLIST=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --playlist)
            PLAYLIST="$2"
            shift 2
            ;;
        *)
            echo "❌ Unknown argument: $1"
            echo "Usage: $0 --playlist \"Playlist Name\""
            exit 1
            ;;
    esac
done

if [ -z "$PLAYLIST" ]; then
    echo "❌ Error: Missing required argument --playlist"
    echo "Usage: $0 --playlist \"Playlist Name\""
    exit 1
fi

# Helper function to generate filesystem-safe slug names matching Python's logic
slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9_-]+/_/g' | sed -E 's/^_+|_+$//g'
}

SLUG=$(slugify "$PLAYLIST")
PLAYLIST_DIR="$SCRIPT_DIR/playlists/$SLUG"
CSV_PATH="$PLAYLIST_DIR/missing_tracks.csv"

# ── STEP 1: Build image via docker compose (idempotent, cache-aware) ─────────
echo "► Ensuring slsk-batchdl image is current..."
cd "$SCRIPT_DIR"
docker compose build --quiet
echo "✓ Image ready."

# ── STEP 2: Check prerequisites ──────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  python3 not found in PATH. Required for search-term cleanup."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/config/sldl.conf" ]; then
    echo "❌  config/sldl.conf not found."
    exit 1
fi

if grep -q "your_soulseek_username" "$SCRIPT_DIR/config/sldl.conf"; then
    echo "❌  Edit config/sldl.conf and set your Soulseek username/password first."
    exit 1
fi

# ── STEP 3: Clean up search terms for Soulseek ───────────────────────────────
# The webapp already runs this in-process (core.cleanup) before invoking this
# script; re-running it here is a harmless no-op for that path and is what
# makes this script self-sufficient when run directly from a terminal.
if [ ! -f "$CSV_PATH" ]; then
    echo "❌  Target CSV not found at: $CSV_PATH"
    exit 1
fi

echo ""
echo "► Cleaning up search terms for Soulseek..."
python3 -c "
from core.cleanup import clean_missing_csv
clean_missing_csv('$CSV_PATH', apply=True)
"

TRACK_COUNT=$(tail -n +2 "$CSV_PATH" | wc -l)
if [ "$TRACK_COUNT" -eq 0 ]; then
    echo "🎉 Zero missing tracks found! Your library is fully up to date for this playlist."
    exit 0
fi

# COPY FILE INTO THE CONTAINER'S ACCESSIBLE SCOPE
# Stage it inside the config folder so the volume map picks it up perfectly
CONTAINER_CSV_STAGING="$SCRIPT_DIR/config/active_search.csv"
cp "$CSV_PATH" "$CONTAINER_CSV_STAGING"

echo ""
echo "► Starting download session for playlist: $PLAYLIST"
echo "  Target Slug   : $SLUG"
echo "  Missing Tracks: $TRACK_COUNT"
echo "  Music library : $MUSIC_DIR"
echo "  Download subdir: $INCOMING_DIR"
echo ""

# ── STEP 4: Get PUID/PGID from the music folder owner ────────────────────────
MUSIC_UID=$(stat -c '%u' "$MUSIC_DIR")
MUSIC_GID=$(stat -c '%g' "$MUSIC_DIR")

if [ "$MUSIC_UID" != "1000" ] || [ "$MUSIC_GID" != "1000" ]; then
    echo ""
    echo "⚠️  WARNING: Music folder owned by UID=$MUSIC_UID GID=$MUSIC_GID (expected 1000:1000)."
    echo "   Downloaded files may be unreadable by beets in Phase 2b."
    echo "   Update 'user:' in docker-compose.yml to match, or fix with:"
    echo "     sudo chown -R \$(id -u):\$(id -g) $INCOMING_DIR/"
    echo ""
    if [ "${REAPER_ASSUME_YES:-0}" = "1" ]; then
        echo "   REAPER_ASSUME_YES=1 set — continuing without prompting (webapp confirmed already)."
    else
        read -r -p "   Continue anyway? [y/N] " _confirm
        if [[ ! "$_confirm" =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 1
        fi
    fi
fi

# ── STEP 5: Run sockseek inside the container ─────────────────────────────────
echo ""
echo "► Running sockseek (output will stream below)..."
echo "  Press Ctrl+C to pause — re-running this script will resume safely."
echo "──────────────────────────────────────────────────────────────"

cd "$SCRIPT_DIR"

# sockseek exits non-zero whenever *any* track fails (rejected transfer,
# offline peer, no results, etc.) — completely normal for Soulseek P2P, not a
# reason to abort the whole script before cleanup/cooldown run. Capture the
# real exit code via PIPESTATUS instead of letting `set -e` kill us here.
set +e
# Verified argument: --max-retries limits endless loop behaviors on locked users
docker compose run --rm --no-deps sldl \
    -c /config/sldl.conf \
    "/config/active_search.csv" \
    --artist-col "artist" \
    --title-col  "title" \
    --max-retries 1 \
    2>&1 | stdbuf -oL tee "$PLAYLIST_DIR/download_log.txt"
SLDL_EXIT_CODE=${PIPESTATUS[0]}
set -e

echo ""
echo "──────────────────────────────────────────────────────────────"
if [ "$SLDL_EXIT_CODE" -ne 0 ]; then
    echo "ℹ️  sockseek finished with some tracks unresolved (exit code $SLDL_EXIT_CODE)."
    echo "   That's normal for Soulseek — see playlists/$SLUG/download_log.txt for"
    echo "   details. Re-running this playlist later will retry what's still missing."
else
    echo "✓ Download session complete."
fi
echo "  Playlist Folder Log: playlists/$SLUG/download_log.txt"

# Clean up our temporary container-facing CSV staging file
if [ -f "$CONTAINER_CSV_STAGING" ]; then
    rm "$CONTAINER_CSV_STAGING"
fi

# If sockseek drops a not_found list into config/, move it to the playlist directory
if [ -f "$SCRIPT_DIR/config/not_found.txt" ]; then
    mv "$SCRIPT_DIR/config/not_found.txt" "$PLAYLIST_DIR/not_found.txt"
fi

if [ -f "$PLAYLIST_DIR/not_found.txt" ] && [ -s "$PLAYLIST_DIR/not_found.txt" ]; then
    NOT_FOUND=$(wc -l < "$PLAYLIST_DIR/not_found.txt")
    echo "  ⚠  $NOT_FOUND track(s) not found on Soulseek — see playlists/$SLUG/not_found.txt"
fi

# ── STEP 6: Container Safety Exit Cleanup ────────────────────────────────────
echo ""
echo "► Cleaning up Docker container..."
docker compose down

if docker container inspect sldl >/dev/null 2>&1; then
    echo "⚠️  WARNING: Container still running! Forcing cleanup..."
    docker compose kill sldl
fi

echo "✓ Soulseek session closed cleanly."
echo "⏱️  Waiting 30 seconds to ensure disconnection..."
sleep 30

echo ""
echo "Safe to log into Soulseek now."
echo "Next: ./move_to_library.sh"