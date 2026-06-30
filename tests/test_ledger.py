from transcript_organizer.ledger import Ledger, atomic_write_json
import json

def test_mark_and_persist(tmp_path):
    p = str(tmp_path / "ledger.json")
    led = Ledger(p)
    assert not led.is_processed("s1")
    led.mark("s1", {"label": "AIRouter"})
    assert led.is_processed("s1")
    # reload from disk
    assert Ledger(p).is_processed("s1")
    assert Ledger(p).all()["s1"]["label"] == "AIRouter"

def test_drop_removes_entry(tmp_path):
    p = str(tmp_path / "ledger.json")
    led = Ledger(p)
    led.mark("s1", {"label": "AIRouter"})
    led.mark("s2", {"label": "Other"})
    led.drop("s1")
    assert not led.is_processed("s1")
    assert led.is_processed("s2")
    # persisted to disk
    assert not Ledger(p).is_processed("s1")
    # dropping an unknown id is a no-op, not an error
    led.drop("nope")


def test_atomic_write(tmp_path):
    p = str(tmp_path / "x.json")
    atomic_write_json(p, {"a": 1})
    assert json.load(open(p))["a"] == 1
