import os
from .models import Target

def route(cwd, config) -> Target:
    archive = Target(label="_archive", root=config.archive_root)
    if not cwd:
        return archive
    proj = config.roots.get("PROJECTS", "")
    for a, b in config.aliases:
        if cwd == a or cwd.startswith(a + os.sep):
            cwd = b + cwd[len(a):]
            break
    if proj and (cwd == proj or cwd.startswith(proj + os.sep)):
        rel = cwd[len(proj):].strip(os.sep).split(os.sep)
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
