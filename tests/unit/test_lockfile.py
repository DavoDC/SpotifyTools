"""Tests for src/lockfile.py — concurrent run protection."""

import os
import tempfile

import pytest

from src.lockfile import LockFile


def test_acquire_succeeds_when_no_lockfile():
    with tempfile.TemporaryDirectory() as d:
        lock = LockFile(os.path.join(d, "test.lock"))
        assert lock.acquire() is True
        lock.release()


def test_acquire_fails_when_held_by_current_process():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        lock1 = LockFile(path)
        lock2 = LockFile(path)

        assert lock1.acquire() is True
        # Same PID is alive, so lock should be held
        assert lock2.acquire() is False
        lock1.release()


def test_release_removes_lockfile():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        lock = LockFile(path)
        lock.acquire()
        lock.release()
        assert not os.path.exists(path)


def test_stale_lockfile_cleaned_up():
    """If lockfile contains a PID that's no longer running, it should be cleaned up."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        # Write a fake PID that definitely isn't running
        with open(path, "w") as f:
            f.write("999999999")

        lock = LockFile(path)
        assert lock.acquire() is True
        lock.release()


def test_invalid_lockfile_cleaned_up():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        with open(path, "w") as f:
            f.write("not a pid")

        lock = LockFile(path)
        assert lock.acquire() is True
        lock.release()


def test_context_manager_acquires_and_releases():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        with LockFile(path):
            assert os.path.exists(path)
        assert not os.path.exists(path)


def test_context_manager_raises_when_locked():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        lock1 = LockFile(path)
        lock1.acquire()
        try:
            with pytest.raises(RuntimeError, match="Another instance"):
                with LockFile(path):
                    pass
        finally:
            lock1.release()


def test_release_only_removes_own_lockfile():
    """Release should not remove a lockfile written by another PID."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.lock")
        # Write someone else's PID
        with open(path, "w") as f:
            f.write("1")  # PID 1 (init/system, always running)

        lock = LockFile(path)
        lock.release()
        # Should NOT have been removed (not our PID)
        assert os.path.exists(path)
