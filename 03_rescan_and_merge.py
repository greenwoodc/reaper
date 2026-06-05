#!/usr/bin/env python3
"""
Rock 2000 — Phase 3: Rescan Navidrome & merge
After 02_download_missing.sh and beets import complete, run this to:
  1. Trigger a Navidrome library rescan (waits for completion)
  2. Re-search for previously missing tracks
  3. Merge newly found ones into found_tracks.json
  4. Update config/missing_tracks.csv with anything still absent
"""

import csv
import json
import hashlib
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib import request, parse
from urllib.error import URLError

# ── CONFIG (must match 01_scan_navidrome.py) ──────────────────────────────────
NAVIDROME_URL   = "http://100.92.200.19:4533/"
ND_USER         = "admin"
ND_PASSWORD     = "xGdADq3Vt9uUFX"
ND_CLIENT       = "rock2000scanner"
ND_VERSION      = "1.16.1"
MATCH_THRESHOLD = 0.85
# ─────────────────────────────────────────────────────────────────────────────

FOUND_FILE   = "found_tracks.json"
MISSING_FILE = "config/missing_tracks.csv"


def subsonic_token(password, salt):
    return hashlib.md5((password + salt).encode()).hexdigest()


def api_get(endpoint, params):
    base_url = NAVIDROME_URL.rstrip("/")
    salt = "rock2000"
    token = subsonic_token(ND_PASSWORD, salt)
    base = {"u": ND_USER, "t": token, "s": salt,
            "v": ND_VERSION, "c": ND_CLIENT, "f": "json"}
    base.update(params)
    url = f"{base_url}/rest/{endpoint}?" + parse.urlencode(base)
    try:
        with request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read())
            response = payload.get("subsonic-response", {})
            if response.get("status") not in (None, "ok"):
                print(f"\n  [ERROR] API returned status={response.get('status')} for {endpoint}")
                return {}
            return payload
    except URLError as e:
        print(f"\n  [ERROR] {e}")
        return {}


def fuzzy(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalise(s):
    """Strip noise and normalise text before fuzzy matching."""
    s = re.sub(
        r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|bonus).*?\)',
        '', s, flags=re.IGNORECASE
    )
    s = re.sub(r'-\s*(remaster|remastered)\s*\d{4}', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*(feat\.?|ft\.?|featuring)\s+.*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[/&+]', ' and ', s)
    s = re.sub(r"'", '', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return s.strip().lower()


def strip_feat(title):
    """Remove featured artist suffix from a title."""
    return re.sub(
        r'\s*(feat\.?|ft\.?|featuring)\s+.*', '', title, flags=re.IGNORECASE
    ).strip()


def trigger_scan():
    print("► Triggering Navidrome library scan...")
    resp = api_get("startScan.view", {})
    status = resp.get("subsonic-response", {}).get("scanStatus", {})
    if status:
        print(f"  Scan started — currently indexed: {status.get('count', '?')} files")
    else:
        print("  [WARN] Could not confirm scan started. Check Navidrome is running.")


def wait_for_scan():
    print("  Waiting for scan to complete", end="", flush=True)
    while True:
        time.sleep(5)
        resp = api_get("getScanStatus.view", {})
        if not resp:
            raise RuntimeError("Unable to read Navidrome scan status")
        status = resp.get("subsonic-response", {}).get("scanStatus", {})
        if not status.get("scanning", True):
            print(f"\n  ✓ Scan complete — {status.get('count', '?')} files indexed.")
            return
        print(".", end="", flush=True)


def search_navidrome(artists, title):
    """
    Search Navidrome for a song.
    Accepts a list of artists.
    Returns best-matching song dict or None.
    """
    best_score, best_match = 0.0, None

    def score_song(song):
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


def main():
    # Load existing found list
    if not Path(FOUND_FILE).exists():
        print(f"❌  {FOUND_FILE} not found. Run 01_scan_navidrome.py first.")
        sys.exit(1)

    with open(FOUND_FILE) as f:
        found = json.load(f)

    # Load missing list
    if not Path(MISSING_FILE).exists():
        print("No missing_tracks.csv found — nothing to rescan for.")
        return

    missing = []
    with open(MISSING_FILE, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            # Support both single artist string and comma-separated list
            artist_str = row["artist"]
            artists = [a.strip() for a in artist_str.split(",")]
            missing.append({
                "rank":    int(row["rank"]),
                "title":   row["title"],
                "artists": artists,
                "artist":  artists[0],
                "album":   row.get("album", ""),
            })

    print(f"Loaded {len(found)} found, {len(missing)} missing.\n")

    # Trigger and wait for rescan
    trigger_scan()
    try:
        wait_for_scan()
    except RuntimeError as exc:
        print(f"\n❌  {exc}")
        sys.exit(1)
    print()

    # Re-search for previously missing tracks
    newly_found, still_missing = [], []

    for i, track in enumerate(missing, 1):
        sys.stdout.write(
            f"\r  [{i:3d}/{len(missing)}] "
            f"{track['artist'][:28]:<28} — {track['title'][:33]:<33}"
        )
        sys.stdout.flush()

        match = search_navidrome(track["artists"], track["title"])
        if match:
            newly_found.append({
                "rank":      track["rank"],
                "title":     track["title"],
                "artist":    track["artist"],
                "nd_id":     match["id"],
                "nd_title":  match.get("title", ""),
                "nd_artist": match.get("artist", ""),
            })
        else:
            still_missing.append(track)
        time.sleep(0.05)

    print(f"\n\n{'─'*62}")
    print(f"  Newly found   : {len(newly_found):>4}")
    print(f"  Still missing : {len(still_missing):>4}")
    print(f"{'─'*62}\n")

    # Merge and save
    all_found = sorted(found + newly_found, key=lambda x: x["rank"])
    with open(FOUND_FILE, "w") as f:
        json.dump(all_found, f, indent=2)
    print(f"✓ {FOUND_FILE} updated ({len(all_found)} total tracks)")

    # Update missing CSV
    with open(MISSING_FILE, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "artist", "title", "album"])
        writer.writeheader()
        for t in still_missing:
            writer.writerow({"rank": t["rank"], "artist": t["artist"],
                             "title": t["title"], "album": t.get("album", "")})
    print(f"✓ {MISSING_FILE} updated ({len(still_missing)} still missing)")

    if still_missing:
        print(f"\n  Tip: re-run 02_download_missing.sh to retry Soulseek,")
        print(f"  or check config/not_found.txt for manual sourcing.")

    print("\nNext: python3 04_create_playlist.py")


if __name__ == "__main__":
    main()
