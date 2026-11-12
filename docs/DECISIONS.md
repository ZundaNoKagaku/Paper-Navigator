# 技術判断記録（ADR）

すべて 2026-11-12 決定。状態: 採用。

## ADR-001 新規リポジトリとして実装
- 背景: 作業環境に既存リポジトリ・README・CLAUDE.md・設計書は存在しなかった。
- 決定: `paper-navigator/` を新規作成（src レイアウト、uv 管理）。
- 代替案: なし（尊重すべき既存規約がない）。

## ADR-002 パッケージ管理は uv、Python ≥3.12
- 決定: uv 0.11 + `uv.lock`。NetworkX 3.7 が Python ≥3.12 を要求するため `requires-python >=3.12`。
- 代替案: pip + requirements.txt（ロックの再現性が弱い）、Poetry（環境に未導入）。

## ADR-003 ADS クライアントは httpx で自作
- 決定: httpx 直接利用。`MockTransport` でオフラインテスト、再試行・エラー分類・部分成功を自前で制御。
- 代替案: 非公式 `ads` パッケージ（エラー分類・ページング部分成功の制御が難しく、依存が増える）。

## ADR-004 DB は SQLite + SQLAlchemy 2.x、マイグレーションは追記型の自前ランナー
- 決定: DDL を版番号付きで `db.MIGRATIONS` に追記し、1 マイグレーション 1 トランザクション、`schema_migrations` に記録。ORM とスキーマの一致はテストで検証。
- 代替案: Alembic（単一ユーザー・小規模に対し設定負荷が大きい。将来必要になれば移行可能）。
- 帰結: 新しすぎるスキーマ（ソフトウェアより新しい版）は起動を拒否する。

## ADR-005 グラフ描画は vis-network（PyVis 同梱）を独自テンプレートで使用
- 背景: PyVis 0.3.2 の標準テンプレートはノードのツールチップを `innerHTML` で描画する（`templates/template.html` 506行）。タイトル・Abstract は外部の信頼できないデータ。
- 決定: PyVis が同梱する vis-network 9.1.2 の JS をインライン化し、データは JSON エスケープして埋め込み、`textContent` で描画する独自テンプレート。CSP で外部読み込みを禁止。HTML 単体でオフライン動作。
- 代替案: PyVis 標準出力（XSS リスク）、CDN 読み込み（オフライン不可）。

## ADR-006 Zotero 書き込みは Local API（Zotero 10+）のみ
- 決定: 公式 Local API の書き込み（10+、利用者許可のキー）だけを使う。Zotero 7〜9 では「未対応」を返し、手動の「識別子で追加」を案内する。
- 代替案: Connector API（`/connector/`）による書き込み（ブラウザ拡張向けの非公開仕様で、公式文書が Local API ページに無い）、Web API（zotero.org アカウント・キーが必要でローカル中心の方針に反する）。

## ADR-007 AAS 公式スタイル `aasjournalv7*.bst` を使用（指示書の `aasjournal.bst` から変更）
- 背景: AAS 一次資料では `aasjournal.bst`（2019）は AASTeX v6+ 用、v7+ は `aasjournalv7.bst` / 最新 `aasjournalv7.1.bst`。公式 v7 サンプルも `\bibliographystyle{aasjournalv7}`。
- 決定: 現行の v7 系を使用。検証は公式 GitHub（固定コミット）の v7.0.1 + `aasjournalv7.bst`。ファイルはリポジトリに含めず `scripts/fetch_aastex.sh` で取得（無改変、SHA256 記録）。
- 未決: AAS サイトの v7.0.2 / `aasjournalv7.1.bst` は取得できず未検証。

## ADR-008 `.bib` はシステムで生成せず Zotero + BBT を正本とする
- 決定: システムは `.bib` を検証するのみ（読み取り専用）。ADS 由来の書誌は Zotero に追加し、BBT 経由で `.bib` 化する。
- 理由: 引用キーの安定性を BBT に一元化し、二重管理によるキー変更・不整合を避ける。

## ADR-009 Streamlit UI は 127.0.0.1 に固定（既定）
- 決定: `.streamlit/config.toml` と `pn ui --address 127.0.0.1` の二重指定。非ループバック指定時は警告。
- 理由: Zotero Local API の読み取りは無認証であり、ローカルデータを外部に露出させない。

## ADR-010 重複は識別子でのみ自動統合
- 決定: DOI → Bibcode → arXiv の一致のみ自動統合。類似タイトルは候補として記録するのみ。
- 理由: 版違い・訂正記事・会議録の誤統合を防ぐ。

## ADR-011 ノードの「役割」は到達経路で定義
- 決定: Reference リスト経由で到達＝`reference`、Citation リスト経由＝`citation`、両方＝`both`。
- 理由: 深さ2以上では「起点より古い/新しい」とは一致しないため、取得の事実に基づく定義にした（凡例に明記）。

## ADR-012 重複候補検索の SQL 事前絞り込みと索引（v0.1.1、マイグレーション v2）
- 背景: 性能測定で、論文保存時の重複候補検索が同時期の全論文とタイトル比較するため、5000 件で 156 秒（二次的増加）だった。
- 決定: 候補条件（第一著者の姓一致）を SQL で先に絞り込み、`papers(year)` と `paper_authors(lower(family), position)` に索引を追加。v0.1.0 を配布済みのため v1 スキーマは変更せず、索引はマイグレーション v2 として追加。
- 結果: 5000 件で 33.8 秒（ほぼ線形）。判定結果は変わらない（候補は元々同姓が条件）。第一著者が無い論文は従来どおり年で絞り込む。
- 代替案: 候補検索の非同期化・後回し（実装が複雑）、索引なしの Python 側フィルタ（DB 読込量が減らない）。
