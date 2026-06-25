import json, os, glob, fnmatch
from datetime import datetime, timezone
from .models import ConvMeta

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

def iter_conversations(config):
    for path in glob.iglob(os.path.join(config.scan_base, "**", "*.jsonl"), recursive=True):
        if any(fnmatch.fnmatch(path, g) for g in config.exclude_globs):
            continue
        yield scan_meta(path)
