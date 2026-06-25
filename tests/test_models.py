from transcript_organizer.models import ConvMeta, Condensed, Target, Finding

def test_finding_defaults_and_fields():
    f = Finding(kind="decision", text="採用した", confidence=0.9,
                source="conv-title", src_ts="2026-06-25T00:00:00Z", label="AIRouter")
    assert f.kind == "decision"
    assert f.confidence == 0.9
    assert f.label == "AIRouter"

def test_target_and_condensed():
    t = Target(label="Webs__portfolio", root="/x/Webs/portfolio")
    assert t.label == "Webs__portfolio"
    c = Condensed(title=None, cwd="/x", first_ts=None, last_ts=None, nmsg=3, body="hi")
    assert c.nmsg == 3 and c.body == "hi"
