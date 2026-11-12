# 運用・保守・リリース

対象: Paper Navigator 0.1.1。利用者（研究者本人）が運用者を兼ねる。

## 1. 配布・インストール・更新・アンインストール

| 操作 | 手順 |
|---|---|
| 配布 | ソースツリー（Git リポジトリまたは ZIP）。PyPI には公開しない |
| インストール | README「セットアップ」（`uv sync` → `.env` 作成 → `uv run pn init-db`） |
| 更新 | 1) `uv run pn backup` 2) 新しいソースに置き換え（`git pull` または ZIP 展開。`data/` と `.env` は残す）3) `uv sync` 4) `uv run pn init-db`（マイグレーション自動適用）5) `uv run pytest` |
| アンインストール | 1) 必要なら `uv run pn backup` で `data/backups/` を退避 2) Zotero の書き込み許可を取り消す（設定 →「詳細」→「Clear Write Authorizations」）3) ディレクトリごと削除（`.venv/`、`data/`、`vendor/`、`.env` を含む）。システム全体への変更はない |

## 2. リリース物・版番号
- 成果物: ソース（`src/`）、テスト（`tests/`）、文書（`docs/`、README、CHANGELOG、TODO）、サンプル（`examples/`）、スクリプト（`scripts/`）、依存定義（`pyproject.toml`、`uv.lock`）、`.env.example`。AASTeX は含めない（取得スクリプトのみ）。
- 版番号: Semantic Versioning 2.0.0。`MAJOR.MINOR.PATCH`。DB スキーマ・エクスポート形式（CSV 列など）・CLI の互換性を壊す変更は MAJOR、機能追加は MINOR、修正は PATCH。1.0.0 までは MINOR でも互換性が変わり得る。
- 版の記載箇所: `pyproject.toml`、`src/paper_navigator/__init__.py`（ジョブ記録とエクスポートに埋め込まれる）、CHANGELOG。
- リリース判定: [TEST_PLAN](TEST_PLAN.md) §7。

## 3. 設定・データの移行、バックアップ・復元、削除
- 設定の移行: `.env` をそのまま使う。新しい設定項目は `.env.example` を参照（未設定時は既定値）。
- データの移行: 新版の起動時に追記型マイグレーションが自動適用される（例: 0.1.0 → 0.1.1 で v1 → v2）。新しいスキーマの DB を旧版で開くと起動を拒否する。
- バックアップ: `uv run pn backup [--dest DIR]`（既定 `data/backups/<DB名>-<UTC>.sqlite3`）。UI 起動中でも整合したコピーが取れる。推奨タイミング: 更新前、大規模なネットワーク取得の前、投稿前。
- 復元: UI と CLI を停止 → バックアップファイルを `PN_DB_PATH`（既定 `data/paper_navigator.sqlite3`）へコピー（同名の `-wal`/`-shm` ファイルがあれば削除）→ 起動。
- 障害復旧: DB が壊れた場合はバックアップから復元。バックアップが無い場合は DB を削除して `pn init-db` 後、ADS から再取得（Zotero と `.bib` は影響を受けない）。中断したジョブは次回起動時に INTERRUPTED と記録され、取得済みデータは残る。同じ起点で再実行するとキャッシュ済みの部分は再取得しない。
- 削除: `data/` を削除するとすべてのローカルデータ（DB、エクスポート、スナップショット、バックアップ、Zotero 書き込みキー）が消える。

## 4. 定常運用
| 頻度・契機 | 作業 |
|---|---|
| 文献調査のたび | `pn search` → `pn network`（打ち切り表示を確認）→ 必要に応じ上限を上げて再実行 |
| 新しい被引用を確認したいとき | `pn network <起点> --refresh`（キャッシュ TTL 30 日を無視） |
| Zotero に論文を追加した後 | `pn zotero-sync <コレクション>` で不一致（manual_review）を確認 |
| 投稿前 | `pn bib-check references.bib --snapshot data/bib_snapshot.json` → `pn cite-check` → `pn apj-build` → AAS 投稿前チェックリスト |
| 月 1 回程度 | `pn backup`、`uv run pip-audit` 相当の確認（依存の脆弱性） |
| 監視 | 常駐しないため監視は不要。UI 起動中の確認は `/_stcore/health`、取得状況は `pn jobs` |

## 5. 問い合わせ・責任
- 運用責任者・データ所有者: 利用者本人。
- 外部サービスの問い合わせ先: NASA ADS（adshelp@cfa.harvard.edu）、AASTeX（aastex-help@aas.org）、Zotero フォーラム、Better BibTeX の GitHub Issues。
- 本ソフトウェアの保守担当: 未定（利用者が決定）。

## 6. 既知の制限・既知の不具合・回避策
| 制限 | 回避策 |
|---|---|
| ADS・Zotero 実機・AASTeX v7.0.2 で未検証 | 初回に `pytest -m live`、`pn zotero-status`、`pn apj-build` で確認 |
| Zotero 7〜9 では追加できない | Zotero の「識別子で追加」に DOI を入力 |
| BBT 自動エクスポートは Zotero 起動中のみ | `.bib` 検証前に Zotero を起動し、エクスポート更新を確認 |
| タイトル検索はフレーズ一致のみ | DOI・Bibcode で検索するか、ADS の Web 画面で特定してから Bibcode で検索 |
| 重複候補の確定・却下 UI が無い | `pn duplicates` で確認し、必要なら Zotero 側で整理 |
| ADS の引用データ欠落は検出不能 | 重要な論文は出版社ページの参考文献と照合 |
| AASTeX v7.0.1 で「クラス名が aastex7」の警告が出る | 公式配布物の仕様。無視してよい |
| 既知の不具合 | なし（2026-11-12 時点、テスト 144 件成功） |

## 7. サポート対象・保守終了
- サポート対象: 最新版のみ。Python 3.12 以上（Python の公式サポート終了に合わせて最低版を引き上げる）、Zotero 7 以上（書き込み 10 以上）、AASTeX v7 系。
- 保守終了条件: 利用者が決定（未定）。ADS API v1 または Zotero Local API の非互換変更時は、対応版をリリースするまで該当機能は利用不可となる。

## 8. ライセンス・著作権・第三者コンポーネント
- 依存パッケージのライセンス: [verification/licenses.md](verification/licenses.md)（強いコピーレフトなし。bibtexparser は LGPLv3 または BSD の選択）。vis-network（PyVis 同梱、Apache-2.0 または MIT）をグラフ HTML に埋め込む。
- AASTeX: LPPL 1.3c。リポジトリには含めず、利用者が公式から取得（無改変で使用）。ApJ サンプルの書誌は AAS 公式サンプル由来。
- ADS データ: ADS 利用規約に従い個人利用。Abstract を含むエクスポートを再配布しない。
- 本ソフトウェアのライセンス: 未決（利用者が決定）。
