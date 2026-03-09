import type { OfflineTrack } from '../types/index.js';

/**
 * Parse a CSV string (the consumer export format) into OfflineTrack[].
 * Expects at minimum Artist and Title columns. Album and Year are optional.
 * Skips rows missing both title and artist. Header row is required.
 */
export function parseCSV(csvText: string): OfflineTrack[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim().length > 0);
  if (lines.length < 2) return [];

  // Parse the header row — normalise to lowercase for flexible matching
  const headers = parseCSVRow(lines[0]).map(h => h.trim().toLowerCase());

  const titleIdx  = findIndex(headers, ['title', 'track', 'song', 'name']);
  const artistIdx = findIndex(headers, ['artist', 'artists', 'performer']);
  const albumIdx  = findIndex(headers, ['album', 'album name']);
  const yearIdx   = findIndex(headers, ['year', 'date', 'release year']);

  if (titleIdx === -1 || artistIdx === -1) {
    throw new Error(
      `CSV must have "Title" and "Artist" columns. Found: ${headers.join(', ')}`
    );
  }

  const tracks: OfflineTrack[] = [];

  for (let i = 1; i < lines.length; i++) {
    const cells = parseCSVRow(lines[i]);
    if (cells.length === 0) continue;

    const title  = safeGet(cells, titleIdx).trim();
    const artist = safeGet(cells, artistIdx).trim();

    // Skip rows with no meaningful data
    if (!title && !artist) continue;
    // A row with a title but no artist is still useful (we can search by title)
    if (!title) continue;

    const track: OfflineTrack = { title, artist };

    if (albumIdx !== -1) {
      const album = safeGet(cells, albumIdx).trim();
      if (album) track.album = album;
    }

    if (yearIdx !== -1) {
      const yearStr = safeGet(cells, yearIdx).trim();
      const year = parseInt(yearStr, 10);
      if (!isNaN(year) && year > 1900 && year <= new Date().getFullYear() + 1) {
        track.year = year;
      }
    }

    tracks.push(track);
  }

  return tracks;
}

/**
 * Parse a JSON string — either an array of track objects or { tracks: [...] }.
 * Field names are flexible (title/name/song/track, artist/artists/performer).
 */
export function parseJSON(jsonText: string): OfflineTrack[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonText);
  } catch {
    throw new Error('Invalid JSON: could not parse file');
  }

  let items: unknown[];
  if (Array.isArray(parsed)) {
    items = parsed;
  } else if (
    parsed !== null &&
    typeof parsed === 'object' &&
    'tracks' in parsed &&
    Array.isArray((parsed as Record<string, unknown>).tracks)
  ) {
    items = (parsed as Record<string, unknown>).tracks as unknown[];
  } else {
    throw new Error('JSON must be an array of tracks or { tracks: [...] }');
  }

  const tracks: OfflineTrack[] = [];

  for (const item of items) {
    if (item === null || typeof item !== 'object') continue;
    const obj = item as Record<string, unknown>;

    const title  = firstString(obj, ['title', 'name', 'song', 'track']);
    const artist = firstString(obj, ['artist', 'artists', 'performer']);

    if (!title) continue;

    const track: OfflineTrack = { title, artist: artist ?? '' };

    const album = firstString(obj, ['album', 'album_name', 'albumName']);
    if (album) track.album = album;

    const yearRaw = obj['year'] ?? obj['date'] ?? obj['releaseYear'] ?? obj['release_year'];
    if (yearRaw !== undefined) {
      const year = parseInt(String(yearRaw), 10);
      if (!isNaN(year) && year > 1900) track.year = year;
    }

    tracks.push(track);
  }

  return tracks;
}

/**
 * Parse an M3U/M3U8 playlist file into OfflineTrack[].
 * Reads #EXTINF lines: `#EXTINF:duration,Artist - Title`
 * Falls back to extracting filename from the file path line if no EXTINF.
 */
export function parseM3U(m3uText: string): OfflineTrack[] {
  const lines = m3uText.split(/\r?\n/);
  const tracks: OfflineTrack[] = [];
  let pendingExtinf: string | null = null;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line === '#EXTM3U') continue;

    if (line.startsWith('#EXTINF:')) {
      // Format: #EXTINF:duration,Artist - Title
      const commaIdx = line.indexOf(',');
      if (commaIdx !== -1) {
        pendingExtinf = line.slice(commaIdx + 1).trim();
      }
      continue;
    }

    if (line.startsWith('#')) continue; // other comment/tag lines

    // This is a file path or URL line
    let title = '';
    let artist = '';

    if (pendingExtinf) {
      const parsed = parseExtinfTitle(pendingExtinf);
      title  = parsed.title;
      artist = parsed.artist;
      pendingExtinf = null;
    } else {
      // No EXTINF — extract from filename
      title = filenameToTitle(line);
    }

    if (title) {
      tracks.push({ title, artist });
    }
  }

  return tracks;
}

// ---- helpers ----------------------------------------------------------------

function findIndex(headers: string[], candidates: string[]): number {
  for (const candidate of candidates) {
    const idx = headers.indexOf(candidate);
    if (idx !== -1) return idx;
  }
  return -1;
}

function safeGet(arr: string[], idx: number): string {
  return idx >= 0 && idx < arr.length ? arr[idx] : '';
}

function firstString(obj: Record<string, unknown>, keys: string[]): string | undefined {
  for (const key of keys) {
    const val = obj[key];
    if (val !== undefined && val !== null && String(val).trim()) {
      return String(val).trim();
    }
  }
  return undefined;
}

/**
 * Parse a single CSV row respecting double-quoted fields with embedded commas.
 */
export function parseCSVRow(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        // Escaped double-quote inside a quoted field
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

/**
 * Parse the display name from an #EXTINF line: "Artist - Title" or just "Title"
 */
function parseExtinfTitle(displayName: string): { artist: string; title: string } {
  const dashIdx = displayName.indexOf(' - ');
  if (dashIdx !== -1) {
    return {
      artist: displayName.slice(0, dashIdx).trim(),
      title:  displayName.slice(dashIdx + 3).trim(),
    };
  }
  return { artist: '', title: displayName.trim() };
}

/**
 * Extract a best-guess title from a file path (last segment, no extension).
 */
function filenameToTitle(filePath: string): string {
  const segments = filePath.replace(/\\/g, '/').split('/');
  const filename = segments[segments.length - 1];
  return filename.replace(/\.[^.]+$/, '').trim();
}
