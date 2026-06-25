from dataclasses import dataclass

@dataclass
class ConvMeta:
    path: str
    sid: str
    cwd: str | None
    first_ts: str | None
    last_ts: str | None
    nmsg: int
    is_sidechain: bool
    basename: str

@dataclass
class Condensed:
    title: str | None
    cwd: str | None
    first_ts: str | None
    last_ts: str | None
    nmsg: int
    body: str

@dataclass
class Target:
    label: str
    root: str

@dataclass
class Finding:
    kind: str
    text: str
    confidence: float
    source: str
    src_ts: str | None
    label: str
