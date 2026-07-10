#!/usr/bin/env python3
"""
Clean up search phrases in missing_tracks.csv for better Soulseek hits.
Leverages Phase 1 normalization with strict word-boundary token matching.
No hardcoded track or artist exemptions.
"""

import argparse
import sys

from core.cleanup import clean_missing_csv, resolve_missing_csv_path


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 1b — Clean Missing CSV for Soulseek")
    parser.add_argument("--csv", help="Direct path to a missing_tracks.csv file")
    parser.add_argument("--playlist", help="Name of playlist folder inside playlists/ to target automatically")
    args = parser.parse_args()

    csv_path = resolve_missing_csv_path(args.csv, args.playlist)

    if not csv_path.exists():
        print(f"❌ Error: Target CSV not found at '{csv_path}'")
        sys.exit(1)

    print(f"Reading {csv_path}...")
    cleaned = clean_missing_csv(csv_path, apply=True)
    print(f"Loaded {len(cleaned)} tracks. Cleaning string layout for Soulseek compatibility...")
    print(f"✓ Replaced file with Soulseek-optimized version: {csv_path}\n")

    print("Sample Modifications Visualizer (Max 10):")
    print(f"{'─'*100}")
    count = 0
    for track in cleaned:
        changed_artist = track['_orig_artist'] != track['artist']
        changed_title = track['_orig_title'] != track['title']

        if changed_artist or changed_title:
            rank_val = track.get('rank', 'N/A')
            print(f"\nTrack [Rank {rank_val}]:")
            if changed_artist:
                print(f"  Artist: {track['_orig_artist']!r:<45} →  {track['artist']!r}")
            if changed_title:
                print(f"  Title:  {track['_orig_title']!r:<45} →  {track['title']!r}")
            count += 1
            if count >= 10:
                break

    print(f"\n{'─'*100}")
    print(f"✓ Post-processing total: {len(cleaned)} tracks successfully structured for Soulseek extraction.")


if __name__ == "__main__":
    main()
