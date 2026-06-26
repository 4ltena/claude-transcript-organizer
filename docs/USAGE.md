# claude-transcript-organizer 操作マニュアル

会話 transcript（`~/.claude/projects/**/*.jsonl`）を差分処理し、各プロジェクトの `docs/HANDOFF.md` を更新して、処理済み会話を安全に退避する手動 CLI ツールの操作手順。README より細かく、全フラグ・出力フォーマット・OS 別の実行・トラブルシュートまで扱う。内部設計は [DESIGN.md](DESIGN.md) を参照。

- 設計思想は「LLM は提案、コードが統合」。LLM が失敗・不正でも台帳/findings/HANDOFF は壊れない。
- 標準ライブラリのみ。Python 3.9 以上で動く。追加インストール不要。
- 外部への同期や git push はしない。必要なら別途手動で。

---

## 0. 事前準備

### 置き場所

リポジトリを任意の場所に clone する。以降のコマンドは `cli.py` のある直下で実行する。短縮コマンド（`tsorg` 等）を使う場合は README のインストール手順で `bin/` を PATH に通す。

### LLM プロバイダの API キー

使うプロバイダの環境変数だけ設定すればよい。

| プロバイダ | 環境変数 | 既定モデル | 接続先 |
|---|---|---|---|
| `gemini`（既定） | `GEMINI_API_KEY` | gemini-2.5-flash | Google Generative Language API |
| `anthropic` | `ANTHROPIC_API_KEY` | claude-haiku-4-5-20251001 | api.anthropic.com |
| `openai` | `OPENAI_API_KEY` | gpt-4.1-mini | api.openai.com |
| `ollama`（ローカル） | 不要 | qwen3.5:4b | `http://localhost:11434`（config の `endpoint`） |

```bash
export GEMINI_API_KEY="..."     # その場限り。常用するならシェルの rc に書く
```

`gemini`・`openai` はキー未設定でそのプロバイダを呼ぶと、リクエスト前に `GEMINI_API_KEY is not set` のように明示エラーで止まる（誤送信しない）。`ollama` はローカルサーバが起動していればキー不要。

---

## 1. 3コマンドの全体像

| コマンド | 何をする | 破壊性 |
|---|---|---|
| `organize` | 未処理会話を抽出して HANDOFF.md を更新（削除しない） | 低（HANDOFF の管理区間のみ書く） |
| `status` | 未処理件数・台帳・findings を表示 | なし（読み取りのみ） |
| `delete` | 処理済み会話を trash へ退避 | 既定 dry-run。`--yes` で実行 |

推奨フローは、`status` で様子を見て、`organize` で抽出し、HANDOFF の中身を確認してから、`delete` で候補を確認し、`delete --yes` で退避する。

### フラグ一覧

| コマンド | フラグ | 意味 |
|---|---|---|
| `organize` | `--config <path>` | 設定ファイルを差し替える（既定は `config.json`） |
| | `--provider <name>` | その回だけプロバイダを上書き |
| | `--project <label>` | 指定ラベルの会話だけ処理 |
| | `--rebuild` | 台帳を無視して再処理（HANDOFF 再構築用） |
| | `--dry-run` | 走査とルート判定だけ。LLM 呼び出しも書き込みもしない |
| | `--verbose` / `-v` | 会話ごとのトレースを stderr に逐次出力 |
| `status` | `--config <path>` | 設定ファイルを差し替える |
| `delete` | `--config <path>` | 設定ファイルを差し替える |
| | `--project <label>` | 指定ラベルの会話だけ削除対象に |
| | `--yes` | 実際に trash へ退避（既定は dry-run） |

すべてのコマンドの戻り値（プロセス終了コード）は正常時 0。

---

## 2. `organize` — 抽出して HANDOFF を更新

未処理（台帳に無い）会話だけを LLM に投げ、構造化 findings を蓄積し、対象プロジェクトの `docs/HANDOFF.md` の管理区間 `<!-- BEGIN transcript-organizer -->` … `<!-- END -->` を再生成する。マーカーの外にある人間の記述は一切変更しない。HANDOFF が無ければ管理区間だけで新規作成する。

