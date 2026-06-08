#!/usr/bin/env bash
# Reaper — Phase 2b: Import downloaded tracks into Music library via beets
#
# Usage:
#   ./02b_move_to_library.sh

set -euo pipefail

INCOMING_DIR="/mnt/4TBExt/Media/incoming"

echo "► Cleaning up any incomplete downloads..."
find "$INCOMING_DIR" -name "*.incomplete" -delete
echo "✓ Incomplete files removed."

echo ""
echo "► Running beets import on: $INCOMING_DIR"
echo "  (duplicates will be skipped and cleaned up automatically)"
echo ""

rm -f ~/.config/beets/state.pickle
beet import -q --singletons "$INCOMING_DIR"

echo ""
echo "► Cleaning up empty directories in incoming..."
find "$INCOMING_DIR" -type d -empty -delete
echo "✓ Done."

echo ""
REMAINING=$(find "$INCOMING_DIR" -type f | wc -l | tr -d ' ')
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  $REMAINING files remain in incoming (check beets-import.log for details):"
    find "$INCOMING_DIR" -type f | head -10
else
    echo "✓ Incoming directory is clear."
fi

echo ""
echo "Next: python3 03_rescan_and_merge.py --playlist \"<Playlist Name>\""