# Paper Navigator (P0)

個人研究者向けの、ローカル中心の論文引用ネットワーク・Reference管理システムです。
NASA ADS から論文メタデータと References / Citations を取得して SQLite に保存し、
NetworkX の有向グラフとしてブラウザで可視化します。書誌情報の正本は Zotero + Better BibTeX とし、
ApJ 投稿用の Reference は AAS 公式の AASTeX と BibTeX スタイルでコンパイルして出力します。

主な対象分野は天文学・天体物理学（特に太陽物理学）ですが、データモデルは分野非依存です。

> **エッジの向き:** `A → B` は「論文Aが論文Bを引用している」を意味します（DB・UI・全エクスポート共通）。
> 引用関係は研究上の影響関係を完全には表さず、引用数は研究の質や重要度を示しません。

## 機能範囲（P0 = 今回実装済み）

| 機能 | 状態 | 主な入口 |
|---|---|---|
| ADS検索（タイトル / DOI / Bibcode / arXiv ID、年範囲） | 実装・モック検証済み、**ライブ未検証** | `pn search` / UI「検索」 |
| References / Citations 取得（ページング・再試行・レート制限・部分成功） | 実装・モック検証済み、**ライブ未検証** | `pn network` |
| 引用グラフ（重複統合・循環許容・階層/件数/リクエスト上限・期間） | 実装・検証済み | `pn network` / UI「引用グラフ」 |
| グラフ表示（起点★/先行●/後続▲を形と色で区別、ノードクリックで詳細、年/役割/階層フィルタ） | 実装・検証済み | UI / エクスポートHTML |
| エクスポート（HTML, JSON node-link, GraphML, エッジCSV） | 実装・検証済み | `pn export-graph` |
| SQLite永続化（マイグレーション・制約・ロールバック・キャッシュ・取得履歴） | 実装・検証済み | 自動 |
| Zotero Local API（状態判定・コレクション読取・照合・不一致記録） | 実装・モック検証済み、**実Zotero未検証** | `pn zotero-*` / UI |
| Zoteroへの追加（Zotero 10+ のみ、利用者の許可が必要） | 実装・モック検証済み、**実Zotero未検証** | `pn zotero-add` |
| Better BibTeX `.bib` 検証（構文・重複キー/DOI・必須項目・DOI形式・キー変更検出） | 実装・検証済み | `pn bib-check` |
| `\citep`/`\citet` と `.bib` のキー整合チェック | 実装・検証済み | `pn cite-check` |
| ApJ Reference コンパイル検証（AASTeX v7.0.1 + `aasjournalv7.bst`） | 実装・**実コンパイル検証済み** | `pn apj-build` |
| ローカルWeb UI（Streamlit、127.0.0.1のみ） | 実装・検証済み | `pn ui` |

**P1以降（未実装）:** 日本語翻訳、PDFダウンロード・本文抽出、Docling/GROBID、LLM翻訳、共引用・書誌結合分析、AI要約。
詳細は [TODO.md](TODO.md)。

## 必要環境