```bash
# 通常実行（既定 Gemini）
python cli.py organize

# 何が対象になるか確認（LLM 呼び出しも書き込みもしない）
python cli.py organize --dry-run

# プロバイダを切り替える
python cli.py organize --provider ollama       # ローカル LLM
python cli.py organize --provider anthropic

# 特定プロジェクトだけ処理（ラベル指定）
python cli.py organize --project Webs__portfolio

# 台帳を無視して作り直す（HANDOFF の管理区間が消えた時の復旧用）
python cli.py organize --rebuild
```

### 標準出力のサマリ

```
処理: 12件 / 新規finding: 47件 / スキップ: {'ledger': 700, 'active': 1, 'sidechain': 8} / HANDOFF更新: 9件
```

- `処理` は今回抽出した会話数（dry-run 時はルート判定まで進んだ会話数）。
- `新規finding` は新たに増えた finding 数。再観測した既存 finding は数えない。
- `スキップ` の内訳キーは `ledger`（処理済み）・`active`（直近活動で保護）・`sidechain`（サブエージェントログ）・`meta`（本ツールの抽出メタ）・`trivial`（中身が薄い）・`protected`（保護指定セッション）・`other_label`（`--project` 不一致）・`extract_failed`（抽出失敗）。
- `HANDOFF更新` は書き換えた HANDOFF.md の数。
- `--dry-run` 時は末尾に `（dry-run: 書き込みなし）` が付く。

### `--verbose` のトレース

会話ごとの処理を追うときは `--verbose`（`-v`）。トレースは stderr、最終サマリは stdout に出る。各行は英語で `HH:MM:SS · event · id · detail` 形式。

| event | 出る場面 | detail の例 |
|---|---|---|
| `read` | 凝縮を読み終えた | `title=… cwd=… msgs=23 chars=7119`（上限超過時は `truncated(head60%/tail40%)`） |
| `route` | 書き込み先が決まった | `label=Webs__portfolio root=…` |
| `extract` | 抽出が成功した | `proposed=7 {'decision': 3, …} new=4` |
| `skip` | いずれかの理由で除外 | `trivial (too little content)` / `active …` / `extract_failed …` |
| `dry-run` | `--dry-run` で抽出を省いた | `no extraction (read-only)` |
| `handoff` | HANDOFF を更新した | `Webs__portfolio · …/docs/HANDOFF.md` |

TTY では最下行に進捗バーが固定表示される。パイプやリダイレクト時は25件ごとに進捗行を出す。

```
02:29:47 · read    · 04520aae-… · title='Review feature design' cwd=… msgs=23 chars=7119
02:29:47 · route   · 04520aae-… · label=my-project root=<PROJECTS>/my-project
02:29:52 · extract · 04520aae-… · proposed=7 {'decision': 3, 'next_step': 2, 'gotcha': 2} new=4
02:30:01 · skip    · 0c059f90-… · trivial (too little content)
02:35:10 · handoff · my-project · <PROJECTS>/my-project/docs/HANDOFF.md
[##############----------]  58.3%  712/1220  remaining 508
```

### ラベルの付き方（`--project` で使う名前）

ラベルは会話の `cwd` を `roots.PROJECTS` と照合して決まる。

- `PROJECTS/<comp>` 直下 → ラベル `<comp>`（例 `claude`）
- `containers`（既定 `Other`/`School`/`Webs`/`claude`/`discord-bots`/`mcp`/`Exam`）配下 → `comp__sub`（例 `Webs__portfolio`）
- 解決できない（移動済み・tmp・home 等）→ `_archive`（`archive_root` に集約）

照合の詳細とエッジケースは DESIGN.md の「ルーティング」を参照。

---

## 3. `status` — 状況確認（読み取りのみ）

```bash
python cli.py status
```

