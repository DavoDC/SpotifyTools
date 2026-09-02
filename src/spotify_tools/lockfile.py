"""Lockfile to prevent concurrent runs.

Uses a simple PID-based lockfile. If the lockfile exists and the PID is still
running, the lock is considered held. Stale lockfiles (PID no longer running)
are cleaned up automatically.
"""

import logging
import os


class LockFile:
    """Simple PID-based lockfile."""

    def __init__(self, path: str):
        self.path = path

    def acquire(self) -> bool:
        """Try to acquire the lock. Returns True if acquired, False if already held."""
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    old_pid = int(f.read().strip())
                if self._pid_alive(old_pid):
                    logging.warning(f"Lock held by PID {old_pid}")
                    return False
                else:
                    logging.info(f"Removing stale lockfile (PID {old_pid} no longer running)")
            except (ValueError, OSError):
                logging.info("Removing invalid lockfile")

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            f.write(str(os.getpid()))
        return True

    def release(self):
        """Release the lock."""
        try:
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.remove(self.path)
        except (ValueError, OSError) as e:
            logging.warning(f"Failed to release lockfile: {e}")

    def _pid_alive(self, pid: int) -> bool:
        """Check if a process with given PID is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(
                "Another instance is already running. "
                "If this is incorrect, delete the lockfile: " + self.path
            )
        return self

    def __exit__(self, *args):
        self.release()
