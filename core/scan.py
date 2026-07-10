"""Reaper — Phase 1 core: scan an Exportify CSV against Navidrome.

Extracted from 01_scan_navidrome.py so both the CLI script and the Flask
backend can drive it, with a progress callback replacing the old \\r stdout
write for the per-track loop.
"""

import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.config import slugify
from core.subsonic import make_api_get
from core.matching import search_navidrome


@dataclass
class ScanResult:
    playlist_name: str
    slug: str
    playlist_dir: Path
    found_file: Path
    missing_file: Path
    found: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    existing_found_uris: set = field(default_factory=set)
    existing_missing_titles: set = field(default_factory=set)
    dry_run: bool = False


def _print_progress(current: int, total: int, track: dict) -> None:
    sys.stdout.write(
        f"\r  [{current:4d}/{total}] "
        f"{track['artist'][:30]:<30} — {track['title'][:35]:<35}"
    )
    sys.stdout.flush()


def read_csv(csv_path: Path, rank_col: str | None) -> list[dict]:
    """Read Exportify CSV and return list of track dicts."""
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    tracks = []
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


def load_existing(found_file: Path, missing_file: Path) -> tuple[set, set]:
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


def run_scan(
    csv_path: Path,
    playlist_name: str,
    config: dict,
    rank_col: str | None = None,
    dry_run: bool = False,
    on_progress=None,
    quiet: bool = False,
) -> ScanResult:
    """Scan csv_path against Navidrome, writing found/missing files unless dry_run.

    on_progress(current, total, track) fires once per CSV row. quiet=True
    suppresses the CLI-style print()s (used by the Flask backend so its own
    server log isn't flooded); the terminal script keeps quiet=False so its
    output is unchanged.
    """
    on_progress = on_progress or _print_progress

    slug = slugify(playlist_name)
    playlist_dir = Path("playlists") / slug
    playlist_dir.mkdir(parents=True, exist_ok=True)

    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    if not quiet:
        if dry_run:
            print("🔍 DRY RUN — no files will be written\n")
        print(f"Playlist : {playlist_name}")
        print(f"Slug     : {slug}")
        print(f"Output   : playlists/{slug}/")
        print(f"CSV      : {csv_path}")
        if rank_col:
            print(f"Ranking  : by column '{rank_col}'")
        else:
            print(f"Ranking  : none (CSV order preserved)")
        print()
        print(f"Reading {csv_path}...")

    tracks = read_csv(csv_path, rank_col)

    if not quiet:
        print(f"Loaded {len(tracks)} tracks. Scanning Navidrome...\n")

    existing_found_uris, existing_missing_titles = load_existing(found_file, missing_file)

    found, missing = [], []

    for i, track in enumerate(tracks, 1):
        on_progress(i, len(tracks), track)

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

    if not quiet:
        print(f"\n\n{'─'*62}")
        print(f"  Found in collection : {len(found):>4}")
        print(f"  Missing             : {len(missing):>4}")
        print(f"{'─'*62}\n")

    result = ScanResult(
        playlist_name=playlist_name,
        slug=slug,
        playlist_dir=playlist_dir,
        found_file=found_file,
        missing_file=missing_file,
        found=found,
        missing=missing,
        existing_found_uris=existing_found_uris,
        existing_missing_titles=existing_missing_titles,
        dry_run=dry_run,
    )

    if dry_run:
        if not quiet:
            _print_dry_run_diff(result)
        return result

    with open(found_file, "w") as f:
        json.dump(found, f, indent=2)
    if not quiet:
        print(f"✓ {found_file}  ({len(found)} tracks)")

    with open(missing_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["artist", "title", "album"] +
                                (["rank"] if rank_col else []))
        writer.writeheader()
        for t in missing:
            row = {"artist": t["artist"], "title": t["title"], "album": t["album"]}
            if rank_col:
                row["rank"] = t["rank"]
            writer.writerow(row)
    if not quiet:
        print(f"✓ {missing_file}  ({len(missing)} tracks to download)")

        if missing:
            print(f"\nNext steps:")
            print(f"  ./02_download_missing.sh --playlist \"{playlist_name}\"")
        else:
            print(f"\nAll tracks found — skip to Phase 4:")
            print(f"  python3 04_create_playlist.py --playlist \"{playlist_name}\"")

    return result


def _print_dry_run_diff(result: ScanResult) -> None:
    newly_found = [t for t in result.found if t["title"] in result.existing_missing_titles]
    newly_missing = [t for t in result.missing if t["uri"] in result.existing_found_uris]

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
