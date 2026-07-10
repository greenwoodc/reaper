"""Shared fuzzy-matching engine used by both scan and rescan. Originally
duplicated verbatim between the two (the two copies had already silently
drifted on tie-breaking/fallback semantics) — this is the single source of
truth now, using the scan step's original behavior.
"""

import re
import unicodedata
from difflib import SequenceMatcher


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
    s = re.sub(r'[^\w\s-]', ' ', s)  # Keep inner hyphens
    s = re.sub(r'\s+', ' ', s)

    # 4. Strip unicode accents
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

    # Boost if primary artist is contained within a featured-artist tag
    # e.g. "Rihanna" contained in "Rihanna feat. Calvin Harris"
    if norm_primary in norm_s_artist and len(norm_primary) > 3:
        a_score = max(a_score, 0.90)

    if norm_s_artist == "various artists" and norm_primary in norm_s_title:
        a_score = 1.0
        if " - " in norm_s_title:
            title_part = normalise(s_title.split(" - ")[0])
            t_score = max(t_score, fuzzy(clean_t, title_part))

    if norm_s_title == clean_t and a_score >= 0.70:
        a_score = max(a_score, 0.90)

    return t_score * 0.60 + a_score * 0.40


def search_navidrome(api_get, artists: list, title: str, threshold: float) -> dict | None:
    """Search Navidrome for the best-matching song, with a broad fallback pass."""
    best_score, best_match = 0.0, None

    cleaned_artists = []
    for artist in artists:
        cleaned_artists.extend([a.strip() for a in artist.split(';') if a.strip()])

    primary_artist = cleaned_artists[0]
    primary_artist_no_punct = re.sub(r'[^\w\s]', '', primary_artist)
    clean_t = normalise(title)

    # If parsing Shihad, automatically stack query variations for the API
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
            if s >= best_score:
                best_score, best_match = s, song

    if best_score >= threshold:
        return best_match

    # Deep Fallback Pass — continues accumulating onto the same best_score/best_match
    fallback_targets = [primary_artist, primary_artist_no_punct]
    if normalise(primary_artist) in ["shihad", "pacifier"]:
        fallback_targets.extend(["Shihad", "Pacifier"])

    for fallback_query in list(dict.fromkeys(fallback_targets)):
        resp = api_get("search3.view", {
            "query": fallback_query,
            "songCount": 600,
            "artistCount": 0,
            "albumCount": 0
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song, clean_t, cleaned_artists, primary_artist)
            if s >= best_score:
                best_score, best_match = s, song

    return best_match if best_score >= threshold else None