```
未処理: 32件 / 台帳: 700件 / findings: {'Webs__portfolio': 38, 'claude': 41, …}
```

- `未処理` はまだ organize していない会話数。保護対象（active 等）も未処理として数えるため、実際に organize される数とは一致しないことがある。
- `台帳` はこれまで処理済みに記録した会話数。
- `findings` はラベル別の蓄積 finding 件数。

---

## 4. `delete` — 処理済み会話を安全に退避

既定は dry-run で、候補数だけ表示して何も動かさない。実際に動かすには `--yes` を付ける。削除と言っても物理削除ではなく、`data/trash/<日付>/` への移動で、保持期間内は戻せる。

```bash
# 候補と保護内訳を確認（何も移動しない）
python cli.py delete

# 実行（trash へ退避）
python cli.py delete --yes

# 特定プロジェクトだけ削除対象にする
python cli.py delete --project Webs__portfolio --yes
```

```
[dry-run] 削除候補: 760件 / 保護: {'unprocessed': 41, 'active': 1, 'sidechain': 8} （実行は --yes）
削除(trash退避): 760件 / 保護: {…}        # --yes 実行時
```

### 削除の安全装置（常に保護され消えない）

1. 台帳に無い会話（未処理）は候補にならない。
2. `active`。直近 `protect_recent_minutes`（既定30分）以内に動いた会話。
3. `sidechain`。サブエージェントログ（`agent-*` / `/subagents/` / `isSidechain`）。
4. `exclude_globs`（既定 `*autonomous*`）一致はそもそも走査対象外。
5. 保護セッション。`protect_session_ids` と環境変数 `CLAUDE_SESSION_ID`。
6. 退避先は `scan_base` 配下に限定。範囲外パスはスキップ。

退避物は `data/trash/<日付>/` に保存。`trash_retention_days`（既定14日）を超えた古い退避は、次回の `delete --yes` 時に自動で GC される。

---

## 5. 短縮コマンド（tsorg / tstat / tsdel）

`bin/` のラッパーで、どのディレクトリからでも呼べる。Windows 用は `.cmd`、macOS/Linux 用は拡張子なしのシェルスクリプト。`tsorg` は `--verbose` を既定で付ける。

| コマンド | 等価 |
|---|---|
| `tsorg` | `python cli.py organize --verbose …` |
| `tstat` | `python cli.py status` |
| `tsdel` | `python cli.py delete` |

引数はそのまま転送される。末尾が後勝ちなので、その回だけ別プロバイダへ上書きもできる。

```
tsorg --dry-run
tsorg --provider anthropic
tsorg --project Webs__portfolio
tsdel --yes
```

### 実行先の切り替え

- Windows の `.cmd` 版は、リポジトリ直下に `config.wsl.json` があれば WSL 内で `python3 cli.py …` を実行する。無ければ Windows の python で実行し、`config.local.json`（あれば）を読む。Windows⇄WSL 境界越しの HTTP POST は連続実行で不安定なため、ローカル LLM を WSL の ollama で動かす構成ではツール自体を WSL 内で動かす。
- macOS/Linux の posix 版はこの分岐を持たず、常に `python3` で実行し、`config.local.json` があればそれを、無ければ `config.json` を読む。

OS 別の設定例（`config.local.json` / `config.wsl.json`）と ollama の接続先は README の短縮コマンド節にまとめてある。`data_dir` を既定のままにすれば、実行環境が違っても同じ台帳を共有する。

---

## 6. 設定ファイル `config.json`

リポジトリ直下の `config.json` が既定。別設定で動かすときは `--config path/to.json`。よく触る項目は次の通り。全キーは DESIGN.md の「設定」を参照。

