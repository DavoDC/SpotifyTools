"""Public-naming guard: the repo must not name a specific consumer or banned product.

Scans every git-tracked text file under src/, tests/, docs/, README.md and CLAUDE.md. The banned names are stored
only as SHA-256 hashes, so this file itself never spells them. To add a name: hash its lowercase letters and digits
only, and add the hash and its length below.
"""

import hashlib
import os
import re
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCAN_PREFIXES = ("src/", "tests/", "docs/")
SCAN_FILES = ("README.md", "CLAUDE.md")

# sha256 of the lowercase alphanumeric name, matched as a substring of the line's letters and digits.
BANNED_SUBSTRING_HASHES = {
    "4a7fdfb27fcc8e34f8b1ba34bf74b48ba09b682b3bd870984069d46446eb1059": 12,
    "1c1f3f132fcd5d806ec8e150fd425b8c1f86e533c08469844d150d9474f0503c": 6,
    "bb4a1d374c387602394cb97228559b78cdcd380a5759e81b18b8d19baf992af1": 18,
}
# Short name: matched only as a whole word, so ordinary words containing it are fine.
BANNED_WORD_HASHES = {"047007876c105127d9e0299df5dcea30b9fa5fae71be6f9d10ddb6357981cb9c"}
ABSOLUTE_PATH_RE = re.compile(r"C:\\Users|/c/Users", re.IGNORECASE)


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _line_has_banned_name(line):
    flat = re.sub(r"[^a-z0-9]", "", line.lower())
    lengths = set(BANNED_SUBSTRING_HASHES.values())
    for n in lengths:
        for i in range(len(flat) - n + 1):
            if BANNED_SUBSTRING_HASHES.get(_h(flat[i:i + n])) == n:
                return True
    return any(_h(w) in BANNED_WORD_HASHES for w in re.findall(r"[a-z0-9]+", line.lower()))


def _scanned_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    # This file holds only hashes and its own self-test inputs, so it is skipped.
    return [r for r in out if r != "tests/unit/test_public_naming.py" and (r.startswith(SCAN_PREFIXES) or r in SCAN_FILES)]


def _violations():
    found = []
    for rel in _scanned_files():
        try:
            with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a text file
        for number, line in enumerate(lines, start=1):
            if _line_has_banned_name(line) or ABSOLUTE_PATH_RE.search(line):
                found.append(f"{rel}:{number}")  # location only, never echo the banned text
    return found


def test_scan_covers_real_files():
    files = _scanned_files()
    assert "src/spotify_tools/acquire.py" in files
    assert "README.md" in files
    assert len(files) > 20


def test_hash_matcher_catches_names_without_spelling_them_here():
    assert _line_has_banned_name("see " + "".join(["audio", "Manager"]) + " docs")
    assert _line_has_banned_name("the " + "gu" + "i is")
    assert not _line_has_banned_name("a guide and guitar")


def test_no_consumer_app_names_or_absolute_user_paths():
    violations = _violations()
    assert violations == [], "\n".join(violations)
