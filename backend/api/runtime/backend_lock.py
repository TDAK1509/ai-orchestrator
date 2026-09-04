"""Track B4: one backend at a time. An flock, not pg_advisory_lock -- the dev path is SQLite (pyproject.toml's aiosqlite extra), which a Postgres-only mechanism would leave unprotected."""
import fcntl
from pathlib import Path


class BackendLock:
    def __init__(self, path: Path):
        self._path = path
        self._handle = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            handle.close()
            raise RuntimeError(f"another backend already holds the run lock at {self._path}") from error
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle, fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None
