import os, json, time
from transcript_organizer.config import load_config
from transcript_organizer.providers.base import MockProvider
from transcript_organizer.pipeline import organize, status, current_protect, render
from transcript_organizer.findings import FindingStore
from transcript_organizer.models import Finding


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
    pl.iter_conversations = lambda _c, _cache=None: iter([gone, good_meta])
    try:
        summary = organize(cfg, prov, now_epoch=time.time() + 10**9)
    finally:
        pl.iter_conversations = orig
    # missing one is skipped, the good one still gets processed (no crash)
    assert summary["skipped"].get("missing", 0) == 1
    assert summary["processed"] == 1
    assert summary["added"] == 1


def test_organize_uses_scan_cache(tmp_path, write_jsonl, monkeypatch):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    src = write_jsonl("sess.jsonl", rows)
    os.replace(src, scan / "enc" / "sess.jsonl")
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    import transcript_organizer.discover as discover
    calls = []
    real = discover.scan_meta
    monkeypatch.setattr(discover, "scan_meta",
                        lambda p: (calls.append(p) or real(p)))
    organize(cfg, prov, now_epoch=time.time() + 10**9)
    organize(cfg, prov, now_epoch=time.time() + 10**9)
    # cache persisted, and the unchanged transcript is scanned only once total
    assert os.path.isfile(os.path.join(cfg.data_dir, "scan_cache.json"))
    assert len(calls) == 1


def test_organize_unexpected_error_does_not_abort(tmp_path, write_jsonl, monkeypatch):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    cwd = str(proj / "Webs" / "portfolio")
    rows = [{"type": "user", "cwd": cwd, "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    os.replace(write_jsonl("bad.jsonl", rows), scan / "enc" / "bad.jsonl")
    os.replace(write_jsonl("ok.jsonl", rows), scan / "enc" / "ok.jsonl")
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    import transcript_organizer.pipeline as pl
    real_classify = pl.classify
    def boom(meta, body, config, now):
        if meta.basename == "bad.jsonl":
            raise RuntimeError("kaboom")          # unexpected, non-OSError/Extraction
        return real_classify(meta, body, config, now)
    monkeypatch.setattr(pl, "classify", boom)
    summary = organize(cfg, prov, now_epoch=time.time() + 10**9)
    # one conversation blew up but the batch finished and processed the other
    assert summary["skipped"].get("error", 0) == 1
    assert summary["processed"] == 1


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


def test_status_reuses_scan_cache_without_writing(tmp_path, write_jsonl, monkeypatch):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    rows = [{"type": "user", "cwd": str(proj / "Webs" / "portfolio"),
             "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "ポートフォリオの要件はAとB。"*5}}]
    os.replace(write_jsonl("sess.jsonl", rows), scan / "enc" / "sess.jsonl")
    cfg = _cfg(tmp_path, scan, proj)
    prov = MockProvider([{"kind": "design_requirement", "text": "要件AとB", "confidence": 0.9}])
    organize(cfg, prov, now_epoch=time.time() + 10**9)   # warms cache
    cache_file = os.path.join(cfg.data_dir, "scan_cache.json")
    mtime_before = os.path.getmtime(cache_file)
    import transcript_organizer.discover as discover
    calls = []
    real = discover.scan_meta
    monkeypatch.setattr(discover, "scan_meta",
                        lambda p: (calls.append(p) or real(p)))
    status(cfg)
    assert calls == []                                   # cache hit, no rescans
    assert os.path.getmtime(cache_file) == mtime_before  # status does not write


def _seed_finding(cfg, label, text="要件AとB"):
    FindingStore(cfg.data_dir).merge(label, [Finding(
        kind="design_requirement", text=text, confidence=0.9,
        source="src", src_ts="2026-06-25T00:00:00Z", label=label)])


def test_render_writes_handoff_from_findings(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    cfg = _cfg(tmp_path, scan, proj)
    _seed_finding(cfg, "Webs__portfolio")
    # findings exist but no HANDOFF yet (e.g. organize was interrupted before render)
    r = render(cfg)
    ho = proj / "Webs" / "portfolio" / "docs" / "HANDOFF.md"
    assert ho.is_file()
    assert "要件AとB" in ho.read_text(encoding="utf-8")
    assert r["rendered"] == 1
    assert ho.as_posix() in [p.replace("\\", "/") for p in r["handoffs"]]


def test_render_project_filter(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    proj = tmp_path / "projects"
    (proj / "Webs" / "portfolio").mkdir(parents=True)
    (proj / "AIRouter").mkdir(parents=True)
    cfg = _cfg(tmp_path, scan, proj)
    _seed_finding(cfg, "Webs__portfolio")
    _seed_finding(cfg, "AIRouter")
    r = render(cfg, only_label="AIRouter")
    assert r["rendered"] == 1
    assert (proj / "AIRouter" / "docs" / "HANDOFF.md").is_file()
    assert not (proj / "Webs" / "portfolio" / "docs" / "HANDOFF.md").exists()


def test_render_dry_run_writes_nothing(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    cfg = _cfg(tmp_path, scan, proj)
    _seed_finding(cfg, "Webs__portfolio")
    r = render(cfg, dry_run=True)
    assert r["handoffs"] == []
    assert not (proj / "Webs" / "portfolio" / "docs" / "HANDOFF.md").exists()


def test_render_skips_missing_root(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    proj = tmp_path / "projects"; proj.mkdir()
    cfg = _cfg(tmp_path, scan, proj)
    _seed_finding(cfg, "Ghost")              # proj/Ghost does not exist
    r = render(cfg)
    assert r["rendered"] == 0
    assert r["skipped"].get("missing_root", 0) == 1
    assert not (proj / "Ghost" / "docs" / "HANDOFF.md").exists()


def test_render_skips_empty_findings(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    proj = tmp_path / "projects"; (proj / "Webs" / "portfolio").mkdir(parents=True)
    cfg = _cfg(tmp_path, scan, proj)
    FindingStore(cfg.data_dir).merge("Webs__portfolio", [])   # writes an empty []
    r = render(cfg)
    assert r["rendered"] == 0
    assert r["skipped"].get("empty", 0) == 1


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
