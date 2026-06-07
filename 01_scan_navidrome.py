#!/usr/bin/env python3
"""
Reaper — Phase 1: Scan Navidrome
Reads an Exportify CSV, searches Navidrome via the Subsonic API,
and produces per-playlist output files.
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
    "match_threshold": 0.85,
}
# ─────────────────────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Load config from config.yml, falling back to defaults."""
    config = dict(DEFAULTS)
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        print(f"[WARN] {CONFIG_FILE} not found — using defaults. Run: cp config.example.yaml config.yml")
        return config

    if yaml is None:
        print("[WARN] pyyaml not installed — pip install pyyaml. Using defaults.")
        return config

    with open(config_path) as f:
        loaded = yaml.safe_load(f) or {}

    config.update({k: v for k, v in loaded.items() if v is not None})
    return config


def slugify(name: str) -> str:
    """Convert a playlist name or filename to a filesystem-safe slug."""
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
            with request.urlopen(url, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    return {}
                response = payload.get("subsonic-response", {})
                if response.get("status") not in (None, "ok"):
                    return {}
                return payload
        except URLError:
            return {}

    return api_get


def fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalise(s: str) -> str:
    """Ruthlessly strip noise, remastered years, live versions, and metadata bloat."""
    if not s:
        return ""
    s = s.lower()
    
    # 1. Remove anything in parentheses that looks like metadata
    s = re.sub(r'\(.*?(remaster|remastered|deluxe|edition|version|mix|mono|stereo|live|feat|bonus|original|studio|20\d{2}|19\d{2}).*?\)', '', s)
    
    # 2. Right-side split for hyphens to handle "Orange Crush - Remaster" vs "Thirty-Three"
    if " - " in s:
        parts = s.split(" - ")
        if any(word in parts[-1] for word in ["remaster", "live", "acoustic", "version", "edit", "mix", "original", "20", "19"]):
            s = " - ".join(parts[:-1])

    # 3. Final scrub of punctuation and multi-spaces
    s = s.replace("'", "")
    s = re.sub(r'[^\w\s-]', ' ', s) # Keep inner hyphens
    s = re.sub(r'\s+', ' ', s)
    
    # 4. Strip unicode accents
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return s.strip()


def score_song(song: dict, clean_t: str, cleaned_artists: list[str], primary_artist: str) -> float:
    """Unified engine to cleanly calculate track precision weightings."""
    s_title = song.get("title", "")
    s_artist = song.get("artist", "")
    
    norm_s_title = normalise(s_title)
    norm_s_artist = normalise(s_artist)

    t_score = fuzzy(clean_t, norm_s_title)
    a_score = max(fuzzy(normalise(artist), norm_s_artist) for artist in cleaned_artists)

    # Compilation Check
    if norm_s_artist == "various artists" and normalise(primary_artist) in norm_s_title:
        a_score = 1.0
        if " - " in norm_s_title:
            title_part = normalise(s_title.split(" - ")[0])
            t_score = max(t_score, fuzzy(clean_t, title_part))

    # Title Anchor Boost (e.g. Shihad/Pacifier fallback preservation)
    if norm_s_title == clean_t and a_score >= 0.70:
        a_score = max(a_score, 0.90)

    return t_score * 0.60 + a_score * 0.40


def search_navidrome(api_get, artists: list[str], title: str, threshold: float) -> dict | None:
    best_score, best_match = 0.0, None

    cleaned_artists = []
    for artist in artists:
        cleaned_artists.extend([a.strip() for a in artist.split(';') if a.strip()])

    primary_artist = cleaned_artists[0]
    primary_artist_no_punct = re.sub(r'[^\w\s]', '', primary_artist)
    clean_t = normalise(title)
    
    is_stubborn = clean_t in ["orange crush", "stand", "tribute", "home again", "all along the watchtower"]

    # Queries tree configuration
    queries = [
        f"{primary_artist} {clean_t}",          
        f"{primary_artist_no_punct} {clean_t}", 
        title,                                  
        clean_t,                                
    ]

    if is_stubborn:
        print(f"\n\n🔍 [LIVE DEBUG] Troubleshooting match for: {primary_artist} — {title}")

    for query in list(dict.fromkeys(queries)):
        if not query or len(query.strip()) < 2: 
            continue
            
        if is_stubborn:
            print(f"  👉 Querying API: '{query.strip()}'")

        resp = api_get("search3.view", {
            "query": query.strip(), 
            "songCount": 120,
            "artistCount": 0,
            "albumCount": 0
        })
        
        songs = resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", [])
        for song in songs:
            s = score_song(song, clean_t, cleaned_artists, primary_artist)
            if is_stubborn:
                print(f"     ↳ Match Found: '{song.get('artist')} — {song.get('title')}' [Score: {s:.2f}]")
            if s >= best_score:  # Inclusive assignment solves identical boundary matches
                best_score, best_match = s, song

    if best_score >= threshold:
        if is_stubborn:
            print(f"  ✅ SUCCESS: Matched with score {best_score:.2f}\n")
        return best_match

    # Deep Fallback Pass — Expand buffer limits to force truncation bypass
    if is_stubborn:
        print(f"  ⚠️  Low scores. Attempting absolute fallback search for artist catalogs.")

    for fallback_query in list(dict.fromkeys([primary_artist, primary_artist_no_punct])):
        resp = api_get("search3.view", {
            "query": fallback_query, 
            "songCount": 500, # Expanded volume catch
            "artistCount": 0,
            "albumCount": 0
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song, clean_t, cleaned_artists, primary_artist)
            if s >= best_score:
                best_score, best_match = s, song

    if is_stubborn:
        if best_score >= threshold:
            print(f"  ✅ SUCCESS IN FALLBACK: Matched '{best_match.get('artist')} — {best_match.get('title')}' ({best_score:.2f})\n")
        else:
            print(f"  ❌ FAILURE: Best found was '{best_match.get('artist') if best_match else 'None'} — {best_match.get('title') if best_match else 'None'}' with score {best_score:.2f} (Needs {threshold})\n")

    return best_match if best_score >= threshold else None


def load_existing(found_file: Path, missing_file: Path) -> tuple[set[str], set[str]]:
    found_uris = set()
    missing_titles = set()

    if found_file.exists():
        with open(found_file) as f:
            for t in json.load(f):
                found_uris.add(t.get("uri", t.get("title", "")))

    if missing_file.exists():
        with open(missing_file, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                missing_titles.add(row.get("title", ""))

    return found_uris, missing_titles


def read_csv(csv_path: Path, rank_col: str | None) -> list[dict]:
    """Read Exportify CSV and return list of track dicts."""
    tracks = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i, row in enumerate(rows):
        all_artists = [a.strip() for a in row["Artist Name(s)"].split(",")]

        if rank_col:
            try:
                rank = int(row[rank_col])
            except (KeyError, ValueError):
                print(f"[WARN] Could not read rank from column '{rank_col}' on row {i+1}, using row order.")
                rank = i + 1
        else:
            rank = None

        tracks.append({
            "rank":    rank,
            "title":   row["Track Name"],
            "artists": all_artists,
            "artist":  all_artists[0],
            "album":   row.get("Album Name", ""),
            "uri":     row.get("Track URI", ""),
        })

    if rank_col:
        tracks.sort(key=lambda x: x["rank"])

    return tracks


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
    slug = slugify(playlist_name)

    playlist_dir = Path("playlists") / slug
    playlist_dir.mkdir(parents=True, exist_ok=True)

    found_file   = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    config = load_config()
    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    if args.dry_run:
        print("🔍 DRY RUN — no files will be written\n")

    print(f"Playlist : {playlist_name}")
    print(f"Slug     : {slug}")
    print(f"Output   : playlists/{slug}/")
    print(f"CSV      : {csv_path}")
    if args.rank_col:
        print(f"Ranking  : by column '{args.rank_col}'")
    else:
        print(f"Ranking  : none (CSV order preserved)")
    print()

    print("🛠️  [DEBUG] Normalisation String Cleanup Transformations:")
    test_items = [
        "All Along the Watchtower",
        "The Man Who Sold The World - Live",
        "Just Like Heaven - Remastered 2006",
        "Reckless (Don't Be So...) - Remastered",
        "Say It Ain't So - Original Mix",
        "Orange Crush - Remastered 2013",
        "Run Like Hell - Live",
        "It's The End Of The World As We Know It (And I Feel Fine)"
    ]
    for item in test_items:
        print(f"    Original: {item:<60} → Normalised: {normalise(item)}")
    print("──────────────────────────────────────────────────────────────\n")

    print(f"Reading {csv_path}...")
    tracks = read_csv(csv_path, args.rank_col)
    print(f"Loaded {len(tracks)} tracks. Scanning Navidrome...\n")

    existing_found_uris, existing_missing_titles = load_existing(found_file, missing_file)

    found, missing = [], []

    for i, track in enumerate(tracks, 1):
        is_stubborn = normalise(track["title"]) in ["orange crush", "stand", "tribute", "home again", "all along the watchtower"]
        if not is_stubborn:
            sys.stdout.write(
                f"\r  [{i:4d}/{len(tracks)}] "
                f"{track['artist'][:30]:<30} — {track['title'][:35]:<35}"
            )
            sys.stdout.flush()

        match = search_navidrome(api_get, track["artists"], track["title"], threshold)
        if match:
            entry = {
                "title":     track["title"],
                "artist":    track["artist"],
                "uri":       track["uri"],
                "nd_id":     match["id"],
                "nd_title":  match.get("title", ""),
                "nd_artist": match.get("artist", ""),
            }
            if track["rank"] is not None:
                entry["rank"] = track["rank"]
            found.append(entry)
        else:
            missing.append(track)

        time.sleep(0.01)

    print(f"\n\n{'─'*62}")
    print(f"  Found in collection : {len(found):>4}")
    print(f"  Missing             : {len(missing):>4}")
    print(f"{'─'*62}\n")

    if args.dry_run:
        newly_found  = [t for t in found if t["title"] in existing_missing_titles]
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

    with open(found_file, "w") as f:
        json.dump(found, f, indent=2)
    print(f"✓ {found_file}  ({len(found)} tracks)")

    with open(missing_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["artist", "title", "album"] +
                                (["rank"] if args.rank_col else []))
        writer.writeheader()
        for t in missing:
            row = {"artist": t["artist"], "title": t["title"], "album": t["album"]}
            if args.rank_col:
                row["rank"] = t["rank"]
            writer.writerow(row)
    print(f"✓ {missing_file}  ({len(missing)} tracks to download)")


if __name__ == "__main__":
    main()