#!/usr/bin/env python3
"""
Rock 2000 — Phase 1: Scan Navidrome
Reads the Spotify export CSV, searches Navidrome via the Subsonic API,
and produces:
  found_tracks.json          — Navidrome song IDs for playlist creation
  config/missing_tracks.csv  — songs to download via slsk-batchdl

Usage:
  python3 01_scan_navidrome.py             # normal run
  python3 01_scan_navidrome.py --dry-run   # preview changes, no files written
"""

import argparse
import csv
import json
import hashlib
import time
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib import request, parse
from urllib.error import URLError

# ── CONFIG ───────────────────────────────────────────────────────────────────
NAVIDROME_URL   = "http://100.92.200.19:4533/"
ND_USER         = "admin"
ND_PASSWORD     = "xGdADq3Vt9uUFX"
ND_CLIENT       = "rock2000scanner"
ND_VERSION      = "1.16.1"

CSV_FILE        = "The_Rock_2000__2025_.csv"
FOUND_FILE      = "found_tracks.json"
MISSING_FILE    = "config/missing_tracks.csv"

# Fuzzy match threshold 0.0–1.0.
# 0.75 works well; raise to 0.85 if you see false positives.
MATCH_THRESHOLD = 0.85
# ─────────────────────────────────────────────────────────────────────────────


def subsonic_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode()).hexdigest()


def api_get(endpoint: str, params: dict) -> dict:
    base_url = NAVIDROME_URL.rstrip("/")
    salt = "rock2000"
    token = subsonic_token(ND_PASSWORD, salt)
    base = {
        "u": ND_USER, "t": token, "s": salt,
        "v": ND_VERSION, "c": ND_CLIENT, "f": "json",
    }
    base.update(params)
    url = f"{base_url}/rest/{endpoint}?" + parse.urlencode(base)
    try:
        with request.urlopen(url, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                snippet = raw[:200].replace("\n", " ").replace("\r", " ")
                print(
                    f"\n  [ERROR] Navidrome returned non-JSON for {endpoint} "
                    f"(HTTP {getattr(resp, 'status', '?')}, "
                    f"content-type={resp.headers.get('Content-Type', '?')})"
                )
                print(f"  [ERROR] Body starts with: {snippet!r}")
                return {}

            response = payload.get("subsonic-response", {})
            if response.get("status") not in (None, "ok"):
                print(f"\n  [ERROR] API returned status={response.get('status')} for {endpoint}")
                return {}
            return payload
    except URLError as e:
        print(f"\n  [ERROR] API call failed: {e}")
        return {}


def fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalise(s: str) -> str:
    """Strip noise and normalise text before fuzzy matching."""
    # Remove bracketed noise
    s = re.sub(
        r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|bonus).*?\)',
        '', s, flags=re.IGNORECASE
    )
    s = re.sub(r'-\s*(remaster|remastered)\s*\d{4}', '', s, flags=re.IGNORECASE)
    # Remove featured artist from title
    s = re.sub(r'\s*(feat\.?|ft\.?|featuring)\s+.*', '', s, flags=re.IGNORECASE)
    # Normalise punctuation and separators
    s = re.sub(r'[/&+]', ' and ', s)        # AC/DC → AC and DC
    s = re.sub(r"'", '', s)                  # don't → dont
    s = re.sub(r'[^\w\s]', ' ', s)          # strip remaining punctuation
    s = re.sub(r'\s+', ' ', s)              # collapse spaces
    # Unicode normalisation: Motörhead → Motorhead
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return s.strip().lower()


def strip_feat(title: str) -> str:
    """Remove featured artist suffix from a title."""
    return re.sub(
        r'\s*(feat\.?|ft\.?|featuring)\s+.*', '', title, flags=re.IGNORECASE
    ).strip()


