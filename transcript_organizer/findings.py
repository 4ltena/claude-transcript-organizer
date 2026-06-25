import hashlib
import os
import re
import json
from .ledger import atomic_write_json


def normalize_id(kind: str, text: str) -> str:
    """Generate stable ID from kind and text by normalizing whitespace and punctuation.

    Args:
        kind: The finding kind (e.g., "decision", "next_step")
        text: The finding text to normalize

    Returns:
        First 16 characters of SHA1 hash of "kind|normalized_text"
    """
    norm = re.sub(r"\s+", " ", text or "").strip().lower()
    norm = re.sub(r"[、。,.\-_/:：；;　]+", "", norm)
    return hashlib.sha1(f"{kind}|{norm}".encode("utf-8")).hexdigest()[:16]


class FindingStore:
    """Store and merge findings with ID-based deduplication and source accumulation."""

    def __init__(self, data_dir: str):
        """Initialize FindingStore with a data directory.

        Args:
            data_dir: Base directory where findings will be stored (per-label JSON files)
        """
        self.dir = os.path.join(data_dir, "findings")

    def _path(self, label: str) -> str:
        """Get the file path for a label's findings.

        Args:
            label: The label identifier

        Returns:
            Full path to the label's JSON file
        """
        return os.path.join(self.dir, f"{label}.json")

    def load(self, label: str) -> list:
        """Load all findings for a label.

        Args:
            label: The label identifier

        Returns:
            List of finding records (dicts), or empty list if file doesn't exist or is corrupted
        """
        p = self._path(label)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def merge(self, label: str, findings) -> int:
        """Merge new findings into the store, deduplicating by ID and accumulating sources.

        Args:
            label: The label identifier
            findings: List of Finding objects to merge

        Returns:
            Count of newly-added finding IDs (duplicates don't increment count)
        """
        recs = self.load(label)
        by_id = {r["id"]: r for r in recs}
        added = 0

        for f in findings:
            fid = normalize_id(f.kind, f.text)
            if fid in by_id:
                # Existing finding: accumulate source info
                r = by_id[fid]
                if f.source and f.source not in r["src_titles"]:
                    r["src_titles"].append(f.source)
                if f.src_ts:
                    r["src_ts_list"].append(f.src_ts)
                    r["last_seen"] = max(r["last_seen"] or "", f.src_ts)
                r["confidence"] = max(r.get("confidence", 0), f.confidence)
            else:
                # New finding: create record
                by_id[fid] = {
                    "id": fid,
                    "kind": f.kind,
                    "text": f.text,
                    "confidence": f.confidence,
                    "src_titles": [f.source] if f.source else [],
                    "src_ts_list": [f.src_ts] if f.src_ts else [],
                    "first_seen": f.src_ts,
                    "last_seen": f.src_ts,
                }
                added += 1

        atomic_write_json(self._path(label), list(by_id.values()))
        return added
