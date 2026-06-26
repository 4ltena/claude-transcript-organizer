import json
import re
from .base import Provider
from . import _http

# 一部のローカルモデル(qwen3 等)は format:"json" でも本文を ```json ... ``` で
# 囲んで返す。json.loads の前に取り除く。フェンスが無ければそのまま返す。
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def _strip_code_fence(s: str) -> str:
    s = (s or "").strip()
    m = _FENCE.search(s)
    return m.group(1).strip() if m else s


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
        return json.loads(_strip_code_fence(resp["message"]["content"]))
