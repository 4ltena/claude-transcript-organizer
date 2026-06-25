import os, time, shutil
from .discover import iter_conversations, classify
from .condense import condense
from .ledger import Ledger
from .pipeline import current_protect


def plan_deletion(config, now_epoch=None) -> dict:
    """Determine which conversations are safe to delete.

    A path is deletable only if:
    - ledger.is_processed(sid) is True
    - not in current_protect (session-id / env guard)
    - not classified as 'active' (recently modified)
    - not classified as 'sidechain'

    exclude_globs are already applied by iter_conversations.

    Args:
        config: Config object.
        now_epoch: Override for current time (float seconds since epoch).

    Returns:
        dict with keys:
            "delete": list of absolute paths that are safe to delete
            "protect": dict mapping reason string to count of protected paths
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    ledger = Ledger(os.path.join(config.data_dir, "ledger.json"))
    protect_ids = current_protect(config)
    delete, protect = [], {}

    def bump(reason):
        protect[reason] = protect.get(reason, 0) + 1

    for meta in iter_conversations(config):   # exclude_globs already applied
        if meta.sid in protect_ids:
            bump("session_id"); continue
        if not ledger.is_processed(meta.sid):
            bump("unprocessed"); continue
        if meta.is_sidechain:
            bump("sidechain"); continue
        cd = condense(meta.path, config.condense_cap)
        flags = classify(meta, cd.body, config, now_epoch)
        if "active" in flags:
            bump("active"); continue
        if "sidechain" in flags:          # defense-in-depth
            bump("sidechain"); continue
        delete.append(meta.path)
    return {"delete": delete, "protect": protect}


def execute(plan, config, yes: bool = False) -> dict:
    """Execute a deletion plan by moving files to trash.

    When yes=False (dry-run), no files are moved and "deleted" is 0.
    When yes=True, files are MOVED (never hard-deleted) to
    data/trash/<date>/ preserving their relative path under scan_base.

    Args:
        plan: dict returned by plan_deletion.
        config: Config object.
        yes: If False, perform a dry-run (no moves). Default False.

    Returns:
        dict with keys:
            "deleted": number of files actually moved (0 for dry-run)
            "would_delete": (dry-run only) number of files that would be moved
    """
    if not yes:
        return {"deleted": 0, "would_delete": len(plan["delete"])}
    date = time.strftime("%Y-%m-%d")
    trash_root = os.path.join(config.data_dir, "trash", date)
    base = config.scan_base
    real_base = os.path.realpath(base)
    moved = 0
    for path in plan["delete"]:
        if not os.path.realpath(path).startswith(real_base + os.sep):
            continue  # パスが scan_base の外にある（通常は発生しない）
        rel = os.path.relpath(path, base)
        dst = os.path.join(trash_root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(path, dst)
        moved += 1
    return {"deleted": moved}


def gc_trash(config, now_epoch=None) -> int:
    """Remove trash subdirectories older than trash_retention_days.

    Only top-level date-named directories under data/trash/ are inspected.
    Uses directory mtime for age comparison.

    Args:
        config: Config object. Uses config.delete["trash_retention_days"].
        now_epoch: Override for current time (float seconds since epoch).

    Returns:
        Number of directories removed.
    """
    now_epoch = now_epoch if now_epoch is not None else time.time()
    trash = os.path.join(config.data_dir, "trash")
    if not os.path.isdir(trash):
        return 0
    cutoff = now_epoch - config.delete["trash_retention_days"] * 86400
    removed = 0
    for name in os.listdir(trash):
        d = os.path.join(trash, name)
        if os.path.isdir(d) and os.path.getmtime(d) < cutoff:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed
