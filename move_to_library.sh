#!/usr/bin/env bash
# Reaper — import downloaded tracks into the Music library via beets.
# Invoked by the webapp backend (backend/routes.py); also runnable directly.
#
# Usage:
#   ./move_to_library.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi
INCOMING_DIR="${REAPER_MEDIA_ROOT:-/mnt/4TBExt/Media}/incoming"

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
echo "Next: finalize the playlist from the webapp (rescan + create/update in Navidrome)."