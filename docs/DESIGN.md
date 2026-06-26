# 設計ドキュメント (DESIGN)

claude-transcript-organizer のアーキテクチャと設計判断のまとめ。操作方法は [USAGE.md](USAGE.md) を参照。

## 設計思想

**「LLM は提案、コードが統合」。** LLM は各会話から findings（構造化された事実）を *提案* するだけで、台帳・findings ストア・HANDOFF への書き込みはすべて決定論的な Python が担う。これにより、LLM の失敗・不正な出力・API 障害が起きても、台帳や HANDOFF が壊れることはない（その会話だけスキップされ、未処理として残る）。

- 標準ライブラリのみ（追加依存なし）。
- **差分処理**: 会話は台帳で一度だけ処理。再実行は増えた分だけ。
- HANDOFF.md は専用マーカー区間のみ自動生成し、人間の記述は不可侵。

## 処理フロー

```mermaid
flowchart TD
    A["scan_base 配下の *.jsonl を走査<br/>(discover.iter_conversations)"] --> B{"台帳に登録済み?<br/>(ledger)"}
    B -- yes --> SKIP1["skip: ledger"]
    B -- no --> C["凝縮 (condense)<br/>本文のみ・上限超過は頭60%/尾40%"]
    C --> D{"分類 (classify)<br/>active / sidechain / meta / trivial"}
    D -- 該当 --> SKIP2["skip: 各理由で保護/除外"]
    D -- 通過 --> E["ルーティング (route)<br/>cwd → label / 書き込み先 root"]
    E --> F["LLM 抽出 (extract)<br/>会話1件=1呼び出し・JSONスキーマ拘束"]
    F -- 失敗 --> SKIP3["skip: extract_failed<br/>(台帳に記録しない)"]
    F -- 成功 --> G["FindingStore.merge<br/>kind|text のハッシュIDで重複排除"]
    G --> H["台帳に記録 (ledger.mark)"]
    H --> I["HANDOFF.md のマーカー区間を再生成<br/>(render + update_handoff)"]
```

## モジュール構成

| モジュール | 役割 |
|---|---|
| `config.py` | `config.json`＋既定値の読込（`load_config`） |
| `discover.py` | jsonl 走査・cwd/timestamp/メタ抽出・分類（`iter_conversations` / `classify`） |
| `condense.py` | jsonl → 本文のみの凝縮文字列（ツール使用・エラー要約・上限処理） |
| `route.py` | 会話の `cwd` → ラベルと書き込み先 `root` を決定 |
| `extract.py` | 凝縮文 → findings 提案プロンプト構築・JSON 検証 |
| `providers/` | LLM バックエンド（gemini / anthropic / openai / ollama）＋共通 HTTP |
| `findings.py` | findings の永続化と ID ベース重複排除・出典累積（`FindingStore`） |
| `ledger.py` | 処理済みセッション台帳（原子的書き込み） |
| `render.py` | findings → HANDOFF マーカー区間の生成・差し替え |
| `deleter.py` | 処理済み会話の trash 退避・保持期間 GC |
| `pipeline.py` | 上記を束ねる `organize` / `status` |

## ラベル解決（route）

会話 transcript に記録された `cwd` を `roots.PROJECTS` と照合してラベルと書き込み先を決める。

- `PROJECTS/<comp>` 直下 → ラベル `<comp>`、root は `PROJECTS/<comp>`
- `containers` に属する中間ディレクトリ配下 → ラベル `<comp>__<sub>`
- 解決できない cwd → `_archive`（`archive_root` に集約）

パス照合は `/` に正規化して行い、返す `root` は実行 OS ネイティブ形式で生成する。これにより、Windows パス形式で記録された `cwd` を `aliases` で別 prefix（例: WSL の `/mnt/...`）へ読み替えても破綻しない。

## 差分処理と重複排除

- **台帳**（`ledger.json`）: セッション ID をキーに持つ dict。`is_processed` で再処理を防ぐため、各会話は生涯一度だけ抽出される。
- **findings 重複排除**: `normalize_id(kind, text)`（空白・記号を正規化した `kind|text` の SHA1）で同一 finding を統合。出典タイトル・タイムスタンプは累積し、`confidence` は最大値を採用。

## プロバイダ

`providers.<name>` で切替。API キーは環境変数（`api_key_env`）で渡し、`config.json` には書かない。未設定のまま呼ぶとリクエスト前に明示エラーで停止する（誤送信防止）。`ollama` はローカル/自前エンドポイントのため API キー不要。思考モデルは `think:false` で冗長な thinking 出力を抑止できる。

## 安全性

- HANDOFF.md は `<!-- BEGIN transcript-organizer -->` … `<!-- END -->` のマーカー区間のみ再生成し、区間外は一切変更しない。
- `delete` は既定 dry-run。実体は trash への退避で、保持期間内は復元可能。台帳に無い会話・直近活動・サイドチェーン・保護セッションは常に保護。
