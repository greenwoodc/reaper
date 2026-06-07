def search_navidrome(api_get, artists: list[str], title: str, threshold: float) -> dict | None:
    best_score, best_match = 0.0, None

    # Handle multi-artists cleanly
    cleaned_artists = []
    for artist in artists:
        cleaned_artists.extend([a.strip() for a in artist.split(';') if a.strip()])

    primary_artist = cleaned_artists[0]
    primary_artist_no_punct = re.sub(r'[^\w\s]', '', primary_artist)
    clean_t = normalise(title)
    
    is_stubborn = clean_t in ["orange crush", "stand", "tribute", "home again", "all along the watchtower"]

    def score_song(song: dict) -> float:
        s_title = song.get("title", "")
        s_artist = song.get("artist", "")
        
        # Clean normalization checks
        norm_s_title = normalise(s_title)
        norm_s_artist = normalise(s_artist)

        t_score = fuzzy(clean_t, norm_s_title)
        a_score = max(fuzzy(normalise(artist), norm_s_artist) for artist in cleaned_artists)

        # Compilation Hack: If artist is "Various Artists", check if the expected artist is in the title string
        if norm_s_artist == "various artists" and normalise(primary_artist) in norm_s_title:
            a_score = 1.0
            # Re-score title based on parsing out the artist delimiter if present (e.g. "Tribute - Tenacious D")
            if " - " in norm_s_title:
                title_part = normalise(s_title.split(" - ")[0])
                t_score = max(t_score, fuzzy(clean_t, title_part))

        # Title Anchor Boost: If track name matches flawlessly, lower artist penalty slightly for group variants (e.g. Shihad/Pacifier)
        if norm_s_title == clean_t and a_score >= 0.70:
            a_score = max(a_score, 0.90)

        return t_score * 0.60 + a_score * 0.40

    # Build expanded query tree to address R.E.M. vs REM and truncation issues
    queries = [
        f"{primary_artist} {clean_t}",          # 1. Raw layout: "R.E.M. orange crush"
        f"{primary_artist_no_punct} {clean_t}", # 2. Punctuation free: "REM orange crush"
        title,                                  # 3. Exact CSV title
        clean_t,                                # 4. Normalised track title
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
            s = score_song(song)
            if is_stubborn:
                print(f"     ↳ Match Found: '{song.get('artist')} — {song.get('title')}' [Score: {s:.2f}]")
            if s > best_score:
                best_score, best_match = s, song

    # Final inclusive evaluation check (fixing the >= exact match edge case)
    if best_score >= threshold:
        if is_stubborn:
            print(f"  ✅ SUCCESS: Matched with score {best_score:.2f}\n")
        return best_match

    # Deep Fallback Pass — Try both raw and punctuation stripped configurations
    if is_stubborn:
        print(f"  ⚠️  Low scores. Attempting absolute fallback search for artist indexes.")

    for fallback_query in list(dict.fromkeys([primary_artist, primary_artist_no_punct])):
        resp = api_get("search3.view", {
            "query": fallback_query, 
            "songCount": 150,
            "artistCount": 0,
            "albumCount": 0
        })
        for song in resp.get("subsonic-response", {}).get("searchResult3", {}).get("song", []):
            s = score_song(song)
            if s > best_score:
                best_score, best_match = s, song

    if is_stubborn:
        if best_score >= threshold:
            print(f"  ✅ SUCCESS IN FALLBACK: Matched '{best_match.get('artist')} — {best_match.get('title')}' ({best_score:.2f})\n")
        else:
            print(f"  ❌ FAILURE: Best found was '{best_match.get('artist') if best_match else 'None'} — {best_match.get('title') if best_match else 'None'}' with score {best_score:.2f} (Needs {threshold})\n")

    return best_match if best_score >= threshold else None