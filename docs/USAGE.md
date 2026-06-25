# claude-transcript-organizer 操作マニュアル

会話 transcript（`~/.claude/projects/**/*.jsonl`）を差分処理し、各プロジェクトの
`docs/HANDOFF.md` を更新、処理済み会話を安全に削除する手動 CLI ツールの操作手順。

- 設計思想: 「LLM は提案、コードが統合」。LLM が失敗・不正でも台帳/findings/HANDOFF は壊れない。
- 標準ライブラリのみ（Python 3.11+）。追加インストール不要。
- `cas push` / git push などの同期は**やらない**（必要なら手動で実行）。

---

## 0. 事前準備

### 置き場所
```
/Users/kn/File/projects/claude/claude-transcript-organizer
```
以下のコマンドはこのディレクトリ内で実行する（`cli.py` がリポジトリ直下にある）。

### LLM プロバイダの API キー（使うものだけ設定）
| プロバイダ | 環境変数 | 既定モデル |
|---|---|---|
| `gemini`（既定） | `GEMINI_API_KEY` | gemini-2.5-flash |
| `anthropic` | `ANTHROPIC_API_KEY` | claude-haiku-4-5-20251001 |
| `openai` | `OPENAI_API_KEY` | gpt-4.1-mini |
| `ollama`（ローカル） | （不要） | qwen3.5:4b（`http://localhost:11434`） |

例（既定の Gemini を使う場合）:
```bash
export GEMINI_API_KEY="..."     # その場限り。常用するならシェルの rc に書く
```
キー未設定でそのプロバイダを呼ぶと、リクエスト前に「`GEMINI_API_KEY is not set`」と明示エラーで止まる（誤送信しない）。
`ollama` はローカルサーバが起動していれば API キー不要。

---

## 3コマンドの全体像

| コマンド | 何をする | 破壊性 |
|---|---|---|
| `organize` | 未処理会話を抽出 → HANDOFF.md を更新（**削除しない**） | 低（HANDOFF の管理区間のみ書く） |
| `status` | 未処理件数・台帳・findings を表示 | なし（読み取りのみ） |
| `delete` | 処理済み会話を trash へ退避 | **既定 dry-run**。`--yes` で実行 |

推奨フロー: **`status` で様子を見る → `organize` で抽出 → 中身を確認 → `delete`（まず素で確認）→ `delete --yes` で退避**。

---

## 1. `organize` — 抽出して HANDOFF を更新

未処理（＝台帳に無い）会話だけを LLM に投げ、構造化 findings を蓄積し、対象プロジェクトの
`docs/HANDOFF.md` の管理区間 `<!-- BEGIN transcript-organizer -->` … `<!-- END -->` を再生成する。
**マーカーの外にある人間の記述は一切変更しない。** HANDOFF が無ければ管理区間だけで新規作成する。

```bash
# 通常実行（既定 Gemini）
python cli.py organize

# まず何が対象になるか確認（LLM 呼び出しも書き込みもしない）
python cli.py organize --dry-run

# プロバイダを切り替える
python cli.py organize --provider ollama       # ローカル LLM
python cli.py organize --provider anthropic

# 特定プロジェクトだけ処理（ラベル指定）
python cli.py organize --project Webs__portfolio

# 台帳を無視して作り直す（HANDOFF の管理区間が消えた時の復旧用）
python cli.py organize --rebuild
```

出力例:
```
処理: 12件 / 新規finding: 47件 / スキップ: {'ledger': 700, 'active': 1, 'sidechain': 8} / HANDOFF更新: 9件
```
- `処理` = 今回抽出した会話数 / `新規finding` = 新たに増えた項目数
- `スキップ` の内訳: `ledger`=処理済み, `active`=直近活動中で保護, `sidechain`=サブエージェントログ, `meta`=本ツールの抽出メタ, `trivial`=中身が薄い, `protected`=保護指定セッション
- `--dry-run` 時は末尾に `（dry-run: 書き込みなし）`

### ラベルの付き方（`--project` で使う名前）
- `~/File/projects/<comp>` 直下 → ラベル `<comp>`（例 `AIRouter`）
- コンテナ（`Other/School/Webs/claude/discord-bots/mcp/Exam`）配下 → `comp__sub`（例 `Webs__portfolio`）
- 上記で解決できない（移動済み・tmp・home 等）→ `_archive`（`_conversation-archive` に集約）

---

## 2. `status` — 状況確認（読み取りのみ）

```bash
python cli.py status
```
出力例:
```
未処理: 32件 / 台帳: 700件 / findings: {'AIRouter': 41, 'Webs__portfolio': 38, ...}
```
- `未処理` = まだ organize していない会話数（※保護対象も未処理として数える点に注意）
- `台帳` = これまで処理済みに記録した会話数
- `findings` = プロジェクト別の蓄積 findings 件数

---

## 3. `delete` — 処理済み会話を安全に削除

