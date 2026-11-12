# Changelog

## [Unreleased]

### 修正
- `pn ui` でブラウザが自動で開かなかった問題（`.streamlit/config.toml` の `server.headless = true` が原因）。
  headless は維持したまま（Streamlit 初回起動時のメール入力待ちを避けるため）、`/_stcore/health` の応答を確認してから
  `pn ui` 自身が既定ブラウザを開くようにした。`--no-browser` で無効化できる。
- README のコマンド例を、zsh（行末 `#` をコメントとして扱わない）にそのまま貼り付けても動く形に変更し、uv の導入手順を追加。

## [0.1.1] - 2026-11-12 — 仕様書チェックリスト監査に基づく是正

### 追加
- `pn backup`（SQLite バックアップ API による整合したコピー）。
- 起動時の中断ジョブ検出（6 時間以上 running のジョブを failed / `INTERRUPTED` に）。
- `scripts/benchmark.py`（性能・容量の測定）、`scripts/gen_checklist_audit.py`（チェックリスト監査の生成と検算）。
- 文書: `docs/OPERATIONS.md`、`docs/DEVELOPMENT.md`、チェックリスト原本の写し、仕様書 v0.2（識別子・命名規則・入出力表・CRUD・状態遷移・並行処理・測定可能な非機能要件・脅威整理・エラー重大度・自己レビュー）。

### 変更
- グラフの役割を色だけでなく形・記号（★●▲◆）でも区別（アクセシビリティ）。後続研究は ▲。
- グラフ初期配置の乱数シードを固定（再現性）。
- 重複候補検索を第一著者の姓で SQL 事前絞り込み。索引をマイグレーション v2 で追加（5000 論文で 156 秒 → 34 秒）。
- 要件を細分化（39 → 58 件、非機能要件を含む）し、トレーサビリティ表に「要件・期待動作」列を追加。
- 要件 PN-DB-004 の曖昧な表現（「など」）を具体化。

## [0.1.0] - 2026-11-12 — P0 初期実装

### 追加
- NASA ADS 検索（タイトル/DOI/Bibcode/arXiv、年範囲）、References/Citations 取得。ページング（`start`/`rows`、最大2000）、`Retry-After` 対応の指数バックオフ、日次上限枯渇時の即停止、部分成功、エラー分類。
- SQLite スキーマ v1（論文・順序付き著者・識別子・引用エッジ・取得状態・取得ジョブ・ジョブ所属・重複候補・Zotero リンク・照合結果・エクスポート記録）と追記型マイグレーション。
- 識別子優先の重複排除（DOI → Bibcode → arXiv）、類似タイトルは候補記録のみ。
- 引用ネットワーク構築（BFS、階層/論文数/リクエスト数/期間の上限、打ち切り記録、キャッシュ再利用）。
- グラフ表示（vis-network、役割の色分け、クリックで詳細、フィルタ）、HTML/JSON/GraphML/CSV エクスポート。
- Zotero Local API クライアント（状態判定、コレクション読取、Zotero 10+ の書き込み・認可）、ADS/Zotero 照合と不一致記録。
- Better BibTeX `.bib` 検証、スナップショットによる引用キー変更検出、`\cite` キー整合チェック。
- AASTeX + AAS 公式 `.bst` によるコンパイル検証とログ解析、ApJ サンプル、`scripts/fetch_aastex.sh`。
- Streamlit UI（5タブ、127.0.0.1）、CLI `pn`。
- 文書一式、トレーサビリティ生成スクリプト、テスト 139 件 + ライブテスト 2 件。

### 開発中に判明し修正した事項
- PyVis 標準テンプレートがツールチップを `innerHTML` で描画するため、独自テンプレートに変更（XSS 対策）。
- BibTeX がコメント中の `@` をエントリ開始と解釈することを実コンパイルで発見し、検証に `STRAY_AT` を追加。
- 引用キーに空白を含むエントリが認識されなかった問題を修正。
- Zotero URL のループバック判定を文字列前方一致から URL 解析に変更（`127.0.0.1.evil.example` を拒否）。
- Streamlit 1.67 の非推奨 API（`use_container_width`, `components.v1.html`）を置換。
- AASTeX v7.0.1 が `epsf.sty` と全著者の `\email` を要求することに対応（README・サンプル）。
- 指示書の `aasjournal.bst` を、AAS 一次資料に基づき v7 用 `aasjournalv7*.bst` に変更（ADR-007）。
