import json, os
from dataclasses import dataclass, field, fields

_DEFAULTS = {
    "provider": "gemini",
    "providers": {
        "gemini":    {"api_key_env": "GEMINI_API_KEY", "model": "gemini-2.5-flash"},
        "anthropic": {"api_key_env": "ANTHROPIC_API_KEY", "model": "claude-haiku-4-5-20251001"},
        "openai":    {"api_key_env": "OPENAI_API_KEY", "model": "gpt-4.1-mini"},
        "ollama":    {"endpoint": "http://localhost:11434", "model": "qwen3.5:4b"},
    },
    "scan_base": "~/.claude/projects",
    "roots": {"PROJECTS": "~/File/projects"},
    "archive_root": "~/File/projects/_conversation-archive",
    "containers": ["Other", "School", "Webs", "claude", "discord-bots", "mcp", "Exam"],
    "aliases": [],
    "exclude_globs": ["*autonomous*"],
    "include_sidechain": False,
    "meta_signatures": ["引き継ぎ", "transcript-organizer"],
    "protect_recent_minutes": 30,
    "condense_cap": 22000,
    "min_msgs": 2,
    "min_chars": 400,
    "retries": 2,
    "delete": {"trash_retention_days": 14},
    "protect_session_ids": [],
    "data_dir": None,  # resolved below
}

# keys whose string value(s) should be expanduser-ed
_PATH_KEYS = {"scan_base", "archive_root", "data_dir"}

@dataclass
class Config:
    provider: str
    providers: dict
    scan_base: str
    roots: dict
    archive_root: str
    containers: list
    aliases: list
    exclude_globs: list
    include_sidechain: bool
    meta_signatures: list
    protect_recent_minutes: int
    condense_cap: int
    min_msgs: int
    min_chars: int
    retries: int
    delete: dict
    protect_session_ids: list
    data_dir: str

def load_config(path: str | None = None) -> Config:
    data = dict(_DEFAULTS)
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if k in data:
                data[k] = v
    # default data_dir = <repo>/data (sibling of this package's parent)
    if not data["data_dir"]:
        pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data["data_dir"] = os.path.join(pkg_parent, "data")
    for k in _PATH_KEYS:
        if isinstance(data.get(k), str):
            data[k] = os.path.expanduser(data[k])
    data["roots"] = {k: os.path.expanduser(v) for k, v in data["roots"].items()}
    data["aliases"] = [[os.path.expanduser(a), os.path.expanduser(b)] for a, b in data["aliases"]]
    allowed = {f.name for f in fields(Config)}
    return Config(**{k: data[k] for k in allowed})
