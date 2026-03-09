// OfflineTrack — represents a track from the user's local music library
export interface OfflineTrack {
  title: string;
  artist: string;       // may be semicolon-separated: "Artist1;Artist2"
  album?: string;
  year?: number;
}

// SpotifyTrack — a track returned from the Spotify API
export interface SpotifyTrack {
  id: string;
  name: string;
  artists: string[];
  album: string;
  uri: string;
  externalUrl: string;
}

// MatchResult — pairing of an offline track to a Spotify search result
export interface MatchResult {
  offline: OfflineTrack;
  spotify: SpotifyTrack | null;
  confidence: 'exact' | 'high' | 'low' | 'none';
  alternatives: SpotifyTrack[];  // up to 3 other candidates the user can pick
}

// Spotify API token response shape
export interface SpotifyTokenResponse {
  access_token: string;
  token_type: string;
  scope: string;
  expires_in: number;
  refresh_token: string;
}

// Session data stored server-side
export interface SessionData {
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: number;   // Unix timestamp ms
  codeVerifier?: string;
}

// Request body for POST /spotify/playlist
export interface CreatePlaylistRequest {
  name: string;
  tracks: MatchResult[];  // user-confirmed matches (spotify may be null for skipped)
  isPublic?: boolean;
}
