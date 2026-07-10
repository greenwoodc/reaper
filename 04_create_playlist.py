#!/usr/bin/env python3
"""
Reaper — Phase 4: Create playlist in Navidrome
Reads found_tracks.json and creates (or updates) the target playlist
in Navidrome via the Subsonic API, in countdown order.

Usage:
    python3 04_create_playlist.py --playlist "The Rock 2000"
"""

import argparse
import sys

from core.config import load_config
from core.create_playlist import (
    create_or_update_playlist,
    NoFoundTracksError,
    EmptyFoundTracksError,
)


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 4 — Create/Update Navidrome Playlist")
    parser.add_argument("--playlist", required=True, help="Playlist name (must match Phase 1–3 slug)")
    parser.add_argument("--title", default=None,
                        help="Override the Navidrome playlist display name (default: same as --playlist)")
    args = parser.parse_args()

    config = load_config()

    try:
        create_or_update_playlist(args.playlist, config, title=args.title)
    except (NoFoundTracksError, EmptyFoundTracksError) as exc:
        print(f"❌  {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
