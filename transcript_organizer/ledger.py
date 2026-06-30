import json
import os
import tempfile


def atomic_write_json(path: str, obj) -> None:
    """Write JSON to a file atomically using a temporary file and os.replace.

    Creates parent directories if they don't exist. If writing fails,
    the temporary file is cleaned up and the original file remains untouched.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Ledger:
    """A ledger for tracking processed session identifiers.

    Stores processed session metadata in a JSON file. Automatically
    persists changes to disk atomically. Missing file is treated
    as an empty ledger.
    """

    def __init__(self, path: str):
        """Initialize a Ledger from a JSON file.

        Args:
            path: Path to the JSON ledger file. Created on first write
                  if it doesn't exist. If file is corrupted, treated as empty.
        """
        self.path = path
        self._data = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def is_processed(self, sid: str) -> bool:
        """Check if a session has been marked as processed.

        Args:
            sid: Session identifier.

        Returns:
            True if session is in the ledger, False otherwise.
        """
        return sid in self._data

    def mark(self, sid: str, meta: dict) -> None:
        """Mark a session as processed with metadata.

        Persists immediately to disk using atomic write.

        Args:
            sid: Session identifier.
            meta: Metadata dictionary to store for this session.
        """
        self._data[sid] = meta
        atomic_write_json(self.path, self._data)

    def drop(self, sid: str) -> bool:
        """Remove a session from the ledger, persisting immediately.

        Used when its transcript is deleted (trashed) so the ledger stays in
        sync with the live transcript set. Dropping an unknown id is a no-op.

        Args:
            sid: Session identifier.

        Returns:
            True if an entry was removed, False if the id was not present.
        """
        if sid not in self._data:
            return False
        del self._data[sid]
        atomic_write_json(self.path, self._data)
        return True

    def all(self) -> dict:
        """Get a copy of all processed sessions and their metadata.

        Returns:
            A dictionary mapping session ID to metadata.
        """
        return dict(self._data)
