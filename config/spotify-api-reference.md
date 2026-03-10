# Spotify Web API Reference — SpotifyPlaylistGen

**Last verified:** 2026-03-10
**Source:** https://developer.spotify.com/documentation/web-api

> **IMPORTANT:** Spotify has deprecated all `/tracks` endpoints and replaced them with `/items`.
> Always check this file before making any API calls. Never assume old endpoint behaviour.

---

## Endpoint Index (Correct Docs URLs)

| Operation | Docs URL |
|-----------|----------|
| Get Playlist | `/reference/get-playlist` |
| Get Playlist Items | `/reference/get-playlists-items` |
| Add Items to Playlist | `/reference/add-items-to-playlist` |
| Remove Playlist Items | `/reference/remove-items-playlist` |
| Update/Replace Playlist Items | `/reference/reorder-or-replace-playlists-items` |

Base: `https://developer.spotify.com/documentation/web-api`

---

## GET /playlists/{id} — Get Playlist

Returns the full playlist object.

**Response structure (critical):**
- Tracks are under `playlist["items"]` key (NOT `playlist["tracks"]`)
- Each playlist item uses `item["item"]` for the track (NOT `item["track"]`)
- `"track"` key still exists but is **deprecated** — use `"item"` instead

```json
{
  "id": "...",
  "items": {
    "href": "...",
    "items": [
      {
        "added_at": "...",
        "added_by": {...},
        "is_local": false,
        "item": {
          "id": "4E64eAph6AYI98ucunrGH8",
          "uri": "spotify:track:4E64eAph6AYI98ucunrGH8",
          "name": "...",
          "artists": [...],
          "album": {...}
        }
      }
    ],
    "limit": 100,
    "next": "...",
    "offset": 0,
    "total": 603
  }
}
```

**Pagination:** First page may return `items=[]` with `total > 0`. Must follow `"next"` URL to paginate.

---

## POST /playlists/{id}/items — Add Tracks

**Request body:**
```json
{ "uris": ["spotify:track:abc", "spotify:track:def"] }
```
- `uris` — required, array of Spotify URIs (max 100 per request)
- `position` — optional integer for insertion point
- Bare list not accepted — MUST be `{"uris": [...]}`
- Old `/tracks` endpoint returns 403

---

## DELETE /playlists/{id}/items — Remove Tracks

**Request body:**
```json
{
  "items": [
    { "uri": "spotify:track:abc" },
    { "uri": "spotify:track:def" }
  ],
  "snapshot_id": "optional"
}
```
- Key is `"items"` (NOT `"tracks"` — that was the old format)
- Max 100 items per request
- `"positions"` field NOT supported on new endpoint (old `/tracks` endpoint had it)
- `snapshot_id` optional, recommended for concurrent safety
- Old `/tracks` endpoint returns 403

---

## PUT /playlists/{id}/items — Replace All Tracks

Replaces the ENTIRE playlist contents with a new set of URIs.

**Request body:**
```json
{ "uris": ["spotify:track:abc", "spotify:track:def"] }
```
- Max 100 URIs — to add more, use PUT first 100 then POST remaining
- Omit `uris` to clear the playlist entirely
- `range_start`/`insert_before`/`range_length` for reordering (mutually exclusive with `uris`)

---

## Key Lessons (Hard-Won)

1. **`"track"` → `"item"` key change**: Every playlist item now uses `item["item"]` for the track object. `item["track"]` exists but is deprecated. Test with `_get_track_obj()` helper that handles both.

2. **`/tracks` endpoints all deprecated**: GET, POST, DELETE, PUT `/playlists/{id}/tracks` → all return 403. Use `/items` equivalents.

3. **DELETE body key changed**: Old format `{"tracks": [{"uri": "...", "positions": [...]}]}` → New format `{"items": [{"uri": "..."}]}`. No `positions` support in new endpoint.

4. **First page can be empty**: `sp.playlist()` may return `items=[]` with `total > 0`. Always paginate via `"next"` URL.

5. **Safety check**: If `get_playlist_track_ids()` returns 0 IDs but API reports `total > 0`, something is wrong — ABORT, do not proceed with uploads (main.py enforces this).

6. **OAuth scopes required**: `playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative`

7. **Rate limiting**: 429 → respect `Retry-After` header. Use 100ms inter-search delay. After bulk upload, wait 15s before next API calls.

8. **spotipy internal methods used**: `sp._post()`, `sp._delete()`, `sp._get_id()` — spotipy's built-in playlist methods use deprecated endpoints.
