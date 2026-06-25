from transcript_organizer.render import render_markdown, update_handoff, BEGIN, END

RECS = [
    {"kind": "design_requirement", "text": "要件A", "src_titles": ["conv1"], "last_seen": "2026-06-20T00:00:00Z"},
    {"kind": "completed", "text": "古い完了", "src_titles": ["old"], "last_seen": "2026-06-01T00:00:00Z"},
    {"kind": "completed", "text": "新しい完了", "src_titles": ["new"], "last_seen": "2026-06-25T00:00:00Z"},
]

def test_render_groups_and_status_recency():
    md = render_markdown(RECS, "AIRouter", "2026-06-25")
    assert md.startswith(BEGIN)
    assert md.rstrip().endswith(END)
    assert "要件A（出典: conv1）" in md
    # newest completed appears before older one
    assert md.index("新しい完了") < md.index("古い完了")

def test_update_handoff_creates_and_preserves(tmp_path):
    root = str(tmp_path / "proj")
    block1 = render_markdown(RECS, "P", "2026-06-25")
    path = update_handoff(root, block1)
    # prepend human prose, then re-render with new block
    content = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write("# 人間の記述\n\n大事なメモ\n\n" + content)
    block2 = render_markdown(RECS[:1], "P", "2026-06-26")
    update_handoff(root, block2)
    final = open(path, encoding="utf-8").read()
    assert "大事なメモ" in final          # human prose preserved
    assert final.count(BEGIN) == 1         # exactly one managed block
    assert "新しい完了" not in final        # block replaced, not duplicated
