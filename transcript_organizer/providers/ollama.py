import json
from .base import Provider
from . import _http

class OllamaProvider(Provider):
    def __init__(self, conf: dict):
        self.endpoint = conf["endpoint"]
        self.model = conf["model"]

    def propose_findings(self, text: str, schema: dict) -> dict:
        url = f"{self.endpoint}/api/chat"
        payload = {"model": self.model, "stream": False, "format": "json",
                   "messages": [{"role": "user", "content": text}]}
        resp = _http.post_json(url, {"Content-Type": "application/json"}, payload)
        return json.loads(resp["message"]["content"])
