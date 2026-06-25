import os

BEGIN = "<!-- BEGIN transcript-organizer -->"
END = "<!-- END transcript-organizer -->"

_SECTIONS = [
    ("design_requirement", "### 設計・要件"),
    ("decision", "### 設計判断と理由"),
    ("completed", "### 完成・動作中"),
    ("in_progress", "### 未完・途中"),
    ("next_step", "### 次にやること"),
    ("gotcha", "### 注意点・ハマりどころ"),
    ("open_question", "### 未決事項"),
]

def _sanitize(s: str) -> str:
    """Strip managed-block markers so LLM-generated text cannot inject them."""
    return s.replace(BEGIN, "").replace(END, "")

def _line(r):
    src = "、".join(_sanitize(t) for t in r.get("src_titles", [])[:2])
    suffix = f"（出典: {src}）" if src else ""
    return f"- {_sanitize(r['text'])}{suffix}"

def render_markdown(records, label: str, date: str) -> str:
    by_kind = {}
    for r in records:
        by_kind.setdefault(r["kind"], []).append(r)
    out = [BEGIN, f"## 自動抽出（transcript-organizer 管理 / {date} 更新）", ""]
    for kind, heading in _SECTIONS:
        rs = by_kind.get(kind)
        if not rs:
            continue
        # status-like kinds: newest last_seen first
        if kind in ("completed", "in_progress"):
            rs = sorted(rs, key=lambda r: r.get("last_seen") or "", reverse=True)
        out.append(heading)
        out.extend(_line(r) for r in rs)
        out.append("")
    out.append(END)
    return "\n".join(out) + "\n"

def update_handoff(root: str, block: str) -> str:
    docs = os.path.join(root, "docs")
    os.makedirs(docs, exist_ok=True)
    path = os.path.join(docs, "HANDOFF.md")
    if os.path.isfile(path):
        content = open(path, encoding="utf-8").read()
    else:
        content = "# HANDOFF（引き継ぎメモ）\n\n"
    if BEGIN in content and END in content:
        pre = content[:content.index(BEGIN)]
        post = content[content.index(END) + len(END):]
        new = pre + block.rstrip("\n") + post
    else:
        sep = "" if content.endswith("\n\n") else ("\n" if content.endswith("\n") else "\n\n")
        new = content + sep + block
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return path
