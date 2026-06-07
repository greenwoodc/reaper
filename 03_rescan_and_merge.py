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
import csv
import json
import hashlib
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib import request, parse
from urllib.error import URLError

try:
    import yaml
except ImportError:
    yaml = None

# ── CONFIG ────────────────────────────────────────────────────────────────────
CONFIG_FILE = "config.yml"

DEFAULTS = {
    "navidrome_url": "http://localhost:4533/",
    "navidrome_user": "admin",
    "navidrome_password": "",
    "navidrome_client": "reaper",
    "navidrome_version": "1.16.1",
    "match_threshold": 0.80,
}
# ─────────────────────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Load config from config.yml, falling back to defaults."""
    config = dict(DEFAULTS)
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        print(f"[WARN] {CONFIG_FILE} not found — using defaults.")
        return config

    if yaml is None:
        return config

    with open(config_path) as f:
        loaded = yaml.safe_load(f) or {}

    config.update({k: v for k, v in loaded.items() if v is not None})
    return config


def slugify(name: str) -> str:
    """Convert a playlist name to its filesystem slug directory."""
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s_-]+', '_', name)
    return name.strip('_')


def subsonic_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode()).hexdigest()


def make_api_get(config: dict):
    """Return an api_get function bound to the given config."""
    base_url = config["navidrome_url"].rstrip("/")
    salt = "reaper"
    token = subsonic_token(config["navidrome_password"], salt)
    auth_base = {
        "u": config["navidrome_user"],
        "t": token,
        "s": salt,
        "v": config["navidrome_version"],
        "c": config["navidrome_client"],
        "f": "json",
    }

    def api_get(endpoint: str, params: dict) -> dict:
        merged = {**auth_base, **params}
        url = f"{base_url}/rest/{endpoint}?" + parse.urlencode(merged)
        try:
            with request.urlopen(url, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                payload = json.loads(raw)
                response = payload.get("subsonic-response", {})
                if response.get("status") not in (None, "ok"):
                    return {}
                return payload
        except (URLError, json.JSONDecodeError):
            return {}

    return api_get


def check_connection(api_get):
    """Verify Navidrome is reachable and credentials are valid before proceeding."""
    resp = api_get("ping.view", {})
    status = resp.get("subsonic-response", {}).get("status")
    if status != "ok":
        print("❌  Cannot reach Navidrome — check config.yml URL and credentials.")
        sys.exit(1)
    print("✓ Navidrome connection verified.")


def fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalise(s: str) -> str:
    """Ruthlessly strip noise, matching Phase 1 exactly."""
    if not s:
        return ""
    s = s.lower()

    s = re.sub(r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|bonus|original|studio|20\d{2}|19\d{2}).*?\)', '', s)

    if " - " in s:
        parts = s.split(" - ")
        if any(word in parts[-1] for word in ["remaster", "live", "acoustic", "version", "edit", "mix", "original", "20", "19"]):
            s = " - ".join(parts[:-1])

    s = s.replace("'", "")
    s = re.sub(r'[^\w\s-]', ' ', s)
    s = re.sub(r'\s+', ' ', s)

    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return s.strip()


def score_song(song: dict, clean_t: str, cleaned_artists: list, primary_artist: str) -> float:
    """Unified engine matching Phase 1 calculations precisely."""
    s_title = song.get("title", "")
    s_artist = song.get("artist", "")

    norm_s_title = normalise(s_title)
    norm_s_artist = normalise(s_artist)

    t_score = fuzzy(clean_t, norm_s_title)
    norm_primary = normalise(primary_artist)

    is_csv_shihad = norm_primary in ["shihad", "pacifier"]
    is_db_shihad = norm_s_artist in ["shihad", "pacifier", "shihad pacifier", "shihadpacifier"]

    if is_csv_shihad and is_db_shihad:
        a_score = 1.0
    else:
        a_score = max(fuzzy(normalise(artist), norm_s_artist) for artist in cleaned_artists)

    if norm_s_artist == "various artists" and norm_primary in norm_s_title:
        a_score = 1.0
        if " - " in norm_s_title:
            title_part = normalise(s_title.split(" - ")[0])
            t_score = max(t_score, fuzzy(clean_t, title_part))

    if norm_s_title == clean_t and a_score >= 0.70:
        a_score = max(a_score, 0.90)

    return t_score * 0.60 + a_score * 0.40


def trigger_scan(api_get):
    print("► Triggering Navidrome library scan...")
    resp = api_get("startScan.view", {})
    status = resp.get("subsonic-response", {}).get("scanStatus", {})
    if status:
        print(f"  Scan started — currently indexed: {status.get('count', '?')} files")
    else:
        print("  [WARN] Could not confirm scan initialization.")


def wait_for_scan(api_get):
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


