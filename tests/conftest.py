import json, pytest

@pytest.fixture
def write_jsonl(tmp_path):
    def _w(name, rows):
        p = tmp_path / name
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return str(p)
    return _w
