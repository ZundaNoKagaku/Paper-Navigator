# TODO / 残課題・リスク

## P0 の未完了・未検証（優先）
- [ ] **仕様チェックリスト監査**: `software_specification_checklist.md` を受領後、第0〜18章の全項目を監査（docs/SOFTWARE_SPECIFICATION_CHECKLIST_AUDIT.md の手順）。
- [ ] **ADS ライブ検証**: 利用者環境で `ADS_API_TOKEN=... uv run pytest -m live`、および `pn search` / `pn network` を実データで確認。
- [ ] **Zotero 実機検証**: `pn zotero-status`（7/8/9/10 各版での表示）、`zotero-sync`、Zotero 10+ での `zotero-authorize` → `zotero-add`。`X-Zotero-Version` ヘッダが返らない場合の版判定を確認。
- [ ] **Better BibTeX 実出力での検証**: 実際の自動エクスポート `.bib`（Unicode/LaTeX 変換設定違い）で `bib-check` と `apj-build` を実行。
- [ ] **AASTeX v7.0.2 / `aasjournalv7.1.bst`**: AAS サイトから取得してコンパイル検証し、サンプルと文書を更新。
- [ ] ライセンスの決定（利用者判断）。

## 技術的負債
- タイトル検索は ADS のフレーズ一致（`title:"…"`）のみ。部分語検索や著者指定は未対応。
- 重複候補の「確定/別物」を記録する UI・CLI が無い（`duplicate_candidates.status` は `pending` のまま）。
- グラフ HTML は vis-network（約0.5MB）を毎回インライン化する。大量出力時はファイルサイズが大きい。
- 大規模グラフ（数千ノード）の描画性能は未測定。
- `fetch_state` の「完全」は ADS の numFound との一致による。ADS 自体の引用データ欠落は検出不能。
- 型検査は `ignore_missing_imports`。Streamlit UI はロジックを持たない方針だが単体テストは AppTest のみ。

## P1 以降（未実装・今回は意図的に対象外）
- PDF 自動ダウンロード・本文抽出、Docling/GROBID による構造解析
- 日本語翻訳（Ollama/Gemini/ChatGPT/Claude API）、原文との段落対応・数式保護
- 共引用・書誌結合による分野分析、AI による研究動向要約
- OpenAlex / Crossref による欠落メタデータ補完
- 拡張方針: `papers.id` を参照する新テーブル（例 `paper_files`, `translations`）をマイグレーション v2 以降で追加し、新サービスモジュールとして実装（ARCHITECTURE.md §6）。

## リスク
- ADS API の仕様・レート制限の変更（ヘッダ名・上限値）。
- Zotero Local API の書き込み仕様は Zotero 10 で導入された新しいもので、今後変更の可能性。
- BBT の引用キー仕様は v8 で大きく変更された（ピン留め廃止）。古い BBT ではキーが再生成される可能性。
- ADS データの利用条件（個人利用、Abstract の著作権）。エクスポートした HTML/JSON に Abstract が含まれるため再配布しないこと。
