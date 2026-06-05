#!/usr/bin/env python3
"""
Rock 2000 — Phase 4: Create playlist in Navidrome
Reads found_tracks.json and creates (or updates) "The Rock 2000 (2025)"
in Navidrome via the Subsonic API, in countdown order.
"""

import json
import hashlib
import sys
from urllib import request, parse
from urllib.error import URLError

# ── CONFIG ────────────────────────────────────────────────────────────────────
NAVIDROME_URL = "http://100.92.200.19:4533/"
ND_USER       = "admin"
ND_PASSWORD   = "xGdADq3Vt9uUFX"
ND_CLIENT     = "rock2000playlist"
ND_VERSION    = "1.16.1"

PLAYLIST_NAME  = "The Rock 2000 (2025)"

# "desc" = #2000 first → #1 last (War Pigs finishes the countdown)
# "asc"  = #1 first (good for shuffle play)
PLAYLIST_ORDER = "desc"

# Subsonic API batch size for adding songs
BATCH_SIZE = 200
# ─────────────────────────────────────────────────────────────────────────────


def subsonic_token(password, salt):
    return hashlib.md5((password + salt).encode()).hexdigest()


def make_auth_base():
    salt = "rock2000"
    token = subsonic_token(ND_PASSWORD, salt)
    return (f"u={ND_USER}&t={token}&s={salt}"
            f"&v={ND_VERSION}&c={ND_CLIENT}&f=json")


def api_get(endpoint, params):
    base_url = NAVIDROME_URL.rstrip("/")
    auth = make_auth_base()
    query = parse.urlencode(params)
    url = f"{base_url}/rest/{endpoint}?{auth}&{query}"
    try:
        with request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read())
            response = payload.get("subsonic-response", {})
            if response.get("status") not in (None, "ok"):
                print(f"  [ERROR] API returned status={response.get('status')} for {endpoint}")
                return None
            return payload
    except URLError as e:
        print(f"  [ERROR] {e}")
        return None


def api_raw(url):
    try:
        with request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read())
            response = payload.get("subsonic-response", {})
            if response.get("status") not in (None, "ok"):
                print(f"  [ERROR] API returned status={response.get('status')}")
                return None
            return payload
    except URLError as e:
        print(f"  [ERROR] {e}")
        return None


def find_existing_playlist(name):
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


def create_playlist(name, first_song_id):
    resp = api_get("createPlaylist.view",
                   {"name": name, "songId": first_song_id})
    if resp is None:
        raise RuntimeError("Unable to create playlist")
    return (resp.get("subsonic-response", {})
               .get("playlist", {})
               .get("id"))


def clear_playlist(playlist_id):
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
    auth = make_auth_base()
    base_url = NAVIDROME_URL.rstrip("/")
    url = f"{base_url}/rest/updatePlaylist.view?{auth}&playlistId={playlist_id}&{indices}"
    if api_raw(url) is None:
        raise RuntimeError("Failed to clear playlist")
    print("done.")


def add_songs_in_batches(playlist_id, song_ids):
    total = len(song_ids)
    added = 0
    auth = make_auth_base()
    base_url = NAVIDROME_URL.rstrip("/")

    for start in range(0, total, BATCH_SIZE):
        batch = song_ids[start:start + BATCH_SIZE]
        songs_param = "&".join(f"songIdToAdd={sid}" for sid in batch)
        url = (f"{base_url}/rest/updatePlaylist.view?"
               f"{auth}&playlistId={playlist_id}&{songs_param}")

        # Retry up to 3 times on failure
        for attempt in range(3):
            result = api_raw(url)
            if result is not None:
                break
            print(f"\n  [WARN] Batch {start}-{start+len(batch)} failed, retrying ({attempt+1}/3)...")
        else:
            raise RuntimeError(f"Failed to add batch starting at index {start} after 3 attempts")

        added += len(batch)
        print(f"\r  Adding songs... {added}/{total}", end="", flush=True)

    print(f"\r  Adding songs... {added}/{total} ✓")


def main():
    try:
        with open("found_tracks.json") as f:
            found = json.load(f)
    except FileNotFoundError:
        print("❌  found_tracks.json not found. Run phases 1–3 first.")
        sys.exit(1)

    if not found:
        print("❌  No found tracks. Nothing to create a playlist from.")
        sys.exit(1)

    try:
        found.sort(key=lambda x: x["rank"], reverse=(PLAYLIST_ORDER == "desc"))
        song_ids = [t["nd_id"] for t in found]

        order_label = ("#2000→#1 countdown order"
                       if PLAYLIST_ORDER == "desc" else "#1→#2000")

        print(f"Creating playlist: '{PLAYLIST_NAME}'")
        print(f"  Order  : {order_label}")
        print(f"  Tracks : {len(song_ids)}/2000")
        print()

        existing_id = find_existing_playlist(PLAYLIST_NAME)

        if existing_id:
            print(f"  Existing playlist found (ID: {existing_id}) — updating...")
            clear_playlist(existing_id)
            add_songs_in_batches(existing_id, song_ids)
            playlist_id = existing_id
        else:
            print("  Creating new playlist...")
            playlist_id = create_playlist(PLAYLIST_NAME, song_ids[0])
            if not playlist_id:
                raise RuntimeError("Playlist was created without an id")
            print(f"  Playlist created (ID: {playlist_id})")
            # Remove the seed song then add the full ordered list
            clear_playlist(playlist_id)
            add_songs_in_batches(playlist_id, song_ids)

        coverage = (len(song_ids) / 2000) * 100
        print(f"\n✓ '{PLAYLIST_NAME}' ready in Navidrome")
        print(f"  Coverage : {len(song_ids)}/2000  ({coverage:.1f}%)")

        # Report gaps
        found_ranks = {t["rank"] for t in found}
        missing_ranks = sorted(r for r in range(1, 2001) if r not in found_ranks)
        if missing_ranks:
            print(f"  Missing  : {len(missing_ranks)} tracks not in playlist")
            sample = ", ".join(f"#{r}" for r in missing_ranks[:10])
            tail = ", ..." if len(missing_ranks) > 10 else ""
            print(f"  Ranks    : {sample}{tail}")
            print(f"  Details  : config/missing_tracks.csv")

    except RuntimeError as exc:
        print(f"❌  {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
