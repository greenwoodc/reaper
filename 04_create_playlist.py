#!/usr/bin/env python3
"""
Reaper — Phase 4: Create playlist in Navidrome
Reads found_tracks.json and creates (or updates) the target playlist
in Navidrome via the Subsonic API, in countdown order.

Usage:
    python3 04_create_playlist.py --playlist "The Rock 2000"
"""

import argparse
import json
import hashlib
import re
import sys
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
    "navidrome_url":      "http://localhost:4533/",
    "navidrome_user":     "admin",
    "navidrome_password": "",
    "navidrome_client":   "reaper",
    "navidrome_version":  "1.16.1",
    # "desc" = highest rank first → #1 last (countdown feel)
    # "asc"  = #1 first (good for shuffle play)
    "playlist_order":     "desc",
}

# Subsonic API batch size for adding songs
BATCH_SIZE = 200
# ─────────────────────────────────────────────────────────────────────────────


def load_config() -> dict:
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
    name = re.sub(r'[^\w\s-]', '', name.lower())
    name = re.sub(r'[\s_-]+', '_', name)
    return name.strip('_')


def subsonic_token(password: str, salt: str) -> str:
    return hashlib.md5((password + salt).encode()).hexdigest()


def make_api(config: dict):
    """Return api_get and api_raw functions bound to config."""
    base_url = config["navidrome_url"].rstrip("/")
    salt = "reaper"
    token = subsonic_token(config["navidrome_password"], salt)
    auth_params = {
        "u": config["navidrome_user"],
        "t": token,
        "s": salt,
        "v": config["navidrome_version"],
        "c": config["navidrome_client"],
        "f": "json",
    }
    auth_str = parse.urlencode(auth_params)

    def _parse(resp_bytes: bytes, endpoint: str) -> Optional[dict]:
        payload = json.loads(resp_bytes)
        response = payload.get("subsonic-response", {})
        if response.get("status") not in (None, "ok"):
            print(f"  [ERROR] API returned status={response.get('status')} for {endpoint}")
            return None
        return payload

    def api_get(endpoint: str, params: dict) -> Optional[dict]:
        query = parse.urlencode(params)
        url = f"{base_url}/rest/{endpoint}?{auth_str}&{query}"
        try:
            with request.urlopen(url, timeout=15) as resp:
                return _parse(resp.read(), endpoint)
        except URLError as e:
            print(f"  [ERROR] {e}")
            return None

    def api_raw(url: str) -> Optional[dict]:
        try:
            with request.urlopen(url, timeout=15) as resp:
                return _parse(resp.read(), url)
        except URLError as e:
            print(f"  [ERROR] {e}")
            return None

    return api_get, api_raw, base_url, auth_str


def check_connection(api_get):
    resp = api_get("ping.view", {})
    status = resp.get("subsonic-response", {}).get("status") if resp else None
    if status != "ok":
        print("❌  Cannot reach Navidrome — check config.yml URL and credentials.")
        sys.exit(1)
    print("✓ Navidrome connection verified.")


def find_existing_playlist(api_get, name: str) -> Optional[str]:
    resp = api_get("getPlaylists.view", {})
    if resp is None:
        raise RuntimeError("Unable to query existing playlists")
    playlists = (resp.get("subsonic-response", {})
                     .get("playlists", {})
                     .get("playlist", []))
    for pl in playlists:
        if pl.get("name") == name:
            return pl.get("id")
    return None


def create_playlist(api_get, name: str, first_song_id: str) -> str:
    resp = api_get("createPlaylist.view", {"name": name, "songId": first_song_id})
    if resp is None:
        raise RuntimeError("Unable to create playlist")
    pl_id = (resp.get("subsonic-response", {})
                 .get("playlist", {})
                 .get("id"))
    if not pl_id:
        raise RuntimeError("Playlist created but no ID returned")
    return pl_id


def clear_playlist(api_get, api_raw, base_url: str, auth_str: str, playlist_id: str):
    """Remove all songs from an existing playlist."""
    resp = api_get("getPlaylist.view", {"id": playlist_id})
    if resp is None:
        raise RuntimeError("Unable to read playlist contents")
    entries = (resp.get("subsonic-response", {})
                   .get("playlist", {})
                   .get("entry", []))
    if not entries:
        return
    print(f"  Clearing {len(entries)} existing songs...", end=" ", flush=True)
    indices = "&".join(f"songIndexToRemove={i}" for i in range(len(entries)))
    url = f"{base_url}/rest/updatePlaylist.view?{auth_str}&playlistId={playlist_id}&{indices}"
    if api_raw(url) is None:
        raise RuntimeError("Failed to clear playlist")
    print("done.")


