import os, time
from transcript_organizer.config import load_config
from transcript_organizer.discover import scan_meta, classify

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
