import builtins
import json
import cli

def _cfg(tmp_path):
    scan = tmp_path / "scan"; scan.mkdir()
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"provider": "mock", "scan_base": str(scan),
                             "data_dir": str(tmp_path / "data"),
                             "roots": {"PROJECTS": str(tmp_path / "projects")},
                             "archive_root": str(tmp_path / "projects" / "_arch")}))
    return str(p)

def test_status_runs(tmp_path, capsys):
    rc = cli.main(["status", "--config", _cfg(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "未処理" in out

def test_organize_dry_run(tmp_path, capsys):
    rc = cli.main(["organize", "--config", _cfg(tmp_path), "--dry-run"])
    assert rc == 0

def test_delete_default_is_dry_run(tmp_path, capsys):
    rc = cli.main(["delete", "--config", _cfg(tmp_path)])
    assert rc == 0
    assert "dry-run" in capsys.readouterr().out.lower()


def _stub_deleter(monkeypatch):
    """Replace deleter funcs with recorders; return a calls dict."""
    calls = {"plan": 0, "execute": [], "gc": 0}
    def plan(cfg, only_label=None):
        calls["plan"] += 1
        return {"delete": [], "protect": {}}
    def execute(plan_arg, cfg, yes=False):
        calls["execute"].append(yes)
        return {"deleted": 0}
    def gc(cfg, now_epoch=None):
        calls["gc"] += 1
        return 0
    monkeypatch.setattr(cli.deleter, "plan_deletion", plan)
    monkeypatch.setattr(cli.deleter, "execute", execute)
    monkeypatch.setattr(cli.deleter, "gc_trash", gc)
    return calls


def _no_prompt(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("input() should not be called")
    monkeypatch.setattr(builtins, "input", boom)


def test_organize_yes_auto_deletes(tmp_path, monkeypatch):
    calls = _stub_deleter(monkeypatch)
    _no_prompt(monkeypatch)                       # -y must skip the prompt
    rc = cli.main(["organize", "--config", _cfg(tmp_path), "--yes"])
    assert rc == 0
    assert calls["execute"] == [True]
    assert calls["gc"] == 1


def test_organize_prompt_yes_deletes(tmp_path, monkeypatch):
    calls = _stub_deleter(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "y")
    rc = cli.main(["organize", "--config", _cfg(tmp_path)])
    assert rc == 0
    assert calls["execute"] == [True]


def test_organize_prompt_no_skips_delete(tmp_path, monkeypatch):
    calls = _stub_deleter(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda *a: "n")
    rc = cli.main(["organize", "--config", _cfg(tmp_path)])
    assert rc == 0
    assert calls["execute"] == []


def test_organize_dry_run_never_prompts(tmp_path, monkeypatch):
    calls = _stub_deleter(monkeypatch)
    _no_prompt(monkeypatch)
    rc = cli.main(["organize", "--config", _cfg(tmp_path), "--dry-run"])
    assert rc == 0
    assert calls["execute"] == []
