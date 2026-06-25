import pytest
from transcript_organizer.providers import gemini, anthropic, openai, ollama
from transcript_organizer.providers import _http

def _patch(monkeypatch, response):
    monkeypatch.setattr(_http, "post_json", lambda *a, **k: response)

def test_gemini_parses(monkeypatch):
    # Gemini returns candidates[].content.parts[].text holding JSON string
    _patch(monkeypatch, {"candidates": [{"content": {"parts": [
        {"text": '{"findings":[{"kind":"decision","text":"t","confidence":0.6}]}'}]}}]})
    p = gemini.GeminiProvider({"api_key_env": "X", "model": "m"})
    monkeypatch.setenv("X", "key")
    out = p.propose_findings("body", {"type": "object"})
    assert out["findings"][0]["text"] == "t"

def test_gemini_raises_if_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_MISSING_KEY", raising=False)
    p = gemini.GeminiProvider({"api_key_env": "GEMINI_MISSING_KEY", "model": "m"})
    with pytest.raises(RuntimeError, match="GEMINI_MISSING_KEY is not set"):
        p.propose_findings("body", {})

def test_openai_parses(monkeypatch):
    _patch(monkeypatch, {"choices": [{"message": {"content":
        '{"findings":[{"kind":"next_step","text":"y","confidence":0.5}]}'}}]})
    monkeypatch.setenv("OAI", "key")
    out = openai.OpenAIProvider({"api_key_env": "OAI", "model": "m"}).propose_findings("b", {})
    assert out["findings"][0]["kind"] == "next_step"

def test_openai_raises_if_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_MISSING_KEY", raising=False)
    p = openai.OpenAIProvider({"api_key_env": "OPENAI_MISSING_KEY", "model": "m"})
    with pytest.raises(RuntimeError, match="OPENAI_MISSING_KEY is not set"):
        p.propose_findings("body", {})

def test_ollama_parses(monkeypatch):
    _patch(monkeypatch, {"message": {"content":
        '{"findings":[{"kind":"gotcha","text":"z","confidence":0.4}]}'}})
    out = ollama.OllamaProvider({"endpoint": "http://x", "model": "m"}).propose_findings("b", {})
    assert out["findings"][0]["kind"] == "gotcha"

def test_anthropic_parses(monkeypatch):
    # tool_use structured output: content[].input holds the object
    _patch(monkeypatch, {"content": [{"type": "tool_use", "name": "emit",
        "input": {"findings": [{"kind": "completed", "text": "done", "confidence": 0.9}]}}]})
    monkeypatch.setenv("ANT", "key")
    out = anthropic.AnthropicProvider({"api_key_env": "ANT", "model": "m"}).propose_findings("b", {})
    assert out["findings"][0]["text"] == "done"

def test_post_json_rejects_non_http():
    with pytest.raises(ValueError, match="unsupported url scheme"):
        _http.post_json("file:///etc/passwd", {}, {})
