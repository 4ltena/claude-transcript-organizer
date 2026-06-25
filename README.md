# claude-transcript-organizer

> Claude Code の会話 transcript を解析し、プロジェクトごとの HANDOFF ファイルへ知見を蓄積するツール。LLM は提案するだけ、書き込みは決定論的 Python が担うため、API 障害でも HANDOFF は壊れない。

![python](https://img.shields.io/badge/python-3.10%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green)

`~/.claude/projects` 以下に蓄積された会話ファイル(`.jsonl`)を走査し、**LLM API** に投げて技術的知見・決定事項・TODO を抽出。プロジェクトルートの `HANDOFF.md` にある専用マーカー領域へ自動で書き込み、人間が書いたそれ以外の文章はそのまま保持します。

```
~/.claude/projects/**/*.jsonl
        │
        ▼ discover / classify
    未処理の会話を台帳と照合
        │
        ▼ condense → LLM extract
    findings (知見・決定・TODO) を生成
        │
        ▼ FindingStore に蓄積・重複排除
        │
        ▼ render + update HANDOFF marker region
    HANDOFF.md の <!-- BEGIN/END transcript-organizer --> 領域を更新
```

---

## 基本フロー: organize → status → delete

### 1. 整理 (organize)

```bash
python cli.py organize
```

会話を走査し、LLM で知見を抽出して HANDOFF を更新します。書き込みをせずに内容だけ確認したい場合:

```bash
python cli.py organize --dry-run
```

特定プロジェクトだけ対象にする場合:

```bash
python cli.py organize --project my-project
```

### 2. 状態確認 (status)

```bash
python cli.py status
```

未処理件数・台帳登録件数・findings 件数をプロジェクト別に表示します。

### 3. 削除 (delete)

```bash
# dry-run: 削除候補を表示するだけ（デフォルト）
python cli.py delete

# 実際にtrashへ退避する
python cli.py delete --yes
```

---

## プロバイダ選択

`--provider` フラグまたは `config.json` の `provider` キーでバックエンドを切り替えられます。

```bash
python cli.py organize --provider gemini      # デフォルト
python cli.py organize --provider anthropic
python cli.py organize --provider openai
python cli.py organize --provider ollama      # ローカル; APIキー不要
```

各プロバイダが必要とする環境変数:

| プロバイダ | 環境変数 |
|-----------|---------|
| `gemini` | `GEMINI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `ollama` | 不要（`config.json` の `endpoint` で接続先を指定） |

---

## HANDOFF マーカー領域の動作

HANDOFF.md に以下のマーカーブロックを含めると、`organize` 実行時にブロック内の内容だけが自動生成コンテンツで置き換えられます。

```markdown
<!-- BEGIN transcript-organizer -->
（ここが自動生成領域）
<!-- END transcript-organizer -->
```

**マーカー外の文章は一切書き換えません。** プロジェクトの説明・手順・メモはマーカーの外に書いておけば永続します。マーカーが存在しない場合はファイル末尾に追記されます。

---

## delete の安全モデル

| 特性 | 説明 |
|------|------|
| **dry-run デフォルト** | `--yes` なしでは何も削除しない。候補件数を表示するだけ |
| **台帳ゲート** | `organize` 済みで台帳に記録された会話のみが削除候補になる |
| **最近のセッション保護** | `protect_recent_minutes`（デフォルト 30 分）以内に更新されたファイルは削除対象から除外 |
| **protect_session_ids** | config に列挙したセッション ID は常に保護 |
| **trash 退避** | 即時削除ではなく `data/trash/` へ移動。`delete.trash_retention_days`（デフォルト 14 日）後に GC |

---

## `cas push` / sync について

本ツールは **`cas push` や外部への同期を実行しません**。HANDOFF.md の更新後は手動で `cas push` を実行してください。自動化する場合はシェルスクリプトやスケジューラ側でラップしてください。

---

## 設定 (config.json)

`config.json` が既定値。主なキー:

| キー | 既定 | 説明 |
|------|------|------|
| `provider` | `gemini` | 使用する LLM プロバイダ |
| `scan_base` | `~/.claude/projects` | 会話ファイルのスキャン起点 |
| `archive_root` | `~/File/projects/_conversation-archive` | アーカイブ済み会話の置き場 |
| `include_sidechain` | `false` | サイドチェーン会話を含めるか |
| `condense_cap` | `22000` | LLM に渡す前の最大文字数 |
| `protect_recent_minutes` | `30` | この時間以内の会話は削除保護 |
| `delete.trash_retention_days` | `14` | trash の保持日数 |

---

## テスト

```bash
python -m pytest -q
```

---

## ライセンス

MIT
