"""Reaper — Phase 4 core: create or update the Navidrome playlist from
found_tracks.json, in countdown (or ascending) order.

Extracted from 04_create_playlist.py.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.config import slugify
from core.subsonic import make_api, check_connection

BATCH_SIZE = 200


class NoFoundTracksError(Exception):
    pass


class EmptyFoundTracksError(Exception):
    pass


class NavidromeUnreachableError(Exception):
    pass


@dataclass
class PlaylistResult:
    playlist_id: str
    display_name: str
    created: bool  # True if newly created, False if an existing one was updated
    track_count: int
    max_rank: int
    coverage_pct: float
    missing_ranks: list = field(default_factory=list)


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


def create_new_playlist(api_get, name: str, first_song_id: str) -> str:
    resp = api_get("createPlaylist.view", {"name": name, "songId": first_song_id})
    if resp is None:
        raise RuntimeError("Unable to create playlist")
    pl_id = (resp.get("subsonic-response", {})
                 .get("playlist", {})
                 .get("id"))
    if not pl_id:
        raise RuntimeError("Playlist created but no ID returned")
    return pl_id


def set_playlist_public(api_raw, base_url: str, auth_str: str, playlist_id: str, quiet: bool = False) -> None:
    """Make the playlist visible to all Navidrome users, not just the owner.
    Subsonic's updatePlaylist supports `public` directly — Navidrome defaults
    new playlists to private otherwise, requiring a manual toggle per playlist."""
    url = f"{base_url}/rest/updatePlaylist.view?{auth_str}&playlistId={playlist_id}&public=true"
    if api_raw(url) is None:
        raise RuntimeError("Failed to mark playlist public")
    if not quiet:
        print("  Marked playlist public.")


def clear_playlist(api_get, api_raw, base_url: str, auth_str: str, playlist_id: str, quiet: bool = False):
    """Remove all songs from an existing playlist."""
    resp = api_get("getPlaylist.view", {"id": playlist_id})
    if resp is None:
        raise RuntimeError("Unable to read playlist contents")
    entries = (resp.get("subsonic-response", {})
                   .get("playlist", {})
                   .get("entry", []))
    if not entries:
        return
    if not quiet:
        print(f"  Clearing {len(entries)} existing songs...", end=" ", flush=True)
    indices = "&".join(f"songIndexToRemove={i}" for i in range(len(entries)))
    url = f"{base_url}/rest/updatePlaylist.view?{auth_str}&playlistId={playlist_id}&{indices}"
    if api_raw(url) is None:
        raise RuntimeError("Failed to clear playlist")
    if not quiet:
        print("done.")


def add_songs_in_batches(api_raw, base_url: str, auth_str: str, playlist_id: str, song_ids: list,
                          quiet: bool = False, on_progress=None):
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
            if not quiet:
                print(f"\n  [WARN] Batch {start}–{start+len(batch)} failed, retrying ({attempt+1}/3)...")
        else:
            raise RuntimeError(f"Failed to add batch starting at index {start} after 3 attempts")

        added += len(batch)
        if on_progress:
            on_progress(added, total)
        if not quiet:
            print(f"\r  Adding songs... {added}/{total}", end="", flush=True)

    if not quiet:
        print(f"\r  Adding songs... {added}/{total} ✓")


def create_or_update_playlist(
    playlist_name: str,
    config: dict,
    title: str | None = None,
    quiet: bool = False,
    on_progress=None,
) -> PlaylistResult:
    slug = slugify(playlist_name)
    playlist_dir = Path("playlists") / slug
    found_file = playlist_dir / "found_tracks.json"

    if not found_file.exists():
        raise NoFoundTracksError(f"{found_file} not found. Run phases 1–3 first.")

    api_get, api_raw, base_url, auth_str = make_api(config)

    if not check_connection(api_get, quiet=quiet):
        raise NavidromeUnreachableError("Cannot reach Navidrome — check config.yml URL and credentials.")

    with open(found_file) as f:
        found = json.load(f)

    if not found:
        raise EmptyFoundTracksError("No found tracks in found_tracks.json. Nothing to create a playlist from.")

    playlist_order = config.get("playlist_order", "desc")
    playlist_display_name = title or playlist_name

    found.sort(key=lambda x: x.get("rank", 9999), reverse=(playlist_order == "desc"))
    song_ids = [t["nd_id"] for t in found]

    if not quiet:
        order_label = ("highest rank → #1 countdown order"
                       if playlist_order == "desc" else "#1 → highest rank")
        print(f"Playlist : '{playlist_display_name}'")
        print(f"Order    : {order_label}")
        print(f"Tracks   : {len(song_ids)}")
        print()

    existing_id = find_existing_playlist(api_get, playlist_display_name)
    created = existing_id is None

    if existing_id:
        if not quiet:
            print(f"  Existing playlist found (ID: {existing_id}) — updating...")
        clear_playlist(api_get, api_raw, base_url, auth_str, existing_id, quiet=quiet)
        add_songs_in_batches(api_raw, base_url, auth_str, existing_id, song_ids, quiet=quiet, on_progress=on_progress)
        playlist_id = existing_id
    else:
        if not quiet:
            print("  No existing playlist found — creating...")
        playlist_id = create_new_playlist(api_get, playlist_display_name, song_ids[0])
        if not quiet:
            print(f"  Playlist created (ID: {playlist_id})")
        clear_playlist(api_get, api_raw, base_url, auth_str, playlist_id, quiet=quiet)
        add_songs_in_batches(api_raw, base_url, auth_str, playlist_id, song_ids, quiet=quiet, on_progress=on_progress)

    set_playlist_public(api_raw, base_url, auth_str, playlist_id, quiet=quiet)

    found_ranks = {t.get("rank") for t in found if t.get("rank") is not None}
    max_rank = max(found_ranks) if found_ranks else len(found)
    expected = set(range(1, max_rank + 1))
    missing_ranks = sorted(expected - found_ranks)

    coverage = (len(song_ids) / max_rank) * 100 if max_rank else 100.0

    if not quiet:
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

    return PlaylistResult(
        playlist_id=playlist_id,
        display_name=playlist_display_name,
        created=created,
        track_count=len(song_ids),
        max_rank=max_rank,
        coverage_pct=coverage,
        missing_ranks=missing_ranks,
    )
