from transcript_organizer.condense import condense

def test_keeps_text_drops_thinking_and_tool_result(write_jsonl):
    rows = [
        {"type": "user", "cwd": "/proj", "timestamp": "2026-06-25T01:00:00Z",
         "message": {"role": "user", "content": "要件はXです"}},
        {"type": "assistant", "timestamp": "2026-06-25T01:01:00Z",
         "message": {"role": "assistant", "content": [
             {"type": "thinking", "text": "secret reasoning"},
             {"type": "text", "text": "了解しました"},
             {"type": "tool_use", "name": "Write", "input": {"file_path": "/proj/a.py"}},
             {"type": "tool_result", "content": "ok body that should be dropped"},
         ]}},
    ]
    c = condense(write_jsonl("s.jsonl", rows))
    assert c.cwd == "/proj"
    assert "要件はXです" in c.body
    assert "了解しました" in c.body
    assert "secret reasoning" not in c.body
    assert "ok body that should be dropped" not in c.body
    assert "[tool:Write] /proj/a.py" in c.body
    assert c.nmsg == 2
    assert c.first_ts == "2026-06-25T01:00:00Z"
    assert c.last_ts == "2026-06-25T01:01:00Z"

def test_cap_truncation(write_jsonl):
    big = "あ" * 50000
    rows = [{"type": "user", "cwd": "/p", "message": {"role": "user", "content": big}}]
    c = condense(write_jsonl("b.jsonl", rows), cap=1000)
    assert len(c.body) < 2000
    assert "中略" in c.body