def search_navidrome(artists: list[str], title: str) -> dict | None:
    """
    Search Navidrome for a song.
    Accepts a list of artists (all from the Spotify CSV).
    Returns best-matching song dict or None.
    Two-pass strategy: title search first, then artist search as fallback.
    Score weighted 55% title / 45% artist.
    """
    best_score, best_match = 0.0, None

    def score_song(song: dict) -> float:
        t = fuzzy(normalise(title), normalise(song.get("title", "")))
        a = max(
            fuzzy(normalise(artist), normalise(song.get("artist", "")))
            for artist in artists
        )
        return t * 0.55 + a * 0.45

    # Pass 1: search by title (try with and without feat. suffix)
    title_queries = list(dict.fromkeys([normalise(title), normalise(strip_feat(title))]))
    for query in title_queries:
        resp = api_get("search3.view", {
            "query": query, "songCount": 10,
            "artistCount": 0, "albumCount": 0,
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song)
            if s > best_score:
                best_score, best_match = s, song

    if best_score >= MATCH_THRESHOLD:
        return best_match

    # Pass 2: search by each artist name
    for artist in artists:
        resp = api_get("search3.view", {
            "query": normalise(artist), "songCount": 20,
            "artistCount": 0, "albumCount": 0,
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song)
            if s > best_score:
                best_score, best_match = s, song

    return best_match if best_score >= MATCH_THRESHOLD else None


def load_existing() -> tuple[set[str], set[str]]:
    """Load existing found/missing URIs for comparison in dry-run mode."""
    found_uris = set()
    missing_uris = set()

    if Path(FOUND_FILE).exists():
        with open(FOUND_FILE) as f:
            for t in json.load(f):
                found_uris.add(t.get("uri", t.get("title", "")))

    if Path(MISSING_FILE).exists():
        with open(MISSING_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                missing_uris.add(row.get("title", ""))

    return found_uris, missing_uris


def main():
    parser = argparse.ArgumentParser(description="Rock 2000 Phase 1 — Scan Navidrome")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing any files")
    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN — no files will be written\n")

    Path("config").mkdir(exist_ok=True)

    print(f"Reading {CSV_FILE}...")
    tracks = []
    with open(CSV_FILE, newline='', encoding='utf-8-sig') as f:
        for i, row in enumerate(csv.DictReader(f)):
            all_artists = [a.strip() for a in row["Artist Name(s)"].split(",")]
            tracks.append({
                "rank":    2000 - i,
                "title":   row["Track Name"],
                "artists": all_artists,
                "artist":  all_artists[0],
                "album":   row["Album Name"],
                "uri":     row["Track URI"],
            })

    tracks.sort(key=lambda x: x["rank"])
    print(f"Loaded {len(tracks)} tracks. Scanning Navidrome...\n")

    # Load existing state for dry-run comparison
    existing_found_uris, existing_missing_titles = load_existing()

    found, missing = [], []

    for i, track in enumerate(tracks, 1):
        sys.stdout.write(
            f"\r  [{i:4d}/{len(tracks)}] "
            f"{track['artist'][:30]:<30} — {track['title'][:35]:<35}"
        )
        sys.stdout.flush()

        match = search_navidrome(track["artists"], track["title"])
        if match:
            found.append({
                "rank":      track["rank"],
                "title":     track["title"],
                "artist":    track["artist"],
                "uri":       track["uri"],
                "nd_id":     match["id"],
                "nd_title":  match.get("title", ""),
                "nd_artist": match.get("artist", ""),
            })
        else:
            missing.append(track)

        time.sleep(0.05)

    print(f"\n\n{'─'*62}")
    print(f"  Found in collection : {len(found):>4}")
    print(f"  Missing             : {len(missing):>4}")
    print(f"{'─'*62}\n")

    if args.dry_run:
        # Show what changed vs current state
        newly_found = [t for t in found if t["title"] in existing_missing_titles]
        newly_missing = [t for t in missing if t["uri"] in existing_found_uris]

        print(f"{'─'*62}")
        print(f"  DRY RUN DIFF vs current files")
        print(f"{'─'*62}")
        print(f"  Tracks now found that were missing : {len(newly_found):>4}")
        print(f"  Tracks now missing that were found : {len(newly_missing):>4}")
        print(f"{'─'*62}\n")

        if newly_found:
            print("✓ Newly matched (would be removed from missing_tracks.csv):")
            for t in newly_found:
                print(f"    {t['artist']:<30} — {t['title']}")
                print(f"      matched → {t['nd_artist']} — {t['nd_title']}")

        if newly_missing:
            print("\n⚠️  Newly missing (would be removed from found_tracks.json):")
            for t in newly_missing:
                print(f"    {t['artist']:<30} — {t['title']}")

        if not newly_found and not newly_missing:
            print("  No changes detected — results identical to current files.")

        print("\n[DRY RUN] No files written.")
        return

    # Normal run — write output files
    with open(FOUND_FILE, "w") as f:
        json.dump(found, f, indent=2)
    print(f"✓ {FOUND_FILE}  ({len(found)} tracks)")

    with open(MISSING_FILE, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "artist", "title", "album"])
        writer.writeheader()
        for t in missing:
            writer.writerow({
                "rank":   t["rank"],
                "artist": t["artist"],
                "title":  t["title"],
                "album":  t["album"],
            })
    print(f"✓ {MISSING_FILE}  ({len(missing)} tracks to download)")
    print("\nNext: ./02_download_missing.sh")


if __name__ == "__main__":
    main()
