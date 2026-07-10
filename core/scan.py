"""Reaper — scan an Exportify CSV against Navidrome.

Used only by the webapp backend (backend/routes.py), which drives it with an
on_progress callback and consumes the returned ScanResult directly — there's
no CLI layer anymore, so this module does no printing of its own.
"""

import csv
import json
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
    on_progress=None,
) -> ScanResult:
    """Scan csv_path against Navidrome, writing found/missing files.

    on_progress(current, total, track) fires once per CSV row.
    """
    on_progress = on_progress or (lambda *_args: None)

    slug = slugify(playlist_name)
    playlist_dir = Path("playlists") / slug
    playlist_dir.mkdir(parents=True, exist_ok=True)

    found_file = playlist_dir / "found_tracks.json"
    missing_file = playlist_dir / "missing_tracks.csv"

    threshold = config["match_threshold"]
    api_get = make_api_get(config)

    tracks = read_csv(csv_path, rank_col)
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
    )

    with open(found_file, "w") as f:
        json.dump(found, f, indent=2)

    with open(missing_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["artist", "title", "album"] +
                                (["rank"] if rank_col else []))
        writer.writeheader()
        for t in missing:
            row = {"artist": t["artist"], "title": t["title"], "album": t["album"]}
            if rank_col:
                row["rank"] = t["rank"]
            writer.writerow(row)

    return result
