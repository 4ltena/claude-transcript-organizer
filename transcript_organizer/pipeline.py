import os, time
from .discover import iter_conversations, classify
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


def organize(config, provider, only_label=None, rebuild=False,
             dry_run=False, now_epoch=None) -> dict:
    """Discover, condense, classify, extract, and render all unprocessed conversations.

    Args:
        config: Config object.
        provider: Provider used for LLM extraction.
        only_label: If set, restrict processing to this label only.
        rebuild: If True, ignore the ledger and reprocess already-marked sessions.
        dry_run: If True, perform discover/route only — nothing is written.
        now_epoch: Override for current time (float seconds since epoch).

    Returns:
        dict with keys: processed, skipped, added, handoffs.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    ledger = Ledger(os.path.join(config.data_dir, "ledger.json"))
    store = FindingStore(config.data_dir)
    protect = current_protect(config)
    skipped: dict[str, int] = {}
    touched: dict[str, str] = {}   # label -> root
    processed = added = 0

    def bump(flag: str) -> None:
        skipped[flag] = skipped.get(flag, 0) + 1

    for meta in iter_conversations(config):
        if meta.sid in protect:
            bump("protected")
            continue
        if not rebuild and ledger.is_processed(meta.sid):
            bump("ledger")
            continue
        cd = condense(meta.path, config.condense_cap)
        flags = classify(meta, cd.body, config, now_epoch)
        if "active" in flags:
            bump("active")
            continue
        if "sidechain" in flags and not config.include_sidechain:
            bump("sidechain")
            continue
        if "meta" in flags:
            bump("meta")
            continue
        if "trivial" in flags:
            bump("trivial")
            continue
        tgt = route(cd.cwd, config)
        if only_label and tgt.label != only_label:
            bump("other_label")
            continue
        if dry_run:
            processed += 1
            touched[tgt.label] = tgt.root
            continue
        try:
            findings = extract(cd, provider, tgt.label, config.retries)
        except ExtractionError:
            bump("extract_failed")
            continue
        added += store.merge(tgt.label, findings)
        ledger.mark(meta.sid, {
            "label": tgt.label,
            "convid": meta.sid,
            "src_ts": cd.last_ts,
            "processed_at": _date(),
        })
        touched[tgt.label] = tgt.root
        processed += 1

    handoffs: list[str] = []
    if not dry_run:
        for label, root in touched.items():
            block = render_markdown(store.load(label), label, _date())
            handoffs.append(update_handoff(root, block))

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
