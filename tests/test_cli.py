import json, os, time
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
