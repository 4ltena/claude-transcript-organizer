import json, re
from collections import Counter
from .models import Condensed

def _trunc(s, n):
    s = s or ""
    return s if len(s) <= n else s[:n] + f" …[+{len(s)-n}c]"

def _tool_line(b):
    name = b.get("name", "?")
    inp = b.get("input", {}) or {}
    key = ""
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Read"):
        key = inp.get("file_path") or inp.get("notebook_path") or ""
    elif name == "Bash":
        key = _trunc((inp.get("command") or "").replace("\n", " ; "), 180)
    elif name in ("Grep", "Glob"):
        key = (inp.get("pattern") or "") + " " + (inp.get("path") or inp.get("glob") or "")
    elif name in ("Task", "Agent"):
        key = _trunc(inp.get("description") or inp.get("prompt") or "", 120)
    else:
        for k in ("path", "query", "url", "description", "prompt"):
            if inp.get(k):
                key = _trunc(str(inp[k]), 120); break
    return f"  [tool:{name}] {key}".rstrip()

def condense(path: str, cap: int = 22000) -> Condensed:
    title = None
    lines = []
    cwds = Counter()
    first_ts = last_ts = None
    nmsg = 0
    with open(path, errors="replace", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except Exception:
                continue
            t = o.get("type")
            if o.get("cwd"):
                cwds[o["cwd"]] += 1
            ts = o.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            if t in ("ai-title", "aiTitle"):
                title = o.get("aiTitle") or o.get("title") or title
                continue
            if t == "summary":
                s = o.get("summary")
                if s:
                    lines.append(f"[SUMMARY] {_trunc(s, 500)}")
                continue
            if t not in ("user", "assistant"):
                continue
            msg = o.get("message")
            if not isinstance(msg, dict):
                continue
            cont = msg.get("content")
            role = msg.get("role", t)
            if isinstance(cont, str):
                txt = cont.strip()
                if txt.startswith("<") and ("system-reminder" in txt[:40]
                        or "local-command" in txt[:40] or "command-name" in txt[:60]):
                    txt = "[harness/command injection 省略]"
                if txt:
                    nmsg += 1
                    lines.append(f"[{role.upper()}] {_trunc(txt, 2500)}")
            elif isinstance(cont, list):
                buf = []
                for b in cont:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text":
                        tx = (b.get("text") or "").strip()
                        if tx:
                            buf.append(_trunc(tx, 3500))
                    elif bt == "thinking":
                        continue
                    elif bt == "tool_use":
                        buf.append(_tool_line(b))
                    elif bt == "tool_result":
                        c = b.get("content")
                        s = ""
                        if isinstance(c, list):
                            s = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        elif isinstance(c, str):
                            s = c
                        if b.get("is_error") or re.search(
                                r"\b(error|fail|panic|exception|traceback)\b", s[:200], re.I):
                            buf.append(f"  [tool_result ERROR] {_trunc(s, 200)}")
                    elif bt == "image":
                        buf.append("  [image]")
                if buf:
                    nmsg += 1
                    lines.append(f"[{role.upper()}] " + "\n".join(buf))
    cwd = cwds.most_common(1)[0][0] if cwds else None
    body = "\n".join(lines)
    if len(body) > cap:
        head = int(cap * 0.6); tail = cap - head
        body = body[:head] + f"\n…[中略 {len(body)-cap}c]…\n" + body[-tail:]
    return Condensed(title=title, cwd=cwd, first_ts=first_ts, last_ts=last_ts,
                     nmsg=nmsg, body=body)
