import os, json
from .base import Provider
from . import _http

class GeminiProvider(Provider):
    def __init__(self, conf: dict):
        self.model = conf["model"]
        self.key_env = conf["api_key_env"]

    def propose_findings(self, text: str, schema: dict) -> dict:
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"{self.key_env} is not set")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"response_mime_type": "application/json",
                                 "response_schema": schema},
        }
        resp = _http.post_json(url, {"Content-Type": "application/json",
                                     "x-goog-api-key": key}, payload)
        raw = resp["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw)
