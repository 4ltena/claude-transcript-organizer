import os, time, json
from transcript_organizer.config import load_config
from transcript_organizer.discover import scan_meta, classify, ScanCache, iter_conversations
import transcript_organizer.discover as discover

def _cfg(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"protect_recent_minutes": 30, "min_msgs": 2,
                             "min_chars": 400, "meta_signatures": ["引き継ぎ", "transcript-organizer"],
                             "exclude_globs": ["*autonomous*"]}))
    return load_config(str(p))

def test_scan_meta_detects_sidechain(write_jsonl):
    rows = [{"type": "user", "cwd": "/p", "isSidechain": True,
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "hi"}}]
    m = scan_meta(write_jsonl("agent-x.jsonl", rows))
    assert m.is_sidechain is True
    assert m.basename == "agent-x.jsonl"

def test_classify_flags(tmp_path, write_jsonl):
    cfg = _cfg(tmp_path)
    now = time.time()
    rows = [{"type": "user", "cwd": "/p", "isSidechain": True,
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "x"}}]
    m = scan_meta(write_jsonl("agent-y.jsonl", rows))
    flags = classify(m, "本文に引き継ぎとtranscript-organizer", cfg, now)
    assert "sidechain" in flags
    assert "meta" in flags        # both signatures present
    # trivial: short body + few msgs
    m2 = scan_meta(write_jsonl("s.jsonl",
        [{"type": "user", "cwd": "/p", "message": {"role": "user", "content": "短い"}}]))
    assert "trivial" in classify(m2, "短い", cfg, now)


def _spy_scan_meta(monkeypatch):
    """Wrap discover.scan_meta with a call recorder; return the calls list."""
    calls = []
    real = discover.scan_meta
    monkeypatch.setattr(discover, "scan_meta",
                        lambda path: (calls.append(path) or real(path)))
    return calls


def test_scan_cache_hit_avoids_reread(tmp_path, write_jsonl, monkeypatch):
    rows = [{"type": "user", "cwd": "/p", "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "hi"}}]
    p = write_jsonl("a.jsonl", rows)
    calls = _spy_scan_meta(monkeypatch)
    cp = str(tmp_path / "scan_cache.json")
    c1 = ScanCache(cp); m1 = c1.get(p); c1.save()      # miss → scan_meta
    c2 = ScanCache(cp); m2 = c2.get(p); c2.save()      # hit → no scan_meta
    assert len(calls) == 1
    assert m1 == m2


def test_scan_cache_change_forces_rescan(tmp_path, write_jsonl, monkeypatch):
    p = write_jsonl("b.jsonl",
                    [{"type": "user", "message": {"role": "user", "content": "hi"}}])
    calls = _spy_scan_meta(monkeypatch)
    cp = str(tmp_path / "sc.json")
    c1 = ScanCache(cp); c1.get(p); c1.save()
    with open(p, "a", encoding="utf-8") as f:           # size (and mtime) change
        f.write(json.dumps({"type": "user",
                            "message": {"role": "user", "content": "more"}}) + "\n")
    c2 = ScanCache(cp); c2.get(p); c2.save()
    assert len(calls) == 2


def test_scan_cache_prunes_deleted(tmp_path, write_jsonl):
    p = write_jsonl("c.jsonl",
                    [{"type": "user", "message": {"role": "user", "content": "hi"}}])
    cp = str(tmp_path / "sc.json")
    c1 = ScanCache(cp); c1.get(p); c1.save()
    assert p in json.load(open(cp, encoding="utf-8"))
    # next run never sees p (file gone) → save drops the stale entry
    c2 = ScanCache(cp); c2.save()
    assert p not in json.load(open(cp, encoding="utf-8"))


def test_scan_cache_corrupt_is_tolerated(tmp_path, write_jsonl):
    cp = str(tmp_path / "sc.json")
    with open(cp, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    p = write_jsonl("d.jsonl",
                    [{"type": "user", "message": {"role": "user", "content": "hi"}}])
    c = ScanCache(cp)                                   # must not raise
    assert c.get(p).basename == "d.jsonl"


def test_iter_conversations_skips_unreadable(tmp_path, monkeypatch):
    scan = tmp_path / "scan"; scan.mkdir()
    for name in ("a.jsonl", "b.jsonl"):
        (scan / name).write_text(
            '{"type":"user","message":{"role":"user","content":"hi"}}\n',
            encoding="utf-8")
    cfgp = tmp_path / "c.json"
    cfgp.write_text(json.dumps({"scan_base": str(scan)}))
    cfg = load_config(str(cfgp))
    real = discover.scan_meta
    monkeypatch.setattr(discover, "scan_meta",
        lambda path: (_ for _ in ()).throw(OSError("gone"))
                     if path.endswith("a.jsonl") else real(path))
    bases = sorted(m.basename for m in iter_conversations(cfg))
    assert bases == ["b.jsonl"]
