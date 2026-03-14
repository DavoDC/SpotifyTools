# Spotify Import Tool Assessment

**Use case:** Build a Spotify playlist from an offline music library exported as CSV.
CSV format: `Artist` (semicolon-separated e.g. `Eminem;50 Cent`), `Title`, `Album`, `Year`.

---

## Tool-by-Tool Breakdown

### 1. `buunguyen/spotify-importer`

| Property | Detail |
|---|---|
| Language | JavaScript (Node.js 14+) |
| Last commit | July 9, 2020 |
| Commits | 7 |
| Input format | CSV: `track_name, artist, playlists (pipe-separated), spotify_uri` |
| Failure handling | Writes unmatched tracks to `.failed.csv` for manual re-run |
| Windows setup | `npm install` + set Spotify credentials, straightforward |

**Assessment:**

- The CSV schema is wrong for this use case. Their CSV has a `playlists` column (pipe-separated playlist names) and a `spotify_uri` column. The input CSV would need to be reformatted to match.
- The `generate-csv` command scans a local directory to build the CSV; it does not accept an external CSV directly — you would use it in reverse (supply your own CSV as the import input, skipping the generate step).
- No multi-artist handling in the artist field. A row like `Eminem;50 Cent` would be passed raw to the Spotify search API, which would likely fail or produce poor results.
- Abandoned since July 2020. No maintenance.
- **Verdict: Poor fit.** Wrong column schema, no multi-artist handling, dead project.

---

### 2. `FutureSharks/spotify-m3u-import`

| Property | Detail |
|---|---|
| Language | Python |
| Last commit | November 6, 2025 (actively maintained) |
| Commits | ~4 (small but recent) |
| Input format | M3U playlist file (paths to local MP3s); reads ID3 tags or parses filename |
| Failure handling | Silent exclusion — unmatched tracks are counted but not written anywhere |
| Windows setup | `pip install -r requirements.txt` + env vars |

**Assessment:**

- Input is M3U, not CSV. The workflow would require either: (a) generating an M3U pointing at your actual MP3 files, or (b) a rewrite.
- Search query is built as `"artist title"` — only two fields, no album. Artist comes from the ID3 `TPE1` tag.
- ID3 `TPE1` tags in this library are already in `Artist;FeatArtist` format (the custom AudioManager format). The script takes `TPE1` as a single string and passes it straight to Spotify search. A query like `"Eminem;50 Cent Patiently Waiting"` would likely fail.
- No failure output file — silently drops unmatched tracks with no recovery path.
- Most recently maintained of the four (Nov 2025), and actively improved (switched from eyed3 to mutagen).
- **Verdict: Closest to working if you have M3U files.** But the semicolon artist format and silent failure are real problems.

---

### 3. `smtchahal/spotify-import`

| Property | Detail |
|---|---|
| Language | Python |
| Last commit | June 17, 2023 |
| Commits | 5 |
| Input format | CSV with columns: `artist, album, title` (or `.txt`) |
| Failure handling | Writes failed track queries to `failed.txt` |
| Windows setup | `pip install -r requirements.txt` + `.env` file for credentials |

**Assessment:**

- **CSV schema is the closest match** to the AudioManager export. The sample CSV (`songs.csv.sample`) uses exactly `artist, album, title` — three of the four columns in the AudioManager export (Year is the only extra, and it is ignored harmlessly).
- Search query is built as `"artist - title - album"` (or `"artist - title"` if no album), then cleaned by stripping "feat.", "ft.", remix variants, and " &".
- The `replace_bad_words()` cleanup is useful — it strips "feat." from titles. However, the semicolon in `Eminem;50 Cent` is not handled. The whole string goes verbatim into the search query, e.g. `"Eminem;50 Cent - Patiently Waiting - 8 Mile"`. Spotify search would likely match on `Eminem` and ignore the rest, which may work accidentally in many cases — but it's unreliable.
- Uses `SequenceMatcher` to rank search results by similarity to the original query, which is smarter than just taking the top result.
- Writes failed queries to `failed.txt` — recovery path exists.
- Has tests (last commit message: "Add some tests").
- Import destination is either `library` (Liked Songs) or a new `playlist`.
- **Verdict: Best fit for direct use or light forking.**

---

### 4. `arg274/SpotiM3U`

| Property | Detail |
|---|---|
| Language | Python |
| Last commit | September 24, 2021 |
| Commits | 5 |
| Input format | M3U playlist |
| Failure handling | Not documented |
| Windows setup | Unclear — README only mentions "requires a Spotify API token" |

**Assessment:**

- Input is M3U, not CSV.
- Last commit message was literally "Fixed breaking Spotify API changes, search is much worse now" — the developer themselves describe the search quality as degraded.
- Sparse documentation and no setup guide.
- **Verdict: Weakest option. Avoid.**

---

## Summary Comparison

| Tool | Language | Last commit | Input | CSV schema match | Multi-artist support | Failure file |
|---|---|---|---|---|---|---|
| buunguyen/spotify-importer | JS/Node | Jul 2020 | CSV (wrong schema) | Poor | No | Yes (.failed.csv) |
| FutureSharks/spotify-m3u-import | Python | **Nov 2025** | M3U + ID3 tags | N/A | No | No (silent drop) |
| smtchahal/spotify-import | Python | Jun 2023 | **CSV (artist/album/title)** | **Good** | No | Yes (failed.txt) |
| arg274/SpotiM3U | Python | Sep 2021 | M3U | N/A | No | Unknown |

---

## Recommendation

**Use `smtchahal/spotify-import` as the base, with one targeted modification.**

It is the only tool that:
- Accepts CSV input directly matching the AudioManager export format (`artist, album, title`)
- Has working failure logging
- Cleans up "feat." and related noise from search queries
- Has tests and reasonably recent maintenance (2023)
- Is simple Python — easy to read and modify

### Required Adaptation: Semicolon Artist Handling

The only substantive change needed is splitting the semicolon-separated artist field before building the search query. Currently the code passes the `artist` column verbatim. The fix is straightforward — in `spotify_import.py`, before constructing the search query, split on `;` and take the first artist (primary artist) for the Spotify search:

```python
# Current (approximate):
query = f"{row['artist']} - {row['title']} - {row['album']}"

# Fix:
primary_artist = row['artist'].split(';')[0].strip()
query = f"{primary_artist} - {row['title']} - {row['album']}"
```

Spotify's search is a fuzzy text search — searching for `Eminem - Patiently Waiting - 8 Mile` will find the right track reliably. Including `50 Cent` in the artist string does not help Spotify and may hurt matching.

### Minor Adaptations

- The AudioManager CSV has a `Year` column not present in the sample. `csv.DictReader` will include it in each row dict but the code never reads it — **no change needed**.
- The `replace_bad_words()` function already strips "feat." and "ft." from titles. This is compatible with the AudioManager filename style.
- Windows: Python runs on Windows, `pip install -r requirements.txt`, credentials go in `.env`. No obstacles.

### Alternative: `FutureSharks/spotify-m3u-import` if M3U is preferred

If you already have M3U playlists (or AudioManager can export them), this tool is more actively maintained (Nov 2025) and reads directly from ID3 tags. The only change needed would be handling the semicolon in `TPE1` — same fix: split on `;` and use only the first artist in the search query. The lack of a failure output file is a drawback that would also need patching.