def search_navidrome(api_get, artists: list, title: str, threshold: float) -> Optional[dict]:
    best_score, best_match = 0.0, None

    cleaned_artists = []
    for artist in artists:
        cleaned_artists.extend([a.strip() for a in artist.split(';') if a.strip()])

    primary_artist = cleaned_artists[0]
    primary_artist_no_punct = re.sub(r'[^\w\s]', '', primary_artist)
    clean_t = normalise(title)

    if normalise(primary_artist) in ["shihad", "pacifier"]:
        queries = ["Shihad " + clean_t, "Pacifier " + clean_t, clean_t]
    else:
        queries = [
            f"{primary_artist} {clean_t}",
            f"{primary_artist_no_punct} {clean_t}",
            title,
            clean_t,
        ]

    for query in list(dict.fromkeys(queries)):
        if not query or len(query.strip()) < 2:
            continue

        resp = api_get("search3.view", {
            "query": query.strip(),
            "songCount": 120,
            "artistCount": 0,
            "albumCount": 0
        })

        songs = resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", [])
        for song in songs:
            s = score_song(song, clean_t, cleaned_artists, primary_artist)
            if s > best_score:  # first match wins on ties
                best_score, best_match = s, song

    if best_score >= threshold:
        return best_match

    # Deep Fallback Pass — search by artist only, score all results
    fallback_targets = [primary_artist, primary_artist_no_punct]
    if normalise(primary_artist) in ["shihad", "pacifier"]:
        fallback_targets.extend(["Shihad", "Pacifier"])

    fallback_best_score, fallback_best_match = 0.0, None

    for fallback_query in list(dict.fromkeys(fallback_targets)):
        resp = api_get("search3.view", {
            "query": fallback_query,
            "songCount": 600,
            "artistCount": 0,
            "albumCount": 0
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song, clean_t, cleaned_artists, primary_artist)
            if s > fallback_best_score:  # first match wins on ties
                fallback_best_score, fallback_best_match = s, song

    if fallback_best_score >= threshold:
        return fallback_best_match

    return None


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 3 — Rescan and Merge Newly Found Tracks")
    parser.add_argument("--playlist", required=True, help="Playlist folder name within playlists/")
    args = parser.parse_args()

    slug = slugify(args.playlist)
    playlist_dir = Path("playlists") / slug

    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    if not found_file.exists():
        print(f"❌  {found_file} not found. Run Phase 1 scan first.")
        sys.exit(1)

    if not missing_file.exists():
        print(f"🎉 No missing_tracks.csv found for '{args.playlist}' — nothing to rescan!")
        return

    config = load_config()
    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    # Validate connection before doing anything
    check_connection(api_get)

    with open(found_file) as f:
        found = json.load(f)

    missing = []
    has_rank_column = False

    with open(missing_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_rank_column = "rank" in fieldnames

        for i, row in enumerate(reader):
            artist_str = row.get("artist", "")
            artists = [a.strip() for a in artist_str.split(";") if a.strip()]
            if not artists:
                artists = [a.strip() for a in artist_str.split(",") if a.strip()]

            rank_val = None
            if has_rank_column and row.get("rank"):
                try:
                    rank_val = int(row["rank"])
                except ValueError:
                    pass

            missing.append({
                "rank":    rank_val if rank_val is not None else (i + 1),
                "title":   row.get("title", ""),
                "artists": artists,
                "artist":  artists[0] if artists else artist_str,
                "album":   row.get("album", ""),
            })

    print(f"Playlist      : {args.playlist}")
    print(f"Current State : {len(found)} already matched, {len(missing)} targeted for rescan.\n")

    trigger_scan(api_get)
    try:
        wait_for_scan(api_get)
    except RuntimeError as exc:
        print(f"\n❌  {exc}")
        sys.exit(1)
    print()

    newly_found, still_missing = [], []

    for i, track in enumerate(missing, 1):
        sys.stdout.write(
            f"\r  [{i:4d}/{len(missing)}] "
            f"{track['artist'][:30]:<30} — {track['title'][:35]:<35}"
        )
        sys.stdout.flush()

        match = search_navidrome(api_get, track["artists"], track["title"], threshold)
        if match:
            entry = {
                "title":     track["title"],
                "artist":    track["artist"],
                "nd_id":     match["id"],
                "nd_title":  match.get("title", ""),
                "nd_artist": match.get("artist", ""),
            }
            if has_rank_column:
                entry["rank"] = track["rank"]
            newly_found.append(entry)
        else:
            still_missing.append(track)
        time.sleep(0.01)

    print(f"\n\n{'─'*62}")
    print(f"  Newly matched from storage: {len(newly_found):>4}")
    print(f"  Still missing             : {len(still_missing):>4}")
    print(f"{'─'*62}\n")

    # Merge and sort
    all_found = found + newly_found
    if has_rank_column:
        all_found = sorted(all_found, key=lambda x: x.get("rank", 9999))

    with open(found_file, "w") as f:
        json.dump(all_found, f, indent=2)
    print(f"✓ {found_file} updated ({len(all_found)} total tracks tracked)")

    # Write remaining missing back to CSV
    output_fields = ["artist", "title", "album"]
    if has_rank_column:
        output_fields.insert(0, "rank")

    with open(missing_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()
        for t in still_missing:
            row = {"artist": t["artist"], "title": t["title"], "album": t["album"]}
            if has_rank_column:
                row["rank"] = t["rank"]
            writer.writerow(row)

    print(f"✓ {missing_file} updated ({len(still_missing)} remaining items)")


if __name__ == "__main__":
    main()