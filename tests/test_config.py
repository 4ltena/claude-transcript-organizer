import json, os
from transcript_organizer.config import load_config

def test_defaults_when_file_missing(tmp_path):
    cfg = load_config(str(tmp_path / "nope.json"))
    assert cfg.provider == "gemini"
    assert "Other" in cfg.containers
    assert cfg.condense_cap == 22000
    assert cfg.delete["trash_retention_days"] == 14

def test_overrides_and_expanduser(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"provider": "ollama", "scan_base": "~/x",
                             "condense_cap": 100}))
    cfg = load_config(str(p))
    assert cfg.provider == "ollama"
    assert cfg.condense_cap == 100
    assert cfg.scan_base == os.path.expanduser("~/x")
    # untouched keys keep defaults
    assert cfg.min_msgs == 2
