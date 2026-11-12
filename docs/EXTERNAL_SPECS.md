# 外部仕様の確認記録

確認日はすべて **2026-11-12**（JST）。確認者: Claude Opus 5.5（実装担当）。
「確認方法」が「Web閲覧」のものは公式ページ本文を取得して確認、「リポジトリ」は公式GitHubリポジトリを clone して確認した。

## 1. NASA ADS API

| 項目 | 採用した仕様 | 出典 | 確認方法 |
|---|---|---|---|
| ベースURL・認証 | `https://api.adsabs.harvard.edu/v1`、`Authorization: Bearer <token>` | https://github.com/adsabs/adsabs-dev-api （README、commit 2e221c0, 2025-04-21） | リポジトリ |
| 検索エンドポイント | `GET /search/query`、`q`（≤1000文字）、`fl`、`rows`、`start`、`sort` | 同 `openapi/parameters.yaml` | リポジトリ |
| ページング | `rows` 既定10・**最大2000**、`start` は0起点オフセット | 同 `parameters.yaml` (`rows.maximum: 2000`) | リポジトリ |
| 取得フィールド | `bibcode, alternate_bibcode, title, author, year, pub, bibstem, volume, issue, page, page_range, doi, identifier, abstract, doctype`（すべて `fl` enum に存在） | 同 `parameters.yaml` | リポジトリ |
| `references()` / `citations()` | `references(q)` = q に一致した論文が**引用している**論文、`citations(q)` = q に一致した論文を**引用している**論文 | https://ui.adsabs.harvard.edu/help/search/citations-and-references | Web閲覧 |
| レート制限 | 通常 5000 リクエスト/日。応答ヘッダ `X-RateLimit-Limit / -Remaining / -Reset`（Reset はUTCエポック秒、UTC 0時にリセット） | https://adsabs.github.io/help/policies/rate-limits 、adsabs-dev-api README | Web閲覧 |
| 利用条件 | ADS データへのアクセスは ADS 利用規約に従う。Abstract・論文の著作権は出版社にあり、個人利用は無料 | adsabs-dev-api README（Terms of Use への言及）、https://adsabs.harvard.edu/abs_doc/faq.html | Web閲覧 |

**未確認:** `ui.adsabs.harvard.edu/help/api/api-docs.html` は取得ツールの許可リスト外で本文未確認。HTTP エラー応答の正式な一覧（401/429/5xx の本文形式）は公式文書で確認できなかったため、
実装は HTTP ステータスのみで分類し、本文形式に依存しない。API への**ライブ接続は開発環境から不可**（プロキシで拒否）。

## 2. Zotero Local API

| 項目 | 採用した仕様 | 出典 |
|---|---|---|
| エンドポイント | `http://localhost:23119/api/`、Web API v3 と同形式、ユーザーID `0` | https://www.zotero.org/support/dev/web_api/v3/local_api （Web閲覧） |
| 有効化 | 設定 → 詳細 → 「このコンピュータ上の他のアプリケーションとZoteroが通信することを許可」。無効時は `403` | 同上 |
| 読み取り認証 | 不要（そのためポートを外部公開してはならない） | 同上 |
| 書き込み | **Zotero 10 以上のみ**。`POST /api/local/authorize`（`appName`、`Zotero-Server-ID` ヘッダ）で利用者がダイアログで許可 → キー。`Zotero-API-Key` ヘッダで送信。キー欠落/不正 `401`、拒否 `403`、`Zotero-Server-ID` 欠落 `428`・不一致 `412`、許可要求は1分5回まで（超過 `429`） | 同上 |
| ページング | Local API は既定でページングなし（`limit`/`start` は有効） | 同上 |
| 導入バージョン | 読み取りの Local API は Zotero 7 で導入（Zotero 7 beta 88 で公開） | https://groups.google.com/g/zotero-dev/c/ElvHhIFAXrY （開発者 ML、Web検索結果） |

**未確認:** `X-Zotero-Version` 応答ヘッダが `/api/` で常に返るかは公式ページに記載なし（フォーラムでコネクタ応答に付与される例あり）。返らない場合、本実装は「バージョン不明 → 書き込み非対応」と安全側に判定する。実機 Zotero での動作は未検証。

