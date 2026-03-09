# Spotify Playlist Generator

Reads your offline music library (CSV/JSON from the consumer, or M3U) and creates a matching Spotify playlist.

**Use case:** You have an offline music library at home, and want to listen to the same tracks on Spotify at work.

## Features

- Upload CSV, JSON, or M3U playlist files from your offline library
- Automatic track matching against Spotify with confidence scoring (exact / high / low / none)
- Review matches and pick alternatives before creating the playlist
- Creates a Spotify playlist with all matched tracks
- Handles semicolon-separated artists (`Artist1;Artist2`) and strips `feat.` from titles

---

## Setup

### 1. Get Spotify API credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Set **Redirect URI** to `http://localhost:PORT/auth/callback`
4. Copy your **Client ID** and **Client Secret**

### 2. Configure environment

```bash
cp .env.example server/.env
```

Edit `server/.env` and fill in your credentials:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:PORT/auth/callback
SESSION_SECRET=any_long_random_string
PORT=3001
```

### 3. Install dependencies

```bash
npm install
```

### 4. Run the app

```bash
# Start both frontend and backend together
npm run dev

# Or start individually
npm run dev:server   # backend on http://localhost:PORT
npm run dev:client   # frontend on http://localhost:PORT
```

### 5. Run tests

```bash
npm test
# or
npm test --workspace=server
```

---

## Input File Formats

### CSV (the consumer export)
Columns: `Artist,Title,Album,Year` (order does not matter, extra columns ignored)

```csv
Artist,Title,Album,Year
Eminem,Lose Yourself,8 Mile Soundtrack,2002
Chiddy Bang;Icona Pop,Mind Your Manners,Mind Your Manners,2012
```

### JSON
Array of track objects:

```json
[
  { "artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile Soundtrack", "year": 2002 },
  { "artist": "Chiddy Bang;Icona Pop", "title": "Mind Your Manners" }
]
```

### M3U
Standard M3U playlist with `#EXTINF` lines:

```
#EXTM3U
#EXTINF:180,Eminem - Lose Yourself
/path/to/file.mp3
```

---

## Project Structure

```
SpotifyTools/
  package.json          # npm workspaces root
  the UI               # React + TypeScript + Vite frontend
    src/
      components/       # page components
      services/         # apiClient.ts (calls backend)
      types/            # Shared TypeScript types
  server/               # Node.js + Express + TypeScript backend
    src/
      routes/           # auth, library, spotify routes
      services/         # spotifyService, libraryService, matchingService
    tests/              # Vitest TDD tests
```

---

## Matching Logic

For each offline track:
1. Primary artist = first artist before `;` separator
2. Strip `feat.` / `ft.` variants from title
3. Search Spotify: `artist:"PrimaryArtist" track:"CleanTitle"`
4. Score the result:
   - **exact** — artist and title match exactly (case-insensitive)
   - **high** — normalised match (strip punctuation, articles like "the")
   - **low** — partial word overlap
   - **none** — no results or very poor match
5. Return top match + up to 3 alternatives for user to review
