#!/usr/bin/env bash
# Rock 2000 — Phase 2: Download missing tracks via slsk-batchdl (Docker)
#
# Prerequisites:
#   1. Run 01_scan_navidrome.py first (produces config/missing_tracks.csv)
#   2. Edit config/sldl.conf with your Soulseek username/password
#   3. Have git and Docker installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── STEP 1: Build from custom Dockerfile with .NET 10 (master branch) ──
if ! docker image inspect slsk-batchdl &>/dev/null; then
    echo "► Building slsk-batchdl from master (with excluded phrase filter fix)..."
    docker build -t slsk-batchdl .
    echo "✓ Image built."
else
    echo "✓ slsk-batchdl image already exists."
fi

# ── STEP 1b: Clean up search phrases in missing_tracks.csv ──────────────────
if [ -f "$SCRIPT_DIR/config/missing_tracks.csv" ]; then
    echo ""
    echo "► Cleaning up CSV search phrases for better Soulseek hits..."
    python3 "$SCRIPT_DIR/01b_cleanup_missing_csv.py"
    if [ $? -ne 0 ]; then
        echo "❌  CSV cleanup failed. Check the error above."
        exit 1
    fi
fi

# ── STEP 2: Check prerequisites ──────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/config/missing_tracks.csv" ]; then
    echo "❌  config/missing_tracks.csv not found."
    echo "    Run: python3 01_scan_navidrome.py"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/config/sldl.conf" ]; then
    echo "❌  config/sldl.conf not found."
    exit 1
fi

# Quick sanity check — make sure credentials have been filled in
if grep -q "your_soulseek_username" "$SCRIPT_DIR/config/sldl.conf"; then
    echo "❌  Edit config/sldl.conf and set your Soulseek username/password first."
    exit 1
fi

TRACK_COUNT=$(tail -n +2 "$SCRIPT_DIR/config/missing_tracks.csv" | wc -l | tr -d ' ')
echo ""
echo "► Starting download of $TRACK_COUNT missing tracks..."
echo "  Music library : /mnt/4TBExt/Media/Music"
echo "  Download subdir: /mnt/4TBExt/Media/incoming"
echo "  Config dir    : $SCRIPT_DIR/config"
echo ""

# ── STEP 4: Get PUID/PGID from the music folder owner ────────────────────────
MUSIC_UID=$(stat -c '%u' /mnt/4TBExt/Media/Music)
MUSIC_GID=$(stat -c '%g' /mnt/4TBExt/Media/Music)

# Update compose env if they differ from defaults
if [ "$MUSIC_UID" != "1000" ] || [ "$MUSIC_GID" != "1000" ]; then
    echo "⚠  Music folder owned by UID=$MUSIC_UID GID=$MUSIC_GID"
    echo "   Update PUID/PGID in docker-compose.yml to match, then re-run."
    echo "   Current defaults are 1000:1000."
fi

# ── STEP 5: Run sldl inside the container ────────────────────────────────────
echo ""
echo "► Running sldl (output will stream below)..."
echo "  Press Ctrl+C to pause — re-running this script will resume (--skip-existing)."
echo "──────────────────────────────────────────────────────────────"

cd "$SCRIPT_DIR"
docker compose run --rm --no-deps sldl \
    -c /config/sldl.conf \
    /config/missing_tracks.csv \
    --artist-col "artist" \
    --title-col  "title" \
    --album-col  "album" \
    2>&1 | tee "$SCRIPT_DIR/config/download_log.txt"

echo ""
echo "──────────────────────────────────────────────────────────────"
echo "✓ Download session complete."
echo "  Full log: config/download_log.txt"

if [ -f "$SCRIPT_DIR/config/not_found.txt" ] && \
   [ -s "$SCRIPT_DIR/config/not_found.txt" ]; then
    NOT_FOUND=$(wc -l < "$SCRIPT_DIR/config/not_found.txt" | tr -d ' ')
    echo "  ⚠  $NOT_FOUND tracks not found on Soulseek — see config/not_found.txt"
fi

# CRITICAL: Ensure container exits cleanly to avoid account bans
echo ""
echo "► Cleaning up Docker container..."
docker compose down

# Verify container is stopped
if docker container inspect sldl >/dev/null 2>&1 2>/dev/null; then
    echo "⚠️  WARNING: Container still running! Forcing cleanup..."
    docker compose kill sldl
fi

echo "✓ Soulseek session closed cleanly."
echo "⏱️  Waiting 30 seconds to ensure disconnection..."
sleep 30

echo ""
echo "Safe to log into Soulseek now."
echo "Next: python3 03_rescan_and_merge.py"
