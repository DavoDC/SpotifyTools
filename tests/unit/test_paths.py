"""Tests for spotify_tools/paths.py - the single source of truth for REPO_ROOT.

Regression coverage for the 2026-09-04 finding: the 2026-09-02 src/ re-nesting
broke CONFIG_PATH (fixed in commit 2fca625, guarded by test_config.py) AND,
identically, spotify_client.py's CACHE_PATH, main.py's HISTORY_PATH/LOCK_PATH/
LOG_DIR/REPORT_DIR, diagnose.py's CONFIG_PATH/LOG_DIR, and open_playlist.py's
CACHE_DIR/LOG_FILE - all silently resolving one directory too shallow (into
src/data/... and src/config/... instead of data/... and config/...) because
each file recomputed its own dirname() chain against __file__ independently.
This file guards the fix: every module below now imports REPO_ROOT from
paths.py instead of deriving its own BASE_DIR, so there is exactly one place
left that can get the depth wrong.
"""
import importlib
import os

from spotify_tools.paths import REPO_ROOT


def test_repo_root_resolves_to_a_real_directory_containing_config_and_data():
    """REPO_ROOT (no env override) must be the actual repo root, not src/."""
    assert os.path.isdir(REPO_ROOT), REPO_ROOT
    assert os.path.isdir(os.path.join(REPO_ROOT, "config")), REPO_ROOT
    assert os.path.isdir(os.path.join(REPO_ROOT, "data")), REPO_ROOT
    assert os.path.basename(os.path.normpath(REPO_ROOT)) != "src", (
        "REPO_ROOT points at src/ - the exact off-by-one bug this module exists to prevent"
    )


def test_spotify_tools_root_env_var_overrides_default(tmp_path):
    """SPOTIFY_TOOLS_ROOT, if set, wins over the computed default.

    Uses os.environ directly (not monkeypatch) so the env var is guaranteed
    gone BEFORE the restoring reload runs: monkeypatch only reverts in fixture
    teardown, which happens AFTER this function returns - reloading the module
    in a `finally` while the fixture's env var is still set would poison
    spotify_tools.paths.REPO_ROOT for every test that runs after this one.
    """
    import spotify_tools.paths as paths_module
    original_root = paths_module.REPO_ROOT
    os.environ["SPOTIFY_TOOLS_ROOT"] = str(tmp_path)
    try:
        importlib.reload(paths_module)
        assert paths_module.REPO_ROOT == str(tmp_path)
    finally:
        del os.environ["SPOTIFY_TOOLS_ROOT"]
        importlib.reload(paths_module)
        assert paths_module.REPO_ROOT == original_root


def test_cache_path_resolves_under_repo_root_not_src():
    """Regression: spotify_client.CACHE_PATH used its own 2-dirname BASE_DIR,
    landing in <repo>/src/data/.cache instead of <repo>/data/.cache."""
    from spotify_tools.spotify_client import CACHE_PATH
    assert CACHE_PATH == os.path.join(REPO_ROOT, "data", ".cache")
    assert "src" not in os.path.relpath(CACHE_PATH, REPO_ROOT).split(os.sep)


def test_main_data_paths_resolve_under_repo_root_not_src():
    """Regression: main.py's HISTORY_PATH/LOCK_PATH/LOG_DIR/REPORT_DIR used
    the same broken BASE_DIR pattern - most dangerously HISTORY_PATH, since a
    wrong path there means the sync tool silently starts with empty history."""
    mod = importlib.import_module("spotify_tools.main")
    assert mod.HISTORY_PATH == os.path.join(REPO_ROOT, "data", "history.json")
    assert os.path.exists(mod.HISTORY_PATH), mod.HISTORY_PATH
    assert mod.LOCK_PATH == os.path.join(REPO_ROOT, "data", "run.lock")
    assert mod.LOG_DIR == os.path.join(REPO_ROOT, "data", "logs")
    assert mod.REPORT_DIR == os.path.join(REPO_ROOT, "data", "reports")


def test_open_playlist_data_paths_resolve_under_repo_root_not_src():
    mod = importlib.import_module("spotify_tools.open_playlist")
    assert mod.CACHE_DIR == os.path.join(REPO_ROOT, "data", "playlist_cache")
    assert mod.LOG_FILE == os.path.join(REPO_ROOT, "data", "logs", "open_playlist.log")


def test_diagnose_data_paths_resolve_under_repo_root_not_src():
    mod = importlib.import_module("spotify_tools.diagnose")
    assert mod.CONFIG_PATH == os.path.join(REPO_ROOT, "config", "config.json")
    assert mod.LOG_DIR == os.path.join(REPO_ROOT, "data", "logs")
