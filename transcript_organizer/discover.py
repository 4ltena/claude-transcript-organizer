import json, os, glob, fnmatch
from dataclasses import asdict
from datetime import datetime, timezone
from .models import ConvMeta
from .ledger import atomic_write_json

def scan_meta(path: str) -> ConvMeta:
    cwd = None; first_ts = last_ts = None; nmsg = 0; sidechain = False
    with open(path, errors="ignore", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except Exception:
                continue
            if o.get("isSidechain"):
                sidechain = True
            if not cwd and o.get("cwd"):
                cwd = o["cwd"]
            ts = o.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            if o.get("type") in ("user", "assistant"):
                nmsg += 1
    base = os.path.basename(path)
    if base.startswith("agent-") or "/subagents/" in path:
        sidechain = True
    return ConvMeta(path=path, sid=base[:-6] if base.endswith(".jsonl") else base,
                    cwd=cwd, first_ts=first_ts, last_ts=last_ts, nmsg=nmsg,
                    is_sidechain=sidechain, basename=base)

def _ts_epoch(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None

def classify(meta: ConvMeta, body: str, config, now_epoch: float) -> set:
    flags = set()
    if meta.is_sidechain:
        flags.add("sidechain")
    sigs = config.meta_signatures
    if sigs and all(s in body for s in sigs):
        flags.add("meta")
    if meta.nmsg < config.min_msgs and len(body) < config.min_chars:
        flags.add("trivial")
    last = _ts_epoch(meta.last_ts)
    if last is None:
        last = os.path.getmtime(meta.path)
    if now_epoch - last < config.protect_recent_minutes * 60:
        flags.add("active")
    return flags

class ScanCache:
    """Cache of scan_meta() results keyed by file mtime+size.

    Avoids re-reading transcripts whose content has not changed between runs.
    The cache is rebuilt from the live file set each run: only files looked up
    via get() during this run are carried into the saved cache, so deleted
    files are pruned automatically. A missing or corrupt cache file is treated
    as empty.
    """

    def __init__(self, path: str):
        self.path = path
        self._old: dict = {}
        self._new: dict = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._old = json.load(f)
            except Exception:
                self._old = {}

    def get(self, file_path: str) -> ConvMeta:
        """Return the (cached or freshly scanned) ConvMeta for file_path.

        Raises OSError if the file vanished between glob and stat.
        """
        st = os.stat(file_path)
        key = f"{st.st_mtime_ns}:{st.st_size}"
        rec = self._old.get(file_path)
        if rec and rec.get("key") == key:
            meta = ConvMeta(**rec["meta"])
        else:
            meta = scan_meta(file_path)
            rec = {"key": key, "meta": asdict(meta)}
        self._new[file_path] = rec
        return meta

    def save(self) -> None:
        atomic_write_json(self.path, self._new)


def iter_conversations(config, cache: "ScanCache | None" = None):
    for path in glob.iglob(os.path.join(config.scan_base, "**", "*.jsonl"), recursive=True):
        if any(fnmatch.fnmatch(path, g) for g in config.exclude_globs):
            continue
        try:
            yield cache.get(path) if cache else scan_meta(path)
        except OSError:
            # File vanished/unreadable between glob and read — skip, don't abort.
            continue
