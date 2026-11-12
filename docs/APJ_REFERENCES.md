# ApJ / AAS 用 Reference の出力と検証

## 1. 責務の分離
| 要素 | 役割 | 管理元 |
|---|---|---|
| `references.bib` | 書誌データ | Zotero + Better BibTeX 自動エクスポート |
| `aasjournalv7*.bst` | Reference の書式 | AAS 公式（改変しない） |
| `aastex7xx.cls` | 文書構造 | AAS 公式（改変しない） |

Paper Navigator は ApJ の見た目を独自に生成しません。公式スタイルで BibTeX/LaTeX をコンパイルし、ログを検査します。
`.bst` を使ってコンパイルできたことは、原稿全体が投稿規定に適合することを意味しません（最終確認は AAS の現行ガイドと投稿前チェックリスト）。

## 2. 公式ファイルの入手（確認日 2026-11-12）
- AAS サイト https://journals.aas.org/authors/aastex.html: 最新 **AASTeX v7.0.2（2026-06-01）**、推奨 **`aasjournalv7.1.bst`**。
- 公式 GitHub https://github.com/AASJournals/AASTeX7（commit `a22d749`, 2025-08-27）: `aastex701.cls`（v7.0.1）、`aasjournalv7.bst`。
- `./scripts/fetch_aastex.sh` は GitHub の固定コミットを `vendor/aastex/` に無改変で取得し、出典と SHA256 を記録します。
  AAS サイトから v7.0.2 の ZIP を取得できる場合は、その `.cls`/`.bst` を `vendor/aastex/` に置き、`.tex` の
  `\documentclass` と `\bibliographystyle` を同梱サンプルの書き方に合わせてください（v7.0.2 は本環境では未検証）。
- TeX Live では `texlive-latex-extra` に加え `texlive-plain-generic`（`epsf.sty`）が必要でした。AASTeX v7.0.1 は全著者に `\email` を要求します。

## 3. 原稿の書き方（公式サンプル準拠）
```latex
\documentclass{aastex701}
...
\citep{astropycollaboration2013}   % 括弧付き
\citet{corrales2015}               % 本文中
...
\bibliography{references}{}
\bibliographystyle{aasjournalv7}
```
サンプル: [examples/apj/sample_apj.tex](../examples/apj/sample_apj.tex)、[examples/apj/references.bib](../examples/apj/references.bib)
（書誌は AASTeX7 公式サンプル `sample701.bib`〔ADS からのエクスポート〕を無改変で転記し、キーのみ BBT 形式に変更。実在する文献のメタデータ）。

## 4. 検証手順
```bash
uv run pn bib-check references.bib                 # 構文・重複キー/DOI・必須項目・DOI形式
uv run pn cite-check references.bib main.tex       # \citep/\citet 等のキーが .bib にあるか
uv run pn apj-build main.tex --bib references.bib  # pdflatex → bibtex → pdflatex ×2、ログ解析
```
`apj-build` の判定: `success`（PDF 生成）と `clean`（未解決引用・BibTeX 警告/エラーなし）を分けて報告します。

## 5. 実施結果（2026-11-12、本環境）
- 環境: pdfTeX 3.141592653-2.6-1.40.25 / BibTeX 0.99d（TeX Live 2023/Debian）
- スタイル: `vendor/aastex/aastex701.cls`、`vendor/aastex/aasjournalv7.bst`（GitHub commit a22d749、無改変）
- コマンド: `pdflatex -interaction=nonstopmode -halt-on-error sample_apj.tex` → `bibtex sample_apj` → `pdflatex` ×2
- 結果: **成功・clean**（未解決引用 0、BibTeX 警告 0、BibTeX エラー 0）。記録: [verification/apj_build_report.json](verification/apj_build_report.json)、
  [verification/apj_sample.bbl.txt](verification/apj_sample.bbl.txt)、[verification/apj_sample.blg.txt](verification/apj_sample.blg.txt)、[1ページ目](verification/apj_sample_page1.png)
- LaTeX 警告 1 件: 「`aastex701` を要求したがクラスは `aastex7` を提供」— 公式 v7.0.1 配布物のファイル名とクラス名の差による（公式サンプルでも同じ）。出力への影響はなし。
- 異常系（自動テスト）: 存在しないキー → `undefined_citations` と BibTeX 警告で検出、スタイル不在 → エラー、DOI 欠落 → `bib-check` で `MISSING_RECOMMENDED`、`.bib` コメント中の `@` → `STRAY_AT`（BibTeX はコメント中の `@` をエントリ開始と解釈するため。開発中に実際の BibTeX エラーとして発見）。
- 未検証: AASTeX v7.0.2 / `aasjournalv7.1.bst`、利用者の実原稿。
