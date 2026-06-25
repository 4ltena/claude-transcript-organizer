import json
from .base import Provider
from . import _http

class OllamaProvider(Provider):
    def __init__(self, conf: dict):
        self.endpoint = conf["endpoint"]
        self.model = conf["model"]
        # Optional: thinking models (gemma3/qwen3 等) は既定で大量の thinking を返し、
        # 抽出に不要なうえ WSL 越しの転送を不安定にする。conf に "think" があれば送る。
        self.think = conf.get("think")

    def propose_findings(self, text: str, schema: dict) -> dict:
        url = f"{self.endpoint}/api/chat"
        payload = {"model": self.model, "stream": False, "format": "json",
                   "messages": [{"role": "user", "content": text}]}
        if self.think is not None:
            payload["think"] = self.think
        resp = _http.post_json(url, {"Content-Type": "application/json"}, payload)
        return json.loads(resp["message"]["content"])
