"""Reaper — Phase 3 core: trigger a Navidrome rescan, then re-search for
previously missing tracks and merge newly found ones in.

Extracted from 03_rescan_and_merge.py; matching now delegates to
core.matching (see that module's docstring re: the fallback-scoring drift
this consolidation fixes).
"""

import csv
import json
import sys
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


def _print_progress(current: int, total: int, track: dict) -> None:
    sys.stdout.write(
        f"\r  [{current:4d}/{total}] "
        f"{track['artist'][:30]:<30} — {track['title'][:35]:<35}"
    )
    sys.stdout.flush()


def trigger_scan(api_get, quiet: bool = False):
    if not quiet:
        print("► Triggering Navidrome library scan...")
    resp = api_get("startScan.view", {})
    status = resp.get("subsonic-response", {}).get("scanStatus", {})
    if not quiet:
        if status:
            print(f"  Scan started — currently indexed: {status.get('count', '?')} files")
        else:
            print("  [WARN] Could not confirm scan initialization.")


def wait_for_scan(api_get, quiet: bool = False, on_scan_tick=None):
    if not quiet:
        print("  Waiting for scan to complete", end="", flush=True)
    while True:
        time.sleep(5)
        resp = api_get("getScanStatus.view", {})
        if not resp:
            raise ScanTimeoutError("Unable to read Navidrome scan status")
        status = resp.get("subsonic-response", {}).get("scanStatus", {})
        if not status.get("scanning", True):
            if not quiet:
                print(f"\n  ✓ Scan complete — {status.get('count', '?')} files indexed.")
            return
        if on_scan_tick:
            on_scan_tick(status)
        if not quiet:
            print(".", end="", flush=True)


def run_rescan(
    playlist_name: str,
    config: dict,
    on_progress=None,
    on_scan_tick=None,
    quiet: bool = False,
) -> RescanResult | None:
    """Rescan Navidrome and re-match previously missing tracks for playlist_name.

    Returns None (no-op) if there's no missing_tracks.csv left to rescan —
    mirrors the original script's early "nothing to rescan" return.
    """
    on_progress = on_progress or _print_progress

    slug = slugify(playlist_name)
    playlist_dir = Path("playlists") / slug

    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    if not found_file.exists():
        raise NoFoundFileError(f"{found_file} not found. Run Phase 1 scan first.")

    if not missing_file.exists():
        if not quiet:
            print(f"🎉 No missing_tracks.csv found for '{playlist_name}' — nothing to rescan!")
        return None

    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    if not check_connection(api_get, quiet=quiet):
        # quiet=False would already have sys.exit(1)'d inside check_connection
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

    if not quiet:
        print(f"Playlist      : {playlist_name}")
        print(f"Current State : {len(found)} already matched, {len(missing)} targeted for rescan.\n")

    trigger_scan(api_get, quiet=quiet)
    wait_for_scan(api_get, quiet=quiet, on_scan_tick=on_scan_tick)
    if not quiet:
        print()

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

    if not quiet:
        print(f"\n\n{'─'*62}")
        print(f"  Newly matched from storage: {len(newly_found):>4}")
        print(f"  Still missing             : {len(still_missing):>4}")
        print(f"{'─'*62}\n")

    all_found = found + newly_found
    if has_rank_column:
        all_found = sorted(all_found, key=lambda x: x.get("rank", 9999))

    with open(found_file, "w") as f:
        json.dump(all_found, f, indent=2)
    if not quiet:
        print(f"✓ {found_file} updated ({len(all_found)} total tracks tracked)")

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

    if not quiet:
        print(f"✓ {missing_file} updated ({len(still_missing)} remaining items)")

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
