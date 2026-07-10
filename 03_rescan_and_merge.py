#!/usr/bin/env python3
"""
Reaper — Phase 3: Rescan Navidrome & Merge
After downloading missing tracks via Soulseek and running a beets import, run this to:
  1. Trigger a Navidrome library rescan (waits for completion)
  2. Re-search for previously missing tracks inside the dynamic playlist folder
  3. Merge newly found ones into found_tracks.json
  4. Update missing_tracks.csv with anything still absent
"""

import argparse
import sys

from core.config import load_config
from core.rescan import run_rescan, NoFoundFileError, ScanTimeoutError


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 3 — Rescan and Merge Newly Found Tracks")
    parser.add_argument("--playlist", required=True, help="Playlist folder name within playlists/")
    args = parser.parse_args()

    config = load_config()

    try:
        run_rescan(args.playlist, config)
    except NoFoundFileError as exc:
        print(f"❌  {exc}")
        sys.exit(1)
    except ScanTimeoutError as exc:
        print(f"\n❌  {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
