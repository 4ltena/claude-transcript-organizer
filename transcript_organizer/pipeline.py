import os, time, traceback
from collections import Counter
from .discover import iter_conversations, classify, ScanCache
from .condense import condense
from .route import route, label_to_root
from .ledger import Ledger
from .findings import FindingStore
from .render import render_markdown, update_handoff
from .extract import extract, ExtractionError


def current_protect(config) -> set:
    """Return session IDs that must never be processed (config list + env var)."""
    s = set(config.protect_session_ids)
    env = os.environ.get("CLAUDE_SESSION_ID")
    if env:
        s.add(env)
    return s


def _date() -> str:
    return time.strftime("%Y-%m-%d")


def _ev(event: str, cid: str, detail: str = "") -> str:
    """Format one English trace line as `HH:MM:SS · event · id · detail`."""
    line = f"{time.strftime('%H:%M:%S')} · {event:<7} · {cid}"
    return f"{line} · {detail}" if detail else line


def organize(config, provider, only_label=None, rebuild=False,
             dry_run=False, now_epoch=None, log=None, progress=None) -> dict:
    """Discover, condense, classify, extract, and render all unprocessed conversations.

    Args:
        config: Config object.
        provider: Provider used for LLM extraction.
        only_label: If set, restrict processing to this label only.
        rebuild: If True, ignore the ledger and reprocess already-marked sessions.
        dry_run: If True, perform discover/route only — nothing is written.
        now_epoch: Override for current time (float seconds since epoch).
        log: Optional callable(str). If given, emits a per-conversation English
            trace line (read / route / extract / skip / handoff) in the form
            `HH:MM:SS · event · id · detail`.
        progress: Optional callable(done, total). Called once per scanned
            transcript so a caller can render a progress bar / remaining count.

    Returns:
        dict with keys: processed, skipped, added, handoffs.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    tracing = callable(log)
    emit = log if tracing else (lambda _msg: None)
    prog = progress if callable(progress) else (lambda _d, _t: None)
    ledger = Ledger(os.path.join(config.data_dir, "ledger.json"))
    store = FindingStore(config.data_dir)
    protect = current_protect(config)
    skipped: dict[str, int] = {}
    touched: dict[str, str] = {}   # label -> root
    processed = added = 0

    def bump(flag: str) -> None:
        skipped[flag] = skipped.get(flag, 0) + 1

    scan_cache = ScanCache(os.path.join(config.data_dir, "scan_cache.json"))
    metas = list(iter_conversations(config, scan_cache))
    scan_cache.save()
    total = len(metas)

    def _process(meta) -> None:
        """Process one conversation. Any exception propagates to the per-item
        guard in the loop, which records it as `error` and moves on."""
        nonlocal processed, added
        if meta.sid in protect:
            bump("protected"); return
        if not rebuild and ledger.is_processed(meta.sid):
            bump("ledger"); return
        try:
            cd = condense(meta.path, config.condense_cap)
        except OSError as e:
            # The transcript vanished or became unreadable between the initial
            # scan and now (e.g. its project dir was deleted mid-run). Skip this
            # one instead of aborting the whole batch, so already-processed work
            # stays committed and the run can finish.
            emit(_ev("skip", meta.sid, f"missing (unreadable transcript): {e}"))
            bump("missing"); return
        truncated = "…[中略" in cd.body
        emit(_ev("read", meta.sid,
                 f'title={cd.title or "(untitled)"!r} cwd={cd.cwd} '
                 f'msgs={cd.nmsg} chars={len(cd.body)}'
                 f'{" truncated(head60%/tail40%)" if truncated else ""}'))
        flags = classify(meta, cd.body, config, now_epoch)
        if "active" in flags:
            emit(_ev("skip", meta.sid, "active (recently active, protected)"))
            bump("active"); return
        if "sidechain" in flags and not config.include_sidechain:
            emit(_ev("skip", meta.sid, "sidechain (subagent log)"))
            bump("sidechain"); return
        if "meta" in flags:
            emit(_ev("skip", meta.sid, "meta (this tool's own output)"))
            bump("meta"); return
        if "trivial" in flags:
            emit(_ev("skip", meta.sid, "trivial (too little content)"))
            bump("trivial"); return
        tgt = route(cd.cwd, config)
        emit(_ev("route", meta.sid, f"label={tgt.label} root={tgt.root}"))
        if only_label and tgt.label != only_label:
            emit(_ev("skip", meta.sid, f"other_label (!= {only_label})"))
            bump("other_label"); return
        if dry_run:
            emit(_ev("dry-run", meta.sid, "no extraction (read-only)"))
            processed += 1
            touched[tgt.label] = tgt.root
            return
        try:
            findings = extract(cd, provider, tgt.label, config.retries)
        except ExtractionError as e:
            emit(_ev("skip", meta.sid,
                     f"extract_failed after {config.retries} retries: {e}"))
            bump("extract_failed"); return
        new = store.merge(tgt.label, findings)
        added += new
        kinds = dict(Counter(f.kind for f in findings))
        emit(_ev("extract", meta.sid,
                 f"proposed={len(findings)} {kinds} new={new}"))
        ledger.mark(meta.sid, {
            "label": tgt.label,
            "convid": meta.sid,
            "src_ts": cd.last_ts,
            "processed_at": _date(),
        })
        touched[tgt.label] = tgt.root
        processed += 1

    for idx, meta in enumerate(metas, 1):
        try:
            _process(meta)
        except Exception as e:
            # One conversation hit an unexpected error (not a missing file or a
            # handled extraction failure). Record it and keep going so a single
            # bad transcript can't abort the whole batch.
            emit(_ev("error", meta.sid, f"{type(e).__name__}: {e}"))
            if tracing:
                # In verbose mode, follow the one-line summary with the full
                # traceback (indented) so frequent errors can be diagnosed.
                emit("  " + traceback.format_exc().rstrip().replace("\n", "\n  "))
            bump("error")
        prog(idx, total)

    handoffs: list[str] = []
    if not dry_run:
        for label, root in touched.items():
            block = render_markdown(store.load(label), label, _date())
            path = update_handoff(root, block)
            emit(_ev("handoff", label, path))
            handoffs.append(path)

    return {"processed": processed, "skipped": skipped,
            "added": added, "handoffs": handoffs}


def status(config) -> dict:
    """Return a summary of ledger/findings state for the current config.

    Returns:
        dict with keys: unprocessed, ledger, labels.
    """
    ledger = Ledger(os.path.join(config.data_dir, "ledger.json"))
    store = FindingStore(config.data_dir)
    # Read-only reporting: reuse the scan cache for speed but do not rewrite it.
    cache = ScanCache(os.path.join(config.data_dir, "scan_cache.json"))
    unprocessed = 0
    for meta in iter_conversations(config, cache):
        if not ledger.is_processed(meta.sid):
            unprocessed += 1
    fdir = os.path.join(config.data_dir, "findings")
    labels: dict[str, int] = {}
    if os.path.isdir(fdir):
        for fn in os.listdir(fdir):
            if fn.endswith(".json"):
                labels[fn[:-5]] = len(store.load(fn[:-5]))
    return {"unprocessed": unprocessed, "ledger": len(ledger.all()),
            "labels": labels}


def render(config, only_label=None, dry_run=False) -> dict:
    """Re-render HANDOFF blocks from persisted findings, without the LLM.

    Recovers HANDOFFs that organize never wrote (interrupted before its final
    render step) or left stale. Each label's output root is recovered from the
    label via route.label_to_root. A label whose root directory no longer
    exists is skipped ("missing_root") rather than recreated.

    Args:
        config: Config object.
        only_label: If set, render this label only.
        dry_run: If True, count what would be rendered but write nothing.

    Returns:
        dict with keys: rendered, handoffs, skipped.
    """
    store = FindingStore(config.data_dir)
    fdir = os.path.join(config.data_dir, "findings")
    skipped: dict[str, int] = {}
    handoffs: list[str] = []
    rendered = 0

    def bump(flag: str) -> None:
        skipped[flag] = skipped.get(flag, 0) + 1

    if not os.path.isdir(fdir):
        return {"rendered": 0, "handoffs": [], "skipped": skipped}

    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json"):
            continue
        label = fn[:-5]
        if only_label and label != only_label:
            continue
        records = store.load(label)
        if not records:
            bump("empty"); continue
        root = label_to_root(label, config)
        if not os.path.isdir(root):
            bump("missing_root"); continue
        rendered += 1
        if dry_run:
            continue
        block = render_markdown(records, label, _date())
        handoffs.append(update_handoff(root, block))

    return {"rendered": rendered, "handoffs": handoffs, "skipped": skipped}
