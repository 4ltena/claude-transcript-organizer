import os, json, time
from transcript_organizer.config import load_config
from transcript_organizer.providers.base import MockProvider
from transcript_organizer.pipeline import organize, status, current_protect


def _cfg(tmp_path, scan, proj):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "scan_base": str(scan), "roots": {"PROJECTS": str(proj)},
        "archive_root": str(proj / "_conversation-archive"),
        "data_dir": str(tmp_path / "data"),
        "protect_recent_minutes": 0,   # don't protect by recency in test
        "min_msgs": 1,                 # 1 message is enough (default 2 would trivial-filter)
        "containers": ["Webs"],
    }))
    return load_config(str(p))


def test_organize_end_to_end(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    # place transcript under scan_base
    src = write_jsonl("sess.jsonl", rows)
    dst = scan / "enc" / "sess.jsonl"; os.replace(src, dst)
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    summary = organize(cfg, prov, now_epoch=time.time() + 10**9)
    assert summary["processed"] == 1
    assert summary["added"] == 1
    ho = proj / "Webs" / "portfolio" / "docs" / "HANDOFF.md"
    assert ho.is_file()
    assert "要件AとB" in ho.read_text(encoding="utf-8")
    # second run is incremental: nothing new
    s2 = organize(cfg, prov, now_epoch=time.time() + 10**9)
    assert s2["processed"] == 0


def test_organize_dry_run(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    src = write_jsonl("sess.jsonl", rows)
    dst = scan / "enc" / "sess.jsonl"; os.replace(src, dst)
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    summary = organize(cfg, prov, dry_run=True, now_epoch=time.time() + 10**9)
    # dry_run: discover/route only, nothing written
    assert summary["processed"] == 1
    assert summary["added"] == 0
    assert summary["handoffs"] == []
    ho = proj / "Webs" / "portfolio" / "docs" / "HANDOFF.md"
    assert not ho.exists()


def test_organize_extraction_failure(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    src = write_jsonl("sess.jsonl", rows)
    dst = scan / "enc" / "sess.jsonl"; os.replace(src, dst)
    cfg = _cfg(tmp_path, scan, proj)
    # fail=True causes ExtractionError
    prov = MockProvider(fail=True)
    summary = organize(cfg, prov, now_epoch=time.time() + 10**9)
    # extraction failed: skipped, ledger NOT marked
    assert summary["processed"] == 0
    assert summary["skipped"].get("extract_failed", 0) == 1


def test_organize_missing_transcript_does_not_abort(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    cwd = str(proj / "Webs" / "portfolio")
    # two transcripts; the first one is deleted after the scan snapshot but
    # before condense runs (simulated by patching iter_conversations below)
    rows = [{"type": "user", "cwd": cwd, "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    good = scan / "enc" / "good.jsonl"
    os.replace(write_jsonl("good.jsonl", rows), good)
    # a meta pointing at a path that does not exist on disk
    from transcript_organizer.models import ConvMeta
    from transcript_organizer import pipeline as pl
    gone = ConvMeta(path=str(scan / "enc" / "gone.jsonl"), sid="gone",
                    cwd=cwd, first_ts="2026-06-25T00:00:00Z",
                    last_ts="2026-06-25T00:00:00Z", nmsg=1,
                    is_sidechain=False, basename="gone.jsonl")
    from transcript_organizer.discover import scan_meta
    good_meta = scan_meta(str(good))
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    orig = pl.iter_conversations
    pl.iter_conversations = lambda _c: iter([gone, good_meta])
    try:
        summary = organize(cfg, prov, now_epoch=time.time() + 10**9)
    finally:
        pl.iter_conversations = orig
    # missing one is skipped, the good one still gets processed (no crash)
    assert summary["skipped"].get("missing", 0) == 1
    assert summary["processed"] == 1
    assert summary["added"] == 1


def test_status(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    src = write_jsonl("sess.jsonl", rows)
    dst = scan / "enc" / "sess.jsonl"; os.replace(src, dst)
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    # before processing
    s0 = status(cfg)
    assert s0["unprocessed"] == 1
    assert s0["ledger"] == 0
    organize(cfg, prov, now_epoch=time.time() + 10**9)
    # after processing
    s1 = status(cfg)
    assert s1["unprocessed"] == 0
    assert s1["ledger"] == 1
    assert s1["labels"].get("Webs__portfolio", 0) == 1


def test_current_protect(tmp_path):
    cfg = _cfg(tmp_path, tmp_path / "scan", tmp_path / "proj")
    protect = current_protect(cfg)
    # no env var set: only protect_session_ids (empty by default)
    assert isinstance(protect, set)
    os.environ["CLAUDE_SESSION_ID"] = "test-sid-xyz"
    try:
        protect2 = current_protect(cfg)
        assert "test-sid-xyz" in protect2
    finally:
        del os.environ["CLAUDE_SESSION_ID"]
