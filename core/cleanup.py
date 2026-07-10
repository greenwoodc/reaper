"""Reaper — clean missing_tracks.csv for better Soulseek search hits.

clean_missing_csv() always returns the full diff (used by the webapp's
cleanup-preview endpoint); apply=True additionally overwrites csv_path in
place (used when actually starting a download).
"""

import csv
import re
import shutil
import unicodedata
from pathlib import Path


def simplify_text(s: str) -> str:
    """Remove diacritics and normalize unicode accents."""
    if not s:
        return ""
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def clean_punctuation(s: str) -> str:
    """
    Strip legacy P2P search hazards (ellipses, trailing dots, rogue symbols)
    while preserving basic spaces.
    """
    if not s:
        return ""
    s = re.sub(r'\.\.\.+', ' ', s)
    s = re.sub(r'[\[\]\(\)\"\'\’\‘\“”\.\,\!\?\*\:\-\—\–\/]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def clean_artist(artist: str) -> str:
    """Extract primary artist, handle specific band eras, and drop collab noise."""
    if not artist:
        return ""

    for sep in [';', ',', r'\band\b', r'\b&\b', r'\bfeat\.?\b', r'\bfeaturing\b', r'\bwith\b']:
        parts = re.split(sep, artist, flags=re.IGNORECASE)
        if len(parts) > 1:
            artist = parts[0].strip()

    artist = re.sub(r'\s*\(feat\..*?\)', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*\bfeaturing\b.*', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s+&\s+the\s+.*', '', artist, flags=re.IGNORECASE)

    return artist.strip()


def clean_title(title: str) -> str:
    """Apply refined right-split logic with strict word boundaries for metadata and collabs."""
    if not title:
        return ""

    title = re.sub(
        r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|featuring|bonus|original|studio|20\d{2}|19\d{2}|\bwith\b|\band\b|\bduet\b|\bvs\b|\bpresents\b|\bpres\b).*?\)',
        '', title, flags=re.IGNORECASE
    )

    if " - " in title:
        parts = title.split(" - ")
        if any(word in parts[-1].lower() for word in ["remaster", "live", "acoustic", "version", "edit", "mix", "original", "20", "19"]):
            title = " - ".join(parts[:-1])

    title = re.sub(r'\s*\(.*?\)\s*$', '', title)
    title = re.sub(r'\s*\(\s*\)', '', title)
    title = re.sub(r'\s*\[\s*\]', '', title)

    return title.strip()


def clean_missing_csv(csv_path: Path | str, apply: bool = True) -> list[dict]:
    """Clean artist/title columns of csv_path for Soulseek compatibility.

    Returns a list of row dicts (cleaned values, plus _orig_artist/_orig_title)
    for every row — callers filter for changed rows themselves. When apply is
    True, csv_path is overwritten in place with the cleaned values (original
    script's only behavior).
    """
    csv_path = Path(csv_path)
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        tracks = list(reader)

    cleaned = []
    for track in tracks:
        orig_artist = track.get('artist', '')
        orig_title = track.get('title', '')

        artist_clean = clean_artist(orig_artist)
        title_clean = clean_title(orig_title)

        artist_clean = simplify_text(artist_clean)
        title_clean = simplify_text(title_clean)

        artist_clean = clean_punctuation(artist_clean)
        title_clean = clean_punctuation(title_clean)

        cleaned_row = track.copy()
        cleaned_row['artist'] = artist_clean
        cleaned_row['title'] = title_clean

        cleaned_row['_orig_artist'] = orig_artist
        cleaned_row['_orig_title'] = orig_title
        cleaned.append(cleaned_row)

    if apply and cleaned:
        output_path = csv_path.with_name("missing_tracks_cleaned.tmp")
        output_fields = [f for f in fieldnames if f in sorted(cleaned[0].keys())] if fieldnames else ['rank', 'artist', 'title', 'album']

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction='ignore')
            writer.writeheader()
            for track in cleaned:
                writer.writerow(track)

        shutil.move(str(output_path), str(csv_path))

    return cleaned
