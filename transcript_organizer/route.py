import os
from .models import Target


def _norm(p):
    """セパレータを '/' に正規化（Windows パスを posix 上で照合するため）。"""
    return p.replace("\\", "/") if p else p


def label_to_root(label, config) -> str:
    """Inverse of route()'s label construction: recover a label's HANDOFF root.

    route builds a label as ``comp`` (top component) or ``comp__sub`` (a
    container's child), with root ``PROJECTS/comp[/sub]``. Splitting on "__"
    and rejoining under PROJECTS recovers that root. The "_archive" label maps
    to config.archive_root. Used by the render command, which has only the
    label (from data/findings/<label>.json) and no source cwd to route.
    """
    if label == "_archive":
        return config.archive_root
    proj = config.roots.get("PROJECTS", "")
    return os.path.join(proj, *label.split("__"))


def route(cwd, config) -> Target:
    # 照合・分割は正規化した '/' 区切りで行い、返す root は元の proj から
    # os.path.join で実行 OS ネイティブ形式に組み立てる（WSL 実行で transcript の
    # Windows パス cwd を /mnt 配下へ alias 変換しても破綻しないようにする）。
    archive = Target(label="_archive", root=config.archive_root)
    if not cwd:
        return archive
    proj = config.roots.get("PROJECTS", "")
    ncwd = _norm(cwd)
    for a, b in config.aliases:
        na = _norm(a)
        if ncwd == na or ncwd.startswith(na + "/"):
            ncwd = _norm(b) + ncwd[len(na):]
            break
    nproj = _norm(proj)
    if nproj and (ncwd == nproj or ncwd.startswith(nproj + "/")):
        rel = ncwd[len(nproj):].strip("/").split("/")
        comp = rel[0] if rel and rel[0] else ""
        if not comp:
            return archive
        if comp in config.containers and len(rel) >= 2:
            root = os.path.join(proj, comp, rel[1])
            label = f"{comp}__{rel[1]}"
        else:
            root = os.path.join(proj, comp)
            label = comp
        if os.path.isdir(root):
            return Target(label=label, root=root)
        return archive
    return archive
