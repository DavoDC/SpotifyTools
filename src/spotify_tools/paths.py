"""Single source of truth for this repo's root directory.

Every module that derives a path from the repo root (config/, data/,
tests/fixtures/) imports REPO_ROOT from here instead of recomputing its own
os.path.dirname(...) chain against __file__. That per-file arithmetic is
fragile: it silently breaks the instant a module's nesting depth changes,
because each copy has to be updated in lockstep and nothing enforces that.

History: the 2026-09-02 src/ re-nesting (moving spotify_tools/ under src/)
added one directory level. config.py's CONFIG_PATH was fixed for it
(commit 2fca625), but spotify_client.py's CACHE_PATH, main.py's
HISTORY_PATH/LOCK_PATH/LOG_DIR/REPORT_DIR, diagnose.py's CONFIG_PATH/LOG_DIR,
and open_playlist.py's CACHE_DIR/LOG_FILE/sys.path entry all still used the
same stale 2-dirname count and silently resolved one level too shallow
(found 2026-09-04). This module exists so that only ONE file ever computes
the offset from its own __file__ - every other module just imports the
already-resolved constant, so a future move only requires updating this file.

Resolution order:
1. SPOTIFY_TOOLS_ROOT env var, if set - lets a consumer (AudioManager's GUI,
   a test) point at a specific location explicitly.
2. This file's own location: paths.py lives at <repo>/src/spotify_tools/paths.py,
   so three dirname() calls from here always lands at <repo>.
"""
import os

_THIS_FILE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.environ.get("SPOTIFY_TOOLS_ROOT", _THIS_FILE_ROOT)
