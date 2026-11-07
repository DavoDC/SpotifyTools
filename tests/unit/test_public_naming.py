"""Public-naming guard: the repo must not name a specific consumer.

Scans every git-tracked text file under src/, tests/, docs/ (including
docs/References/Engineering-Guidelines.md), README.md and CLAUDE.md. Fails on consumer-app names, on the old name, on absolute user paths, and on one more banned product name (no exceptions).
"""

import os
import re
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
THIS_FILE = "tests/unit/test_public_naming.py"
SCAN_PREFIXES = ("src/", "tests/", "docs/")
SCAN_FILES = ("README.md", "CLAUDE.md")

FORBIDDEN_RE = old_pattern
BANNED_TERM_RE = re.compile("old-name", re.IGNORECASE)
ABSOLUTE_PATH_RE = re.compile(r"C:\\Users|/c/Users", re.IGNORECASE)


def _scanned_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    picked = []
    for rel in out:
        if rel == THIS_FILE:
            continue
        if rel.startswith(SCAN_PREFIXES) or rel in SCAN_FILES:
            picked.append(rel)
    return picked


def _violations():
    found = []
    for rel in _scanned_files():
        path = os.path.join(REPO_ROOT, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a text file
        for number, line in enumerate(lines, start=1):
            where = f"{rel}:{number}: {line.strip()}"
            if FORBIDDEN_RE.search(line):
                found.append(where)
            if BANNED_TERM_RE.search(line):
                found.append(where)
            if ABSOLUTE_PATH_RE.search(line):
                found.append(where)
    return found


def test_scan_covers_real_files():
    # Guards against a vacuous pass if git ls-files ever returns nothing useful.
    files = _scanned_files()
    assert "src/spotify_tools/acquire.py" in files
    assert "README.md" in files
    assert len(files) > 20


def test_no_consumer_app_names_or_absolute_user_paths():
    violations = _violations()
    assert violations == [], "\n".join(violations)