**既定は dry-run（何も消さない・件数だけ表示）。** 実際に動かすには `--yes` を付ける。
削除と言っても即時 `rm` ではなく、`data/trash/<日付>/` に**退避（move）**するだけ（保持期間内は戻せる）。

```bash
# まず候補と保護内訳を確認（何も移動しない）
python cli.py delete

# 実行（trash へ退避）
python cli.py delete --yes

# 特定プロジェクトだけ削除対象にする
python cli.py delete --project Webs__portfolio --yes
```

出力例:
```
[dry-run] 削除候補: 760件 / 保護: {'unprocessed': 41, 'active': 1, 'sidechain': 8} （実行は --yes）
削除(trash退避): 760件 / 保護: {...}        # --yes 実行時
```

### 削除の安全装置（これらは常に保護＝消えない）
1. **台帳に無い会話**（未処理）は削除候補にならない
2. **`active`**: 直近 `protect_recent_minutes`（既定30分）以内に動いた会話
3. **`sidechain`**: サブエージェントログ（`agent-*` / `subagents/` / `isSidechain`）
4. **autonomous**: `exclude_globs`（既定 `*autonomous*`）に一致 → そもそも走査対象外
5. **保護セッション**: `protect_session_ids` と環境変数 `CLAUDE_SESSION_ID`
6. 退避先は `scan_base` 配下のパスに限定（範囲外パスはスキップ）

退避物は `data/trash/<日付>/` に保存。`trash_retention_days`（既定14日）を超えた古い退避は、次回 `delete` 実行時に自動で gc される。

---

## 4. 設定ファイル `config.json`

リポジトリ直下の `config.json` が既定設定。別の設定で動かしたいときは `--config path/to.json`。
よく触る項目:

| キー | 既定 | 意味 |
|---|---|---|
| `provider` | `gemini` | 既定 LLM プロバイダ（`--provider` で都度上書き可） |
| `scan_base` | `~/.claude/projects` | 会話の走査ルート |
| `roots.PROJECTS` | `~/File/projects` | プロジェクト群のルート（ラベル解決の基準） |
| `containers` | `[Other,School,Webs,…]` | `comp__sub` ラベルにする中間ディレクトリ |
| `aliases` | `[]` | 移動した cwd の読み替え `[["旧prefix","新prefix"]]` |
| `exclude_globs` | `["*autonomous*"]` | 走査から除外するパス |
| `include_sidechain` | `false` | true でサブエージェントログも抽出対象に |
| `protect_recent_minutes` | `30` | 直近活動を保護する分数 |
| `condense_cap` | `22000` | 1会話の凝縮上限（超過は頭60%+尾40%） |
| `min_msgs` / `min_chars` | `2` / `400` | これ未満は `trivial` として除外 |
| `retries` | `2` | LLM 失敗時の再試行回数（尽きたらその会話だけスキップ） |
| `delete.trash_retention_days` | `14` | trash の保持日数 |
| `protect_session_ids` | `[]` | 常に保護するセッション ID |

> API キーは `config.json` に書かず**環境変数**で渡す（`providers.<name>.api_key_env` がその変数名）。
> ローカル専用の上書きは `config.local.json`（.gitignore 済み）に置くと安全。

---

## 5. データの置き場所（`data/`、.gitignore 済み）

```
data/ledger.json            処理済みセッションの台帳（差分判定の核）
data/findings/<label>.json  プロジェクト別に蓄積した findings
data/trash/<日付>/…         delete --yes で退避した会話（保持期間内は復元可）
```
- HANDOFF を作り直したい → `data/findings/` は残したまま該当 HANDOFF を消して `organize`、または `organize --rebuild`。
- 完全にやり直したい → `data/` を消す（※台帳も消えるので、次回は全会話が未処理＝再抽出になる）。

---

## 6. よくある操作レシピ

```bash
# A. 定期メンテ: 増えた会話を取り込んで HANDOFF 更新、消さずに確認だけ
python cli.py status
python cli.py organize
git -C ~/File/projects/<proj> diff docs/HANDOFF.md   # 中身を目視

# B. 確認できたら処理済み会話を退避
python cli.py delete            # 候補数と保護を確認
python cli.py delete --yes      # trash へ退避

# C. ローカル LLM で API 課金なしに回す
python cli.py organize --provider ollama

# D. 消えた/壊れた HANDOFF を蓄積 findings から作り直す
python cli.py organize --project <label> --rebuild
```

---

## 7. テスト

```bash
python -m pytest -q        # 48 tests、ネットワーク不要（mock provider）
```

---

## 8. 注意点

- このツールは**同期しない**。退避後に他マシンへ反映したいなら、別途 `cas push` 等を手動で。
- `delete` は履歴を消すのではなく `data/trash/` へ動かすだけ。完全に消えるのは保持期間超過後の gc 時。
- `status` の「未処理」には保護対象（active 等）も含まれるため、実際に organize される数とは一致しないことがある。
- findings の「完成/未完」系は最新（`last_seen` 降順）が上に出るが、古い項目を自動で打ち消しはしない（将来の改善予定）。
