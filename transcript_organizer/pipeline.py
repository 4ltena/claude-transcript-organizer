import os, time
from collections import Counter
from .discover import iter_conversations, classify, ScanCache
from .condense import condense
from .route import route
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
    emit = log if callable(log) else (lambda _msg: None)
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
    for idx, meta in enumerate(metas, 1):
        if meta.sid in protect:
            bump("protected"); prog(idx, total); continue
        if not rebuild and ledger.is_processed(meta.sid):
            bump("ledger"); prog(idx, total); continue
        try:
            cd = condense(meta.path, config.condense_cap)
        except OSError as e:
            # The transcript vanished or became unreadable between the initial
            # scan and now (e.g. its project dir was deleted mid-run). Skip this
            # one instead of aborting the whole batch, so already-processed work
            # stays committed and the run can finish.
            emit(_ev("skip", meta.sid, f"missing (unreadable transcript): {e}"))
            bump("missing"); prog(idx, total); continue
        truncated = "…[中略" in cd.body
        emit(_ev("read", meta.sid,
                 f'title={cd.title or "(untitled)"!r} cwd={cd.cwd} '
                 f'msgs={cd.nmsg} chars={len(cd.body)}'
                 f'{" truncated(head60%/tail40%)" if truncated else ""}'))
        flags = classify(meta, cd.body, config, now_epoch)
        if "active" in flags:
            emit(_ev("skip", meta.sid, "active (recently active, protected)"))
            bump("active"); prog(idx, total); continue
        if "sidechain" in flags and not config.include_sidechain:
            emit(_ev("skip", meta.sid, "sidechain (subagent log)"))
            bump("sidechain"); prog(idx, total); continue
        if "meta" in flags:
            emit(_ev("skip", meta.sid, "meta (this tool's own output)"))
            bump("meta"); prog(idx, total); continue
        if "trivial" in flags:
            emit(_ev("skip", meta.sid, "trivial (too little content)"))
            bump("trivial"); prog(idx, total); continue
        tgt = route(cd.cwd, config)
        emit(_ev("route", meta.sid, f"label={tgt.label} root={tgt.root}"))
        if only_label and tgt.label != only_label:
            emit(_ev("skip", meta.sid, f"other_label (!= {only_label})"))
            bump("other_label"); prog(idx, total); continue
        if dry_run:
            emit(_ev("dry-run", meta.sid, "no extraction (read-only)"))
            processed += 1
            touched[tgt.label] = tgt.root
            prog(idx, total); continue
        try:
            findings = extract(cd, provider, tgt.label, config.retries)
        except ExtractionError as e:
            emit(_ev("skip", meta.sid,
                     f"extract_failed after {config.retries} retries: {e}"))
            bump("extract_failed"); prog(idx, total); continue
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
    unprocessed = 0
    for meta in iter_conversations(config):
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
