import re


# Common music metadata tags that appear in parentheses/brackets.
# These pollute search queries and title comparisons.
_TAGS_PATTERN = re.compile(
    r'\s*[\(\[]\s*(?:'
    r'album version\s*(?:explicit|clean)?|album ver\.?\s*(?:explicit|clean)?|'
    r'explicit version|explicit|clean version|clean|edit|'
    r'remaster(?:ed)?(?:\s+\d{4})?|'
    r'deluxe(?:\s+edition)?|bonus track|'
    r'radio edit|radio mix|radio version|'
    r'original mix|extended mix|'
    r'single version|live|acoustic|'
    r'from\s+"[^"]*"|from\s+the\s+\w+'
    r')\s*[\)\]]',
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Remove feat./ft. sections and common metadata tags from a title."""
    # Remove feat./ft. and everything after it (with or without parens)
    title = re.sub(r'\s*[\(\[]?feat\.?\s+[^\)\]]*[\)\]]?', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*[\(\[]?ft\.?\s+[^\)\]]*[\)\]]?', '', title, flags=re.IGNORECASE)
    # Remove common metadata tags in parentheses/brackets
    title = _TAGS_PATTERN.sub('', title)
    # Remove "with <artist>" suffixes (Spotify format)
    title = re.sub(r'\s*[\(\[]\s*with\s+[^\)\]]+[\)\]]', '', title, flags=re.IGNORECASE)
    return title.strip()


def clean_artist(artist: str) -> str:
    """Clean artist name for search queries — strip feat/ft suffixes.

    Only removes feat./ft. patterns. Does NOT strip "&" or "and" because
    those are often part of legitimate band names (Simon & Garfunkel,
    Earth Wind & Fire). The XML parser already splits multi-artist on ";".
    """
    artist = re.sub(r'\s*feat\.?\s+.*', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*ft\.?\s+.*', '', artist, flags=re.IGNORECASE)
    return artist.strip()


def normalise(s: str) -> str:
    s = s.lower()
    s = re.sub(r'\bthe\b|\ba\b|\ban\b', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def score_match(track: dict, result: dict) -> str:
    track_artist = track["primary_artist"].lower()
    track_title = clean_title(track["title"]).lower()
    track_album = track["album"].lower()

    result_artist = result["artists"][0]["name"].lower() if result.get("artists") else ""
    result_title = clean_title(result.get("name", "")).lower()
    result_album = (result.get("album") or {}).get("name", "").lower()

    artist_match = track_artist == result_artist
    title_match = track_title == result_title
    album_match = track_album == result_album

    if artist_match and title_match and album_match:
        return "exact"

    if artist_match and title_match:
        return "high"

    norm_artist_match = normalise(track_artist) == normalise(result_artist)
    norm_title_match = normalise(track_title) == normalise(result_title)

    if norm_artist_match and norm_title_match:
        return "high"

    # Partial word overlap on title
    track_words = set(normalise(track_title).split())
    result_words = set(normalise(result_title).split())
    if track_words and result_words:
        overlap = len(track_words & result_words) / max(len(track_words), len(result_words))
        if norm_artist_match and overlap >= 0.5:
            return "low"

    return "none"