| キー | 既定 | 意味 |
|---|---|---|
| `provider` | `gemini` | 既定 LLM プロバイダ（`--provider` で都度上書き可） |
| `scan_base` | `~/.claude/projects` | 会話の走査ルート |
| `roots.PROJECTS` | `~/File/projects` | プロジェクト群のルート（ラベル解決の基準） |
| `containers` | `[Other, School, Webs, …]` | `comp__sub` ラベルにする中間ディレクトリ |
| `aliases` | `[]` | 移動した cwd の読み替え `[["旧prefix", "新prefix"]]` |
| `exclude_globs` | `["*autonomous*"]` | 走査から除外するパス |
| `include_sidechain` | `false` | true でサブエージェントログも抽出対象に |
| `protect_recent_minutes` | `30` | 直近活動を保護する分数 |
| `condense_cap` | `22000` | 1会話の凝縮上限（超過は頭60%/尾40%） |
| `min_msgs` / `min_chars` | `2` / `400` | これ未満は `trivial` として除外 |
| `retries` | `2` | LLM 失敗時の再試行回数（尽きたらその会話だけスキップ） |
| `delete.trash_retention_days` | `14` | trash の保持日数 |
| `protect_session_ids` | `[]` | 常に保護するセッション ID |

API キーは `config.json` に書かず環境変数で渡す（`providers.<name>.api_key_env` がその変数名）。ローカル専用の上書きは `config.local.json`（.gitignore 済み）に置く。

---

## 7. データの置き場所（`data/`、.gitignore 済み）

```
data/ledger.json            処理済みセッションの台帳（差分判定の核）
data/findings/<label>.json  ラベル別に蓄積した findings
data/trash/<日付>/…         delete --yes で退避した会話（保持期間内は復元可）
```

`data_dir` を未指定にするとリポジトリ直下 `data/` に解決される。

- HANDOFF を作り直したい → `data/findings/` は残したまま該当 HANDOFF を消して `organize`、または `organize --rebuild`。
- 完全にやり直したい → `data/` を消す。台帳も消えるので、次回は全会話が未処理として再抽出される。

---

## 8. よくある操作レシピ

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

## 9. テスト

```bash
python -m pytest -q        # ネットワーク不要（mock provider で LLM を差し替え）
```

---

## 10. トラブルシュート

| 症状 | 原因と対処 |
|---|---|
| `GEMINI_API_KEY is not set` 等で即停止 | そのプロバイダの環境変数が未設定。`export`（Windows は `setx` か `$env:`）で渡す。誤送信防止の正常な挙動 |
| `extract_failed` が多発 | API キーの誤り・レート制限・モデル名の誤り。`--verbose` で末尾の例外を確認。`retries` を上げる |
| ollama に繋がらない | `ollama serve` が起動しているか、`endpoint` のホスト/ポートが合っているか。別マシンなら相手側を `OLLAMA_HOST=0.0.0.0` で待ち受けさせる |
| 思考モデルが遅い・冗長 | `config` の ollama に `"think": false` を足して thinking 出力を抑止する |
| WSL 越しで POST が不安定 | ツール自体を WSL 内で実行する構成にする（`config.wsl.json` を置き、`tsorg` の `.cmd` 版から WSL 実行へ切り替える） |
| Windows で日本語が文字化け | 短縮コマンド（`.cmd`）は `chcp 65001` と `PYTHONUTF8=1` を設定済み。素の `python` 実行なら `set PYTHONUTF8=1` を併用する |
| posix 版ラッパーで `python3 not found` | macOS/Linux/WSL 向け。Windows ネイティブでは `.cmd` 版（`python`）を使う |
| ラベルが全部 `_archive` になる | `roots.PROJECTS` が実環境と違う、または `aliases` の読み替えが不足。`--verbose` の `route` 行で root を確認 |

---

## 11. 注意点

- このツールは同期しない。退避後に他マシンへ反映したいなら、別途同期ツールを手動で実行する。
- `delete` は履歴を消すのではなく `data/trash/` へ動かすだけ。完全に消えるのは保持期間超過後の GC 時。
- `status` の「未処理」には保護対象（active 等）も含まれるため、実際に organize される数とは一致しないことがある。
- findings の状態系（完成/未完）は最新（`last_seen` 降順）が上に出るが、古い項目を自動で打ち消しはしない。
