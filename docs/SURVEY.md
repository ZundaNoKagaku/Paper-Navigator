# 作業開始時の調査記録（2026-11-12）

## 既存環境・リポジトリ
- 作業ディレクトリ `/home/claude` に既存リポジトリ・README・CLAUDE.md・AGENTS.md・設計書・pyproject・テスト・CI は**なし**。Git 履歴もなし → 新規作成（ADR-001）。
- OS: Linux x86_64。Python 3.13.18、uv 0.11.32、git あり。
- TeX: TeX Live 2023（pdflatex, bibtex, natbib）。AASTeX・`aasjournal*.bst` は未導入。`epsf.sty` 不足を後に発見し `texlive-plain-generic` を導入。
- APIキー: `ADS_API_TOKEN` 等の関連環境変数なし（値は表示していない）。
- ネットワーク: PyPI・GitHub は到達可。**api.adsabs.harvard.edu・journals.aas.org・CTAN はプロキシで拒否**。

## 添付資料
- 実装指示書 `paper_navigator_claude_opus55_implementation_prompt.md`: 全文読了。
- **`software_specification_checklist.md`: 未添付**（ファイルシステム全体を検索して不在を確認）→ 利用者に通知、監査は保留。

## 再利用したもの
- 既存コードなし。外部: AAS 公式 AASTeX7 リポジトリ（サンプル構成・書誌データ）、ADS 公式 dev-api リポジトリ（OpenAPI 定義）、PyVis 同梱 vis-network。

## 不足している前提条件
ADS トークンと到達性（ライブ検証不可）、Zotero 実機（実機検証不可）、AAS サイトの最新配布物（v7.0.2 未取得）、チェックリスト原本。

## 実装計画（実施順）
A 調査・外部仕様確認 → B DB・設定・ADS → C グラフ・可視化 → D Zotero・BibTeX・ApJ → E UI・CLI → F 総合テスト・文書・監査。

## 確定事項・仮定・提案・未決
| 区分 | 内容 |
|---|---|
| 確定 | ADS の `references()`/`citations()` の意味、rows 最大 2000、Zotero 書き込みは 10+、BBT v8+ はキー常時固定、AASTeX 現行は v7 系・`aasjournalv7*.bst` |
| 仮定 | 単独利用者・ローカル PC、ADS を主データソースとする |
| 提案 | OpenAlex/Crossref による補完、重複候補の確定 UI（TODO.md） |
| 未決 | ライセンス、v7.0.2 への切替、チェックリスト監査、実 ADS/Zotero での受入れ |