## 3. Better BibTeX for Zotero

| 項目 | 採用した仕様 | 出典 |
|---|---|---|
| 自動エクスポート | コレクション右クリック → 「コレクションをエクスポート…」→ 形式「Better BibTeX」→「Keep updated」をチェック → 保存先指定。以後の変更で自動再出力。管理は BBT 設定の「Automatic export」タブ | https://retorque.re/zotero-better-bibtex/exporting/auto/ （Web検索結果本文） |
| 引用キーの固定 | BBT v8.0.0 以降「ピン留めの概念は廃止、キーは常に固定」。キーは Zotero ネイティブの引用キーフィールドに保存 | https://retorque.re/zotero-better-bibtex/changelog/ （Web閲覧） |
| 対応Zotero | BBT v9.0.0 以降は Zotero 8+ 専用、v9.0.76 は Zotero 10 / 11 beta 対応。changelog の最新は v9.0.77（日付記載なし） | 同上 |
| 自動エクスポートの前提 | Zotero 起動中のみ再出力される | Web検索結果（複数の利用ガイド。一次資料での明記は未確認） |

## 4. AAS / AASTeX

| 項目 | 確認結果 | 出典 |
|---|---|---|
| 現行版 | AAS サイトの一覧: **AASTeX v7.0.2（2026-06-01）**、v7.0.1（2025-05-29）、v7.0（2025-03-04） | https://journals.aas.org/authors/aastex.html （Web閲覧） |
| BibTeX スタイル | サイトの推奨: **`aasjournalv7.1.bst`**（AASTeX v7+ の全原稿で使用）。旧 `aasjournal.bst`（v2019）は v6+ 用 | 同上 |
| 公式 GitHub | https://github.com/AASJournals/AASTeX7 の最新コミット `a22d749`（2025-08-27）: `aastex701.cls`（v7.0.1）、`aasjournalv7.bst`（2025-03-04版） | リポジトリ |
| 公式サンプルの書き方 | `\documentclass{aastex701}`、`\bibliography{sample701}`、`\bibliographystyle{aasjournalv7}` | 同リポジトリ `sample/sample701.tex` |
| v7 の引用表記変更 | 本文中引用に名の頭文字を含める（例 “G. Smith et al. (2022)”）。PSJ では Reference にタイトル | https://journals.aas.org/introducing-aastex-v7-0/ |
| ライセンス | LaTeX Project Public License 1.3c | CTAN aastex ページ、リポジトリ LICENSE |

**判断:** 指示書は `aasjournal.bst` を挙げているが、AAS 一次資料では v7 用は `aasjournalv7*.bst` であるため、現行版に合わせた（ADR-007）。
**未確認・未検証:** v7.0.2 と `aasjournalv7.1.bst` は journals.aas.org への接続が開発環境から拒否され取得できず、コンパイル検証は GitHub 版 v7.0.1 + `aasjournalv7.bst` で実施。

## 5. 採用ライブラリ（uv.lock で固定）

| パッケージ | 版 | 確認事項 |
|---|---|---|
| httpx | 0.28.1 | `MockTransport` によるオフラインテスト |
| SQLAlchemy | 2.1.8 | 2.x ORM（`Mapped`/`mapped_column`） |
| NetworkX | 3.7 | Python ≥3.12 必須（このため `requires-python >=3.12`）。`node_link_data(edges="edges")` |
| PyVis | 0.3.2 | 同梱の vis-network 9.1.2 を使用。PyVis 標準テンプレートはツールチップを `innerHTML` で描画するため独自テンプレート（ADR-005） |
| Streamlit | 1.67.0 | `use_container_width` は非推奨 → `width`、`components.v1.html` は非推奨 → `st.iframe` |
| bibtexparser | 1.4.4 | v2 系はAPI非互換のため 1.x に固定。ライセンス LGPLv3 または BSD |
| pytest 9.2.0 / ruff 0.17.4 / mypy 2.4.1 / pip-audit / pip-licenses | — | 開発用 |
