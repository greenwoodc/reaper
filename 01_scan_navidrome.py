#!/usr/bin/env python3
"""
Reaper — Phase 1: Scan Navidrome
Reads an Exportify CSV, searches Navidrome via the Subsonic API,
and produces per-playlist output files.
"""

import argparse
import sys
from pathlib import Path

from core.config import load_config
from core.scan import run_scan


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 1 — Scan Navidrome")
    parser.add_argument("--csv", required=True, help="Path to Exportify CSV file")
    parser.add_argument("--name", default=None,
                        help="Playlist name (default: derived from CSV filename)")
    parser.add_argument("--rank-col", default=None,
                        help="CSV column to use for track ranking (optional)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing any files")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌  CSV file not found: {csv_path}")
        sys.exit(1)

    playlist_name = args.name or csv_path.stem.replace("_", " ").replace("-", " ").strip()

    config = load_config()
    run_scan(csv_path, playlist_name, config, rank_col=args.rank_col, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
