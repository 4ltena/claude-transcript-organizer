import pytest
from transcript_organizer.providers.base import Provider, MockProvider
from transcript_organizer.providers import get_provider
from transcript_organizer.config import load_config


def test_mock_returns_findings():
    mp = MockProvider([{"kind": "decision", "text": "t", "confidence": 0.5}])
    out = mp.propose_findings("body", {})
    assert out["findings"][0]["text"] == "t"


def test_mock_fail_raises():
    with pytest.raises(RuntimeError):
        MockProvider(fail=True).propose_findings("b", {})


def test_get_provider_mock(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"provider": "mock"}))
    prov = get_provider(load_config(str(p)))
    assert isinstance(prov, Provider)
