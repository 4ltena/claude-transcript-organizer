import os
from transcript_organizer.config import load_config
from transcript_organizer.route import route

def _cfg(tmp_path):
    proj = tmp_path / "projects"
    (proj / "Webs" / "portfolio").mkdir(parents=True)
    (proj / "AIRouter").mkdir(parents=True)
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "roots": {"PROJECTS": str(proj)},
        "archive_root": str(proj / "_conversation-archive"),
        "aliases": [[str(tmp_path / "Desktop" / "AIRouter"), str(proj / "AIRouter")]],
    }))
    return load_config(str(p)), proj

def test_container_sub(tmp_path):
    cfg, proj = _cfg(tmp_path)
    t = route(str(proj / "Webs" / "portfolio"), cfg)
    assert t.label == "Webs__portfolio"
    assert t.root == str(proj / "Webs" / "portfolio")

def test_top_component(tmp_path):
    cfg, proj = _cfg(tmp_path)
    t = route(str(proj / "AIRouter"), cfg)
    assert t.label == "AIRouter"

def test_alias_then_resolve(tmp_path):
    cfg, proj = _cfg(tmp_path)
    t = route(str(tmp_path / "Desktop" / "AIRouter"), cfg)
    assert t.label == "AIRouter"

def test_missing_dir_goes_archive(tmp_path):
    cfg, proj = _cfg(tmp_path)
    t = route(str(proj / "Webs" / "ghost"), cfg)
    assert t.label == "_archive"
    assert t.root == cfg.archive_root

def test_outside_projects_archive(tmp_path):
    cfg, proj = _cfg(tmp_path)
    assert route("/tmp/whatever", cfg).label == "_archive"
    assert route(None, cfg).label == "_archive"
