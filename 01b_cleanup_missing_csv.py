#!/usr/bin/env python3
"""
Clean up search phrases in missing_tracks.csv for better Soulseek hits.
Removes remaster/deluxe/edition suffixes, simplifies featured artists,
and normalizes special characters.
"""

import csv
import re
import unicodedata
from pathlib import Path


def simplify_text(s: str) -> str:
    """Remove diacritics and normalize unicode."""
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def clean_artist(artist: str) -> str:
    """Extract primary artist, remove featured/collaboration cruft."""
    # Split on semicolons, commas, " and ", " feat", " with"
    # and take the first part
    for sep in [';', ',', ' and ', ' &']:
        if sep in artist:
            artist = artist.split(sep)[0].strip()

    # Remove (feat. ...) style info
    artist = re.sub(r'\s*\(feat\..*?\)', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*\bfeat\..*', '', artist, flags=re.IGNORECASE)

    return artist.strip()


def clean_title(title: str) -> str:
    """Remove remaster/deluxe/edition/version noise and featured artists from title."""
    # Remove things like "- 2009 Remaster", "- Remastered", etc.
    title = re.sub(
        r'\s*[-–]?\s*(20\d{2}\s+)?Remaster(ed)?(\s+\d{4})?',
        '', title, flags=re.IGNORECASE
    )

    # Remove (edition) style tags
    title = re.sub(
        r'\s*\(.*?(deluxe|edition|version|remix|mix|remaster|mono|stereo|expanded|special|live).*?\)',
        '', title, flags=re.IGNORECASE
    )

    # Remove (feat. ...) and (featuring ...) tags - these break Soulseek searches
    title = re.sub(
        r'\s*\(.*?(feat\.|featuring).*?\)',
        '', title, flags=re.IGNORECASE
    )

    # Remove studio/live prefixes and suffixes
    title = re.sub(r'^\s*\(.*?(Live|Studio).*?\)\s*', '', title, flags=re.IGNORECASE)

    # Clean up apostrophes (curly vs straight)
    title = title.replace("'", "'")

    # Remove empty parentheses left behind
    title = re.sub(r'\s*\(\s*\)', '', title)

    # Remove excess whitespace
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def main():
    csv_path = Path("config/missing_tracks.csv")
    output_path = Path("config/missing_tracks_cleaned.csv")

    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        return

    print(f"Reading {csv_path}...")
    tracks = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracks.append(row)

    print(f"Loaded {len(tracks)} tracks. Cleaning...")

    cleaned = []
    for track in tracks:
        artist = track['artist']
        title = track['title']

        # Clean
        artist_clean = clean_artist(artist)
        title_clean = clean_title(title)

        # Normalize diacritics for Soulseek
        artist_clean = simplify_text(artist_clean)
        title_clean = simplify_text(title_clean)

        cleaned.append({
            'rank': track['rank'],
            'artist': artist_clean,
            'title': title_clean,
            'album': track['album'],
            'artist_orig': artist,
            'title_orig': title,
        })

    # Write cleaned CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['rank', 'artist', 'title', 'album']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for track in cleaned:
            writer.writerow({k: track[k] for k in fieldnames})

    print(f"✓ {output_path}")

    # AUTO-REPLACE the original CSV with cleaned version
    import shutil
    shutil.move(str(output_path), str(csv_path))
    print(f"✓ Replaced original CSV with cleaned version\n")

    # Show some examples of changes
    print("Sample changes (first 10):")
    print(f"{'─'*100}")
    count = 0
    for track in cleaned[:20]:
        if track['artist_orig'] != track['artist'] or track['title_orig'] != track['title']:
            print(f"\nTrack {track['rank']}:")
            if track['artist_orig'] != track['artist']:
                print(f"  Artist: {track['artist_orig']!r}")
                print(f"      →  {track['artist']!r}")
            if track['title_orig'] != track['title']:
                print(f"  Title:  {track['title_orig']!r}")
                print(f"      →  {track['title']!r}")
            count += 1
            if count >= 10:
                break

    print(f"\n{'─'*100}")
    print(f"✓ Cleaned {len(cleaned)} tracks and auto-replaced original")
    print(f"  Ready for download!\n")


if __name__ == "__main__":
    main()
