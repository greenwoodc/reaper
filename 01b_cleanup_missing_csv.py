#!/usr/bin/env python3
"""
Clean up search phrases in missing_tracks.csv for better Soulseek hits.
Leverages the robust normalization logic built for Phase 1 with added
protection against trailing parenthetical collaborations.
"""

import argparse
import csv
import re
import shutil
import sys
import unicodedata
from pathlib import Path


def slugify(name: str) -> str:
    """Convert a playlist name to its filesystem slug directory."""
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s_-]+', '_', name)
    return name.strip('_')


def simplify_text(s: str) -> str:
    """Remove diacritics and normalize unicode accents."""
    if not s:
        return ""
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def clean_artist(artist: str) -> str:
    """Extract primary artist, handle specific band eras, and drop collab noise."""
    if not artist:
        return ""
    
    # Handle multi-artist splits early
    for sep in [';', ',', ' and ', ' &', ' feat.', ' feat']:
        if sep in artist.lower():
            # Split and keep the primary artist
            artist = re.split(sep, artist, flags=re.IGNORECASE)[0].strip()

    # Drop trailing/inner feature parentheses left behind
    artist = re.sub(r'\s*\(feat\..*?\)', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*\bfeaturing\b.*', '', artist, flags=re.IGNORECASE)
    
    # Shihad / Pacifier Multi-era Soulseek search enhancement
    if artist.lower() in ["shihad", "pacifier", "shihad/pacifier"]:
        return "Shihad Pacifier"

    return artist.strip()


def clean_title(title: str) -> str:
    """Apply the refined Phase 1 right-split logic to strip metadata and collab bloat safely."""
    if not title:
        return ""

    # 1. Strip structural parenthesis blocks matching metadata keywords OR collaboration cues
    # Added: 'with', 'and', 'duet', 'featuring', 'feat', 'vs', 'presents', 'pres'
    title = re.sub(
        r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|featuring|bonus|original|studio|20\d{2}|19\d{2}|with|and|duet|vs|presents|pres).*?\)',
        '', title, flags=re.IGNORECASE
    )

    # 2. Right-side split for hyphens matching keywords (Matches 01_scan_navidrome logic)
    if " - " in title:
        parts = title.split(" - ")
        if any(word in parts[-1].lower() for word in ["remaster", "live", "acoustic", "version", "edit", "mix", "original", "20", "19"]):
            title = " - ".join(parts[:-1])

    # 3. Clean up empty brackets and trailing noise (But preserve internal hyphens/apostrophes)
    title = re.sub(r'\s*\(\s*\)', '', title)
    title = re.sub(r'\s*\[\s*\]', '', title)
    title = re.sub(r'\s+', ' ', title)
    
    return title.strip()


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 1b — Clean Missing CSV for Soulseek")
    parser.add_argument("--csv", help="Direct path to a missing_tracks.csv file")
    parser.add_argument("--playlist", help="Name of playlist folder inside playlists/ to target automatically")
    args = parser.parse_args()

    # Determine input file path location
    if args.csv:
        csv_path = Path(args.csv)
    elif args.playlist:
        slug = slugify(args.playlist)
        csv_path = Path("playlists") / slug / "missing_tracks.csv"
    else:
        # Fallback default lookup to match your previous setup
        csv_path = Path("playlists/hauraki_top_25/missing_tracks.csv")
        if not csv_path.exists():
            csv_path = Path("config/missing_tracks.csv")

    if not csv_path.exists():
        print(f"❌ Error: Target CSV not found at '{csv_path}'")
        print("Please specify path explicitly via: --csv path/to/file.csv or --playlist 'Playlist Name'")
        sys.exit(1)

    output_path = csv_path.with_name("missing_tracks_cleaned.tmp")

    print(f"Reading {csv_path}...")
    tracks = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            tracks.append(row)

    print(f"Loaded {len(tracks)} tracks. Cleaning string layout for Soulseek compatibility...")

    cleaned = []
    for track in tracks:
        orig_artist = track.get('artist', '')
        orig_title = track.get('title', '')

        # Process strings using the synchronized logic
        artist_clean = clean_artist(orig_artist)
        title_clean = clean_title(orig_title)

        # Normalize diacritics / special characters
        artist_clean = simplify_text(artist_clean)
        title_clean = simplify_text(title_clean)

        # Preserve the incoming metadata structure cleanly
        cleaned_row = track.copy()
        cleaned_row['artist'] = artist_clean
        cleaned_row['title'] = title_clean
        
        # Store metadata references to render debugging transformations nicely
        cleaned_row['_orig_artist'] = orig_artist
        cleaned_row['_orig_title'] = orig_title
        cleaned.append(cleaned_row)

    # Re-verify and compile required fields for writing out
    output_fields = [f for f in fieldnames if f in sorted(cleaned[0].keys())] if fieldnames else ['rank', 'artist', 'title', 'album']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction='ignore')
        writer.writeheader()
        for track in cleaned:
            writer.writerow(track)

    # Overwrite the original target file atomically
    shutil.move(str(output_path), str(csv_path))
    print(f"✓ Replaced file with Soulseek-optimized version: {csv_path}\n")

    # Display transformation comparisons
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