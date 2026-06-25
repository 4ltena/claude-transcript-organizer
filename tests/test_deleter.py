import os, json, time
from transcript_organizer.config import load_config
from transcript_organizer.ledger import Ledger
from transcript_organizer.deleter import plan_deletion, execute


def _setup(tmp_path, write_jsonl):
    scan = tmp_path / "scan"; (scan / "enc").mkdir(parents=True)
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"scan_base": str(scan), "data_dir": str(tmp_path / "data"),
                             "protect_recent_minutes": 0}))
    cfg = load_config(str(p))
    rows = [{"type": "user", "cwd": "/p", "timestamp": "2026-06-25T00:00:00Z",
             "message": {"role": "user", "content": "x"*500}}]
    a = write_jsonl("aaa.jsonl", rows); os.replace(a, scan / "enc" / "aaa.jsonl")
    b = write_jsonl("bbb.jsonl", rows); os.replace(b, scan / "enc" / "bbb.jsonl")
    # mark only aaa as processed
    Ledger(os.path.join(cfg.data_dir, "ledger.json")).mark("aaa", {"label": "P"})
    return cfg, scan


def test_plan_only_processed(tmp_path, write_jsonl):
    cfg, scan = _setup(tmp_path, write_jsonl)
    plan = plan_deletion(cfg, now_epoch=time.time() + 10**9)
    names = sorted(os.path.basename(p) for p in plan["delete"])
    assert names == ["aaa.jsonl"]            # bbb not in ledger -> protected


def test_execute_moves_to_trash(tmp_path, write_jsonl):
    cfg, scan = _setup(tmp_path, write_jsonl)
    plan = plan_deletion(cfg, now_epoch=time.time() + 10**9)
    res = execute(plan, cfg, yes=True)
    assert res["deleted"] == 1
    assert not (scan / "enc" / "aaa.jsonl").exists()       # moved out
    assert (scan / "enc" / "bbb.jsonl").exists()           # untouched
    # trash retains it
    trash = os.path.join(cfg.data_dir, "trash")
    found = []
    for r, _, fs in os.walk(trash):
        found += [f for f in fs if f == "aaa.jsonl"]
    assert found == ["aaa.jsonl"]


def test_dry_run_moves_nothing(tmp_path, write_jsonl):
    cfg, scan = _setup(tmp_path, write_jsonl)
    plan = plan_deletion(cfg, now_epoch=time.time() + 10**9)
    res = execute(plan, cfg, yes=False)
    assert res["deleted"] == 0
    assert (scan / "enc" / "aaa.jsonl").exists()
