import re
import unicodedata


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
    """Clean artist name for search queries - strip feat/ft suffixes.

    Only removes feat./ft. patterns. Does NOT strip "&" or "and" because
    those are often part of legitimate band names (Simon & Garfunkel,
    Earth Wind & Fire). The XML parser already splits multi-artist on ";".
    """
    artist = re.sub(r'\s*feat\.?\s+.*', '', artist, flags=re.IGNORECASE)
    artist = re.sub(r'\s*ft\.?\s+.*', '', artist, flags=re.IGNORECASE)
    return artist.strip()


def normalise(s: str) -> str:
    # Strip diacritics first (e.g. JAŸ-Z → JAY-Z, café → cafe)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'\bthe\b|\ba\b|\ban\b', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# Registered and copyright marks, which sources spell differently ("BNYX(R)" vs "BNYX®").
_MARKS_RE = re.compile(r"\(R\)|\(C\)|[®™©]")
_ARTIST_SPLIT_RE = re.compile(r"\s*&\s*|\s*;\s*|\s*,\s*")
_DASH_SUFFIX_RE = re.compile(r"\s+-\s+([^-]+)$")
# A trailing "(Edited)", "- Explicit", "[Clean]", "- Remastered 2009" or "(Radio Edit)" is the same
# track as the bare title. Applied after clean_title inside title_key.
_TITLE_SUFFIX_RE = re.compile(
    r"\s*(?:[\(\[]|[-])?\s*\b(?:edited|explicit|clean|remaster(?:ed)?(?:\s+\d{4})?|radio edit)\b\s*[\)\]]?\s*$",
    re.IGNORECASE,
)


def primary_artist(artist: str) -> str:
    """First artist of a multi-artist field: feat./ft. dropped, (R)/(C)/trademark marks removed,
    then the text before " & ", ";" or ","."""
    name = _MARKS_RE.sub("", clean_artist(artist))
    return _ARTIST_SPLIT_RE.split(name)[0].strip()


def title_key(title: str) -> str:
    """Normalised title for matching. A trailing " - Single Version" becomes "(Single Version)",
    then clean_title and the trailing edit words are removed, then normalise."""
    text = _DASH_SUFFIX_RE.sub(r" (\1)", title or "")
    return normalise(_TITLE_SUFFIX_RE.sub("", clean_title(text)))


def content_key(artist: str, title: str) -> str:
    """Normalised "primary artist:title key" pair, content only (no fetch-order index)."""
    return f"{normalise(primary_artist(artist))}:{title_key(title)}"


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
