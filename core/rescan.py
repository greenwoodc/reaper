"""Reaper — trigger a Navidrome rescan, then re-search for previously
missing tracks and merge newly found ones in.

Used only by the webapp backend — see core/scan.py's docstring for why
there's no printing here.
"""

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.config import slugify
from core.subsonic import make_api_get, check_connection
from core.matching import search_navidrome


class NoFoundFileError(Exception):
    pass


class NothingToRescanError(Exception):
    pass


class NavidromeUnreachableError(Exception):
    pass


class ScanTimeoutError(Exception):
    pass


@dataclass
class RescanResult:
    playlist_name: str
    slug: str
    playlist_dir: Path
    found_file: Path
    missing_file: Path
    newly_found: list = field(default_factory=list)
    still_missing: list = field(default_factory=list)
    all_found: list = field(default_factory=list)


def trigger_scan(api_get) -> None:
    api_get("startScan.view", {})


def wait_for_scan(api_get, on_scan_tick=None) -> None:
    while True:
        time.sleep(5)
        resp = api_get("getScanStatus.view", {})
        if not resp:
            raise ScanTimeoutError("Unable to read Navidrome scan status")
        status = resp.get("subsonic-response", {}).get("scanStatus", {})
        if not status.get("scanning", True):
            return
        if on_scan_tick:
            on_scan_tick(status)


def run_rescan(
    playlist_name: str,
    config: dict,
    on_progress=None,
    on_scan_tick=None,
) -> RescanResult | None:
    """Rescan Navidrome and re-match previously missing tracks for playlist_name.

    Returns None (no-op) if there's no missing_tracks.csv left to rescan.
    """
    on_progress = on_progress or (lambda *_args: None)

    slug = slugify(playlist_name)
    playlist_dir = Path("playlists") / slug

    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    if not found_file.exists():
        raise NoFoundFileError(f"{found_file} not found. Run a scan first.")

    if not missing_file.exists():
        return None

    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    if not check_connection(api_get):
        raise NavidromeUnreachableError("Cannot reach Navidrome — check config.yml URL and credentials.")

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

    trigger_scan(api_get)
    wait_for_scan(api_get, on_scan_tick=on_scan_tick)

    newly_found, still_missing = [], []

    for i, track in enumerate(missing, 1):
        on_progress(i, len(missing), track)

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

    all_found = found + newly_found
    if has_rank_column:
        all_found = sorted(all_found, key=lambda x: x.get("rank", 9999))

    with open(found_file, "w") as f:
        json.dump(all_found, f, indent=2)

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

    return RescanResult(
        playlist_name=playlist_name,
        slug=slug,
        playlist_dir=playlist_dir,
        found_file=found_file,
        missing_file=missing_file,
        newly_found=newly_found,
        still_missing=still_missing,
        all_found=all_found,
    )
