import type { OfflineTrack, SpotifyTrack, MatchResult } from '../types/index.js';

// Words stripped during normalisation for "high" confidence matching
const STRIP_WORDS = new Set(['the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for']);

// Regex patterns for feat. removal — covers common variants
const FEAT_PATTERN =
  /\s*[\(\[](feat\.?|ft\.?|featuring|with|w\/)\s+[^\)\]]+[\)\]]/gi;
const FEAT_INLINE_PATTERN =
  /\s+(feat\.?|ft\.?|featuring)\s+.+$/i;

/**
 * Build the Spotify search query string for an offline track.
 * - Uses the primary artist (first before `;`)
 * - Strips feat. from title
 */
export function buildSearchQuery(track: OfflineTrack): string {
  const primaryArtist = track.artist.split(';')[0].trim();
  const cleanTitle = stripFeat(track.title);

  if (primaryArtist) {
    return `artist:"${primaryArtist}" track:"${cleanTitle}"`;
  }
  return `track:"${cleanTitle}"`;
}

/**
 * Remove feat./ft./featuring annotations from a title string.
 * Handles both parenthetical "(feat. X)" and inline "feat. X" forms.
 */
export function stripFeat(title: string): string {
  let cleaned = title.replace(FEAT_PATTERN, '');
  cleaned = cleaned.replace(FEAT_INLINE_PATTERN, '');
  return cleaned.trim();
}

/**
 * Normalise a string for "high" confidence comparison:
 * lowercase, strip punctuation, remove common stop words.
 */
export function normalise(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')   // punctuation → space
    .split(/\s+/)
    .filter(w => w.length > 0 && !STRIP_WORDS.has(w))
    .join(' ');
}

/**
 * Score how well a Spotify track matches an offline track.
 * Returns a confidence level.
 */
export function scoreMatch(
  offline: OfflineTrack,
  spotify: SpotifyTrack
): 'exact' | 'high' | 'low' | 'none' {
  const offlineTitle  = stripFeat(offline.title).toLowerCase().trim();
  const offlineArtist = offline.artist.split(';')[0].trim().toLowerCase();

  const spotifyTitle  = spotify.name.toLowerCase().trim();
  const spotifyArtist = spotify.artists[0]?.toLowerCase() ?? '';

  // Exact match — case-insensitive, otherwise identical
  if (offlineTitle === spotifyTitle && offlineArtist === spotifyArtist) {
    return 'exact';
  }
  // Also treat as exact if only the title matches perfectly and artist is blank
  if (offlineTitle === spotifyTitle && !offlineArtist) {
    return 'exact';
  }

  // High confidence — normalised comparison
  const normOfflineTitle  = normalise(stripFeat(offline.title));
  const normOfflineArtist = normalise(offlineArtist);
  const normSpotifyTitle  = normalise(spotify.name);
  const normSpotifyArtist = normalise(spotifyArtist);

  const titleMatch  = normOfflineTitle === normSpotifyTitle;
  const artistMatch = normOfflineArtist === normSpotifyArtist || !normOfflineArtist;

  if (titleMatch && artistMatch) return 'high';

  // Low confidence — at least one significant word from the title overlaps
  const offlineWords  = new Set(normOfflineTitle.split(' ').filter(w => w.length > 2));
  const spotifyWords  = normSpotifyTitle.split(' ').filter(w => w.length > 2);
  const overlap = spotifyWords.filter(w => offlineWords.has(w));

  if (overlap.length >= Math.min(2, offlineWords.size)) return 'low';

  return 'none';
}

/**
 * Match a list of offline tracks against Spotify results.
 * The spotifySearchFn callback does the actual Spotify API call —
 * this keeps the matching logic pure and easily testable.
 *
 * @param tracks       offline tracks to match
 * @param searchFn     async fn(query: string) => SpotifyTrack[] (top 5 results)
 */
export async function matchTracks(
  tracks: OfflineTrack[],
  searchFn: (query: string) => Promise<SpotifyTrack[]>
): Promise<MatchResult[]> {
  const results: MatchResult[] = [];

  for (const offline of tracks) {
    const query = buildSearchQuery(offline);
    let candidates: SpotifyTrack[] = [];

    try {
      candidates = await searchFn(query);
    } catch {
      // Network error — return 'none' for this track
      results.push({ offline, spotify: null, confidence: 'none', alternatives: [] });
      continue;
    }

    if (candidates.length === 0) {
      results.push({ offline, spotify: null, confidence: 'none', alternatives: [] });
      continue;
    }

    // Score every candidate and pick the best
    const scored = candidates.map(c => ({
      track: c,
      confidence: scoreMatch(offline, c),
    }));

    // Sort by confidence priority
    const priority: Record<string, number> = { exact: 0, high: 1, low: 2, none: 3 };
    scored.sort((a, b) => priority[a.confidence] - priority[b.confidence]);

    const best = scored[0];
    const alternatives = scored
      .slice(1)
      .filter(s => s.confidence !== 'none')
      .map(s => s.track)
      .slice(0, 3);

    results.push({
      offline,
      spotify:      best.confidence !== 'none' ? best.track : null,
      confidence:   best.confidence,
      alternatives,
    });
  }

  return results;
}