- Python 3.12 以上（3.13.18 / Linux で検証。macOS・Windows は未検証）、[uv](https://docs.astral.sh/uv/)（0.11 で検証）
- NASA ADS API トークン（検索・引用取得に必須。無くてもキャッシュ済みデータとBibTeX機能は使えます）
- 任意: Zotero 7 以上（読み取り）。Local API からの書き込みは **Zotero 10 以上** が必要
- 任意: Better BibTeX for Zotero（`.bib` 自動エクスポート）
- 任意: TeX Live（`pdflatex`, `bibtex`）。Debian/Ubuntu では `texlive-latex-extra` と
  `texlive-plain-generic`（AASTeX が `epsf.sty` を読み込むため）が必要

## セットアップ

```bash
git clone <this repository> paper-navigator && cd paper-navigator
uv sync                       # uv.lock どおりに依存関係を導入
cp .env.example .env          # ADS_API_TOKEN= の後にトークンを記入（.env はGit管理外）
uv run pn init-db             # data/paper_navigator.sqlite3 を作成（マイグレーション適用）
uv run pytest                 # オフラインテスト（ネットワーク不要、ライブテストは除外）
./scripts/fetch_aastex.sh     # 任意: AAS公式AASTeX（GitHub、固定コミット）を vendor/aastex/ へ
```

ADS トークンは https://ui.adsabs.harvard.edu/user/settings/token で発行します。

## 起動・停止

```bash
uv run pn ui                  # http://127.0.0.1:8501 （既定で 127.0.0.1 のみ待ち受け）
# 停止: ターミナルで Ctrl+C。データは data/ に残り、再起動後もそのまま使えます。
```

`--address 0.0.0.0` 等で外部公開もできますが、ローカルDBとZoteroへのアクセスがネットワークに
露出するため警告を表示します。既定のままの利用を推奨します。

## 使い方（CLI）

```bash
uv run pn search "coronal mass ejection" --year-from 2015 --max 20
uv run pn search 10.1086/146579                       # DOI / Bibcode / arXiv は自動判定
uv run pn network 1998ApJ...509..678G --direction both --depth 1 --max-papers 300 \
                  --export-dir data/exports
uv run pn jobs                                         # 取得履歴（部分成功・打ち切りを表示）
uv run pn export-graph 3 --year-from 2010              # HTML / JSON / GraphML / CSV
uv run pn show 1998ApJ...509..678G
uv run pn duplicates                                   # 重複候補（自動統合しない）
uv run pn backup                                       # data/backups/ に DB のコピー

uv run pn zotero-status                                # unavailable / local_api_disabled / read_only / ...
uv run pn zotero-collections
uv run pn zotero-sync ABCD1234                          # Zotero は変更せず、照合結果をDBに記録
uv run pn zotero-authorize                             # Zotero 10+: 書き込み許可ダイアログ
uv run pn zotero-add 1998ApJ...509..678G --collection ABCD1234

uv run pn bib-check ~/thesis/references.bib --snapshot data/bib_snapshot.json --accept
uv run pn cite-check ~/thesis/references.bib ~/thesis/main.tex
uv run pn apj-build examples/apj/sample_apj.tex --bib examples/apj/references.bib
```

終了コード: `0` 成功 / `2` 部分成功・警告あり / `1` 失敗。

## 設定

`.env.example` を参照。主な項目: `ADS_API_TOKEN`、`PN_DB_PATH`、`PN_CACHE_TTL_DAYS`（既定30日）、
`PN_NETWORK_DEPTH`（既定1）、`PN_NETWORK_MAX_PAPERS`（既定300）、`PN_NETWORK_MAX_REQUESTS`（既定50）、
`ZOTERO_BASE_URL`（ループバックのみ許可）。300などの値は安全側の初期値で、すべて変更可能です。

## Zotero / Better BibTeX / ApJ

- 導入と自動エクスポートの設定手順: [docs/ZOTERO_BBT_SETUP.md](docs/ZOTERO_BBT_SETUP.md)
- ApJ Reference の作り方と検証: [docs/APJ_REFERENCES.md](docs/APJ_REFERENCES.md)

## 制限事項（重要）

- NASA ADS・Zotero 実機への**ライブ接続は未検証**です（開発環境から ADS API に到達できず、
  Zotero も存在しないため）。すべてモックで検証しています。初回利用時に
  `ADS_API_TOKEN=... uv run pytest -m live` を実行してください。
- Zotero 7〜9 では Local API が読み取り専用のため、`zotero-add` は「未対応」を返します
  （成功したようには表示しません）。代わりに Zotero の「識別子で追加」に DOI を入力してください。
- AAS サイトは AASTeX v7.0.2（2026-06-01）と `aasjournalv7.1.bst` を最新としていますが、
  開発環境から取得できたのは AAS 公式 GitHub の v7.0.1 / `aasjournalv7.bst` です。
- `.bst` を使ったことは投稿規定全体への適合を意味しません。最終確認は AAS の現行ガイドで行ってください。
- ADS の取得データは個人利用の範囲で扱ってください（ADS 利用規約、Abstract の著作権は出版社）。

## ドキュメント

[仕様書](docs/SYSTEM_SPECIFICATION.md) ・ [アーキテクチャ](docs/ARCHITECTURE.md) ・ [運用](docs/OPERATIONS.md) ・ [開発・変更管理](docs/DEVELOPMENT.md) ・
[技術判断](docs/DECISIONS.md) ・ [外部仕様の確認記録](docs/EXTERNAL_SPECS.md) ・
[トレーサビリティ](docs/TRACEABILITY_MATRIX.md) ・ [テスト計画と結果](docs/TEST_PLAN.md) ・
[チェックリスト監査](docs/SOFTWARE_SPECIFICATION_CHECKLIST_AUDIT.md) ・ [CHANGELOG](CHANGELOG.md) ・ [TODO](TODO.md)
