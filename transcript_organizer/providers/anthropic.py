import os
from .base import Provider
from . import _http

# NOTE: confirm model id / API shape via the claude-api skill before relying in prod.
class AnthropicProvider(Provider):
    def __init__(self, conf: dict):
        self.model = conf["model"]
        self.key_env = conf["api_key_env"]

    def propose_findings(self, text: str, schema: dict) -> dict:
        key = os.environ.get(self.key_env)
        url = "https://api.anthropic.com/v1/messages"
        tool = {"name": "emit", "description": "Emit findings",
                "input_schema": schema}
        payload = {"model": self.model, "max_tokens": 2048,
                   "tools": [tool], "tool_choice": {"type": "tool", "name": "emit"},
                   "messages": [{"role": "user", "content": text}]}
        headers = {"x-api-key": key or "", "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
        resp = _http.post_json(url, headers, payload)
        for block in resp.get("content", []):
            if block.get("type") == "tool_use":
                return block["input"]
        return {"findings": []}
