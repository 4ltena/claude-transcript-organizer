from transcript_organizer.models import Finding
from transcript_organizer.findings import FindingStore, normalize_id


def test_normalize_id_stable_across_whitespace():
    a = normalize_id("decision", "採用した  方式")
    b = normalize_id("decision", "採用した 方式")
    assert a == b


def test_merge_dedup_and_source_accumulation(tmp_path):
    store = FindingStore(str(tmp_path))
    f1 = Finding("decision", "Xを採用", 0.9, "conv-A", "2026-06-20T00:00:00Z", "P")
    f1b = Finding("decision", "Xを採用", 0.8, "conv-B", "2026-06-25T00:00:00Z", "P")
    f2 = Finding("next_step", "Yをやる", 0.7, "conv-A", "2026-06-20T00:00:00Z", "P")
    assert store.merge("P", [f1, f2]) == 2
    assert store.merge("P", [f1b]) == 0          # duplicate text -> no new id
    recs = store.load("P")
    assert len(recs) == 2
    dec = [r for r in recs if r["kind"] == "decision"][0]
    assert set(dec["src_titles"]) == {"conv-A", "conv-B"}
    assert dec["last_seen"] == "2026-06-25T00:00:00Z"


def test_merge_src_ts_list_no_duplicates(tmp_path):
    store = FindingStore(str(tmp_path))
    ts = "2026-06-20T00:00:00Z"
    f = Finding("decision", "Xを採用", 0.9, "conv-A", ts, "P")
    # Merge the same finding (same src_ts) twice — src_ts_list must stay length 1
    store.merge("P", [f])
    store.merge("P", [f])
    recs = store.load("P")
    dec = [r for r in recs if r["kind"] == "decision"][0]
    assert dec["src_ts_list"].count(ts) == 1
    assert len(dec["src_ts_list"]) == 1
