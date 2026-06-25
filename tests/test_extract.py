import pytest
from transcript_organizer.models import Condensed
from transcript_organizer.providers.base import MockProvider
from transcript_organizer.extract import extract, ExtractionError, FINDINGS_SCHEMA

C = Condensed(title="会話A", cwd="/p", first_ts="t0", last_ts="t1", nmsg=3, body="本文")

def test_extract_maps_to_findings():
    prov = MockProvider([
        {"kind": "decision", "text": "Xを採用", "confidence": 0.9},
        {"kind": "BOGUS", "text": "ignored", "confidence": 0.1},   # invalid kind dropped
        {"kind": "next_step", "text": "", "confidence": 0.5},      # empty text dropped
    ])
    out = extract(C, prov, "AIRouter")
    assert len(out) == 1
    assert out[0].kind == "decision"
    assert out[0].source == "会話A"
    assert out[0].src_ts == "t1"
    assert out[0].label == "AIRouter"

def test_extract_raises_after_retries():
    with pytest.raises(ExtractionError):
        extract(C, MockProvider(fail=True), "P", retries=1)

def test_schema_is_object():
    assert FINDINGS_SCHEMA["type"] == "object"
