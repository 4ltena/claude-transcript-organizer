import json, urllib.request

def post_json(url: str, headers: dict, payload: dict, timeout: int = 60) -> dict:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"unsupported url scheme: {url}")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