def add_songs_in_batches(api_raw, base_url: str, auth_str: str, playlist_id: str, song_ids: list):
    total = len(song_ids)
    added = 0

    for start in range(0, total, BATCH_SIZE):
        batch = song_ids[start:start + BATCH_SIZE]
        songs_param = "&".join(f"songIdToAdd={sid}" for sid in batch)
        url = (f"{base_url}/rest/updatePlaylist.view?"
               f"{auth_str}&playlistId={playlist_id}&{songs_param}")

        for attempt in range(3):
            result = api_raw(url)
            if result is not None:
                break
            print(f"\n  [WARN] Batch {start}–{start+len(batch)} failed, retrying ({attempt+1}/3)...")
        else:
            raise RuntimeError(f"Failed to add batch starting at index {start} after 3 attempts")

        added += len(batch)
        print(f"\r  Adding songs... {added}/{total}", end="", flush=True)

    print(f"\r  Adding songs... {added}/{total} ✓")


def main():
    parser = argparse.ArgumentParser(description="Reaper Phase 4 — Create/Update Navidrome Playlist")
    parser.add_argument("--playlist", required=True, help="Playlist name (must match Phase 1–3 slug)")
    parser.add_argument("--title", default=None,
                        help="Override the Navidrome playlist display name (default: same as --playlist)")
    args = parser.parse_args()

    slug = slugify(args.playlist)
    playlist_dir = Path("playlists") / slug
    found_file = playlist_dir / "found_tracks.json"

    if not found_file.exists():
        print(f"❌  {found_file} not found. Run phases 1–3 first.")
        sys.exit(1)

    config = load_config()
    api_get, api_raw, base_url, auth_str = make_api(config)

    check_connection(api_get)

    with open(found_file) as f:
        found = json.load(f)

    if not found:
        print("❌  No found tracks in found_tracks.json. Nothing to create a playlist from.")
        sys.exit(1)

    playlist_order = config.get("playlist_order", "desc")
    playlist_display_name = args.title or args.playlist

    found.sort(key=lambda x: x.get("rank", 9999), reverse=(playlist_order == "desc"))
    song_ids = [t["nd_id"] for t in found]

    order_label = ("highest rank → #1 countdown order"
                   if playlist_order == "desc" else "#1 → highest rank")

    print(f"Playlist : '{playlist_display_name}'")
    print(f"Order    : {order_label}")
    print(f"Tracks   : {len(song_ids)}")
    print()

    existing_id = find_existing_playlist(api_get, playlist_display_name)

    if existing_id:
        print(f"  Existing playlist found (ID: {existing_id}) — updating...")
        clear_playlist(api_get, api_raw, base_url, auth_str, existing_id)
        add_songs_in_batches(api_raw, base_url, auth_str, existing_id, song_ids)
        playlist_id = existing_id
    else:
        print("  No existing playlist found — creating...")
        playlist_id = create_playlist(api_get, playlist_display_name, song_ids[0])
        print(f"  Playlist created (ID: {playlist_id})")
        # Clear the seed song then populate in order
        clear_playlist(api_get, api_raw, base_url, auth_str, playlist_id)
        add_songs_in_batches(api_raw, base_url, auth_str, playlist_id, song_ids)

    # Coverage report (only meaningful if ranks are 1-based sequential e.g. Rock 2000)
    found_ranks = {t.get("rank") for t in found if t.get("rank") is not None}
    max_rank = max(found_ranks) if found_ranks else len(found)
    expected = set(range(1, max_rank + 1))
    missing_ranks = sorted(expected - found_ranks)

    coverage = (len(song_ids) / max_rank) * 100 if max_rank else 100.0

    print(f"\n✓ '{playlist_display_name}' ready in Navidrome")
    print(f"  Coverage : {len(song_ids)}/{max_rank}  ({coverage:.1f}%)")

    if missing_ranks:
        print(f"  Missing  : {len(missing_ranks)} ranks not in playlist")
        sample = ", ".join(f"#{r}" for r in missing_ranks[:10])
        tail = ", ..." if len(missing_ranks) > 10 else ""
        print(f"  Ranks    : {sample}{tail}")
        missing_csv = playlist_dir / "missing_tracks.csv"
        if missing_csv.exists():
            print(f"  Details  : {missing_csv}")


if __name__ == "__main__":
    main()