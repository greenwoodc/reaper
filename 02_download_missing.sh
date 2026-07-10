#!/usr/bin/env bash
# Reaper — Phase 2: Download missing tracks via sockseek (Docker)
#
# Usage:
#   ./02_download_missing.sh --playlist "Hauraki Top 25"
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
MEDIA_ROOT="${REAPER_MEDIA_ROOT:-/mnt/4TBExt/Media}"
MUSIC_DIR="$MEDIA_ROOT/Music"
INCOMING_DIR="$MEDIA_ROOT/incoming"

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
    echo "❌  python3 not found in PATH. Required for Phase 1b cleanup."
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

# ── STEP 3: Run Phase 1b String Cleanup dynamically ─────────────────────────
echo ""
echo "► Launching cleanup phase on target playlist directory..."
python3 "$SCRIPT_DIR/01b_cleanup_missing_csv.py" --playlist "$PLAYLIST"

if [ ! -f "$CSV_PATH" ]; then
    echo "❌  Target CSV not found at: $CSV_PATH"
    exit 1
fi

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

# Verified argument: --max-retries limits endless loop behaviors on locked users
docker compose run --rm --no-deps sldl \
    -c /config/sldl.conf \
    "/config/active_search.csv" \
    --artist-col "artist" \
    --title-col  "title" \
    --max-retries 1 \
    2>&1 | stdbuf -oL tee "$PLAYLIST_DIR/download_log.txt"

echo ""
echo "──────────────────────────────────────────────────────────────"
echo "✓ Download session complete."
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
echo "Next: ./02b_move_to_library.sh"
echo "Then: python3 03_rescan_and_merge.py --playlist \"$PLAYLIST\""