#!/usr/bin/env python3
"""
Clean up search phrases in missing_tracks.csv for better Soulseek hits.
Leverages Phase 1 normalization with strict word-boundary token matching.
No hardcoded track or artist exemptions.
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
    
    # Handle multi-artist splits early using strict boundaries or explicit delimiters
    for sep in [';', ',', r'\band\b', r'\b&\b', r'\bfeat\.?\b', r'\bfeaturing\b']:
        # Split on the separator if it matches as a standalone token/character
        parts = re.split(sep, artist, flags=re.IGNORECASE)
        if len(parts) > 1:
            artist = parts[0].strip()

    # Drop any trailing/inner feature parentheses left behind
    artist = re.sub(r'\s*\(feat\..*?\)', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*\bfeaturing\b.*', '', artist, flags=re.IGNORECASE)
    
    # Handle composite dual-identities safely using clean spacing
    artist = artist.replace('/', ' ')

    return artist.strip()


def clean_title(title: str) -> str:
    """Apply refined right-split logic with strict word boundaries for metadata and collabs."""
    if not title:
        return ""

    # 1. Strip structural metadata blocks safely.
    # We use \b (word boundaries) around short words so 'and' matches '(And I Feel Fine)' 
    # but completely ignores 'Stand' inside '(Stand by Me)'.
    title = re.sub(
        r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|featuring|bonus|original|studio|20\d{2}|19\d{2}|\bwith\b|\band\b|\bduet\b|\bvs\b|\bpresents\b|\bpres\b).*?\)',
        '', title, flags=re.IGNORECASE
    )

    # 2. Right-side split for hyphens matching keywords (Matches 01_scan_navidrome logic)
    if " - " in title:
        parts = title.split(" - ")
        if any(word in parts[-1].lower() for word in ["remaster", "live", "acoustic", "version", "edit", "mix", "original", "20", "19"]):
            title = " - ".join(parts[:-1])

    # 3. Clean up empty brackets and trailing noise (Preserving valid internal punctuation)
    title = re.sub(r'\s*\(\s*\)', '', title)
    title = re.sub(r'\s*\[\s*\]', '', title)
    title = re.sub(r'\s+', ' ', title)
    
    return title.strip()


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 1b — Clean Missing CSV for Soulseek")
    parser.add_argument("--csv", help="Direct path to a missing_tracks.csv file")
    parser.add_argument("--playlist", help="Name of playlist folder inside playlists/ to target automatically")
    args = parser.parse_args()

    if args.csv:
        csv_path = Path(args.csv)
    elif args.playlist:
        slug = slugify(args.playlist)
        csv_path = Path("playlists") / slug / "missing_tracks.csv"
    else:
        csv_path = Path("playlists/hauraki_top_25/missing_tracks.csv")
        if not csv_path.exists():
            csv_path = Path("config/missing_tracks.csv")

    if not csv_path.exists():
        print(f"❌ Error: Target CSV not found at '{csv_path}'")
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

        artist_clean = clean_artist(orig_artist)
        title_clean = clean_title(orig_title)

        artist_clean = simplify_text(artist_clean)
        title_clean = simplify_text(title_clean)

        cleaned_row = track.copy()
        cleaned_row['artist'] = artist_clean
        cleaned_row['title'] = title_clean
        
        cleaned_row['_orig_artist'] = orig_artist
        cleaned_row['_orig_title'] = orig_title
        cleaned.append(cleaned_row)

    output_fields = [f for f in fieldnames if f in sorted(cleaned[0].keys())] if fieldnames else ['rank', 'artist', 'title', 'album']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction='ignore')
        writer.writeheader()
        for track in cleaned:
            writer.writerow(track)

    shutil.move(str(output_path), str(csv_path))
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