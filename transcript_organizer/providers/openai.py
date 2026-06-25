import os, json
from .base import Provider
from . import _http

class OpenAIProvider(Provider):
    def __init__(self, conf: dict):
        self.model = conf["model"]
        self.key_env = conf["api_key_env"]

    def propose_findings(self, text: str, schema: dict) -> dict:
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"{self.key_env} is not set")
        url = "https://api.openai.com/v1/chat/completions"
        payload = {"model": self.model,
                   "messages": [{"role": "user", "content": text}],
                   "response_format": {"type": "json_object"}}
        resp = _http.post_json(url, {"Authorization": f"Bearer {key}",
                                     "Content-Type": "application/json"}, payload)
        return json.loads(resp["choices"][0]["message"]["content"])
