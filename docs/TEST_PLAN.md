# テスト計画と結果

対象: Paper Navigator 0.1.1。要件とテストの対応は [TRACEABILITY_MATRIX](TRACEABILITY_MATRIX.md)（58 要件）。

## 1. テスト分類

| 分類 | 対象 | ファイル | 外部依存 |
|---|---|---|---|
| 単体 | 正規化、クエリ生成、ADS 応答変換・エラー分類・ページング、DB 保存・更新・ロールバック・移行・バックアップ、重複排除、BibTeX 検証、引用キー抽出、設定・秘密情報 | `test_normalize.py`, `test_ads_client.py`, `test_db_repository.py`, `test_bibliography.py`（非 LaTeX）, `test_config_security.py` | なし |
| 結合 | モック ADS → DB → グラフ、部分失敗、キャッシュ、エクスポート、Zotero 応答（正常/停止/無効/版/認可）、照合、ApJ コンパイル | `test_network.py`, `test_zotero.py`, `test_bibliography.py`（`latex` マーカー） | LaTeX テストのみ pdflatex/bibtex と `vendor/aastex` |
| システム／受入れ | Streamlit UI（AppTest でヘッドレス実行）、CLI（サブプロセス）、空 DB からのセットアップ・再起動、バックアップ | `test_ui_cli_acceptance.py` | なし（ADS はモック） |
| 非機能 | 性能・容量（`scripts/benchmark.py`）、セキュリティ（`test_config_security.py`、HTML エスケープ、pip-audit）、互換性（移行テスト） | — | — |
| ライブ | 実 NASA ADS API（構造とエッジ方向のみ判定） | `test_live_ads.py`（`-m live`、既定で除外） | ADS_API_TOKEN、外部ネットワーク |

### 1.1 対象範囲と対象外
- 対象: P0 の全要件（TRACEABILITY_MATRIX の PN-ADS/GRAPH/DB/ZOT/BBT/APJ/UI/SEC/OPS/NFR）。
- 対象外: P1 機能（PN-P1-001）、外部サービス自体の正確性（ADS の引用データ、Zotero・BBT・AASTeX の内部動作）、ブラウザごとの描画差、macOS・Windows（環境がないため。要確認事項）。
- 環境上の理由で未実施: ADS ライブ接続、Zotero 実機、AASTeX v7.0.2（[仕様書](SYSTEM_SPECIFICATION.md) §16）。

## 2. テスト環境
Linux (x86_64, kernel 6.18、2 コア、メモリ 7 GB), Python 3.13.18, uv 0.11.32, pytest 9.2.0, TeX Live 2023 (pdfTeX 1.40.25, BibTeX 0.99d) + `texlive-plain-generic`、
AASTeX v7.0.1（GitHub commit a22d749）、Google Chrome（ヘッドレス、グラフ HTML の描画確認）。NASA ADS / journals.aas.org には接続不可、Zotero なし。

## 3. テストデータ
- ADS・Zotero 応答: **合成データ**（`tests/conftest.py`、`tests/fixtures/`）。Bibcode は `YYYYTEST…` 形式、DOI は Crossref のテスト用接頭辞 `10.5555`。実在文献として扱わない。
- ApJ サンプル: AASTeX7 公式サンプル `sample701.bib`（ADS からのエクスポート）の書誌を無改変で転記した 5 件（キーのみ BBT 形式）。
- 異常系 `.bib`: `tests/fixtures/bib/bad.bib`（重複キー、重複 DOI、不正 DOI、必須欠落、不正キー、括弧不整合、エントリ外 `@`、未エスケープ `&`、非 ASCII、同一著者同年）。

## 4. 観点と期待結果（合否基準）

| 観点 | 種別 | 期待結果（すべて満たせば合格） |
|---|---|---|
| エッジ方向 | 正常 | References: 起点→参照先、Citations: 引用元→起点 |
| 共有参照・循環 | 境界 | 1 ノードに統合、入次数 2、循環を保持 |
| ページング | 正常・境界 | 24 件を 10 件ずつ 3 ページで全件、上限 15 件では `complete=False` |
| 0 件 vs エラー | 異常 | 0 件は `error=None`、401/403→AUTH_ERROR、429→再試行後 RATE_LIMITED、5xx→再試行、タイムアウト→TIMEOUT、不正 JSON→INVALID_RESPONSE |
| 部分成功 | 異常 | 2 ページ目失敗で 10 件保持・`partial`、Citations 失敗でも References を保持 |
| 上限 | 境界 | 最大論文数・リクエスト数到達で `truncated=1` と理由を記録 |
| 入力 | 境界・極端 | 空・空白のみ・501 文字・制御文字・階層 0/9・年の逆転を処理開始前に拒否 |
| キャッシュ | 正常 | 2 回目の API 呼び出し 0、トークン無しでも再構築可 |
| DB | 異常・復旧 | 制約違反でロールバックし変更なし、再起動後もデータ保持、v1→v2 移行でデータ保持、中断ジョブを INTERRUPTED に |
| Zotero | 異常 | 停止→unavailable、403→local_api_disabled、7.x→read_only、10+→要認可/読み書き、書き込み失敗時に成功を返さない |
| BibTeX | 異常 | 全欠陥を検出、ファイル不変、キー変更をスナップショットで検出 |
| ApJ | 正常・異常 | 公式スタイルで PDF 生成・警告なし、未定義キー・スタイル不在を検出 |
| UI | 受入れ | トークン無しで CONFIG_ERROR 表示しクラッシュしない、検索→起点→グラフ→詳細→BibTeX 検証が通る、部分成功を警告表示 |
| セキュリティ | 非機能 | トークンがログ・出力・ジョブ記録に出ない、HTML にスクリプトが注入されない、`.env`/`data/` が Git 管理外 |
| 性能・容量 | 非機能・極端 | 仕様書 §9 の目標値（300 論文: 処理 ≤10 秒、読込＋生成 ≤2 秒。5000 論文で完了） |

### 4.1 非機能要件の検証方法
性能・容量は `uv run python scripts/benchmark.py`（合成データ、ADS 通信を除く）。セキュリティはテストと pip-audit。互換性は移行テスト。アクセシビリティは役割の形・記号の一意性テスト（WCAG 評価は対象外）。再現性は再生成テストとシード固定テスト。

### 4.2 外部サービスで結果が変動する場合の判定
ライブ ADS テストは件数を固定値で判定せず、「結果が 1 件以上」「References の出版年 ≤ 起点年 + 1」「Citations の出版年 ≥ 起点年 − 1」「レート制限ヘッダが返る」という構造条件で判定する。起点は環境変数 `PN_LIVE_SEED_BIBCODE` で変更可能。

## 5. 実行結果

実行日時: 2026-11-12T06:15:00Z（UTC）。コマンド: `uv run pytest -v -rs --junitxml=docs/verification/junit.xml`
（出力全文: [verification/pytest_full.txt](verification/pytest_full.txt)、JUnit: [verification/junit.xml](verification/junit.xml)）

| テスト分類 | ファイル | 実行 | 成功 | 失敗 | 未実施 | 備考 |
|---|---|---:|---:|---:|---:|---|
| 単体 | test_normalize | 30 | 30 | 0 | 0 | |
| 単体 | test_ads_client | 24 | 24 | 0 | 0 | モック ADS |
| 単体 | test_db_repository | 15 | 15 | 0 | 0 | 移行・バックアップ・中断ジョブを含む |
| 単体 | test_config_security | 17 | 17 | 0 | 0 | |
| 単体＋結合 | test_bibliography | 11 | 11 | 0 | 0 | うち LaTeX 実コンパイル 4 |
| 結合 | test_network | 21 | 21 | 0 | 0 | モック ADS |
| 結合 | test_zotero | 18 | 18 | 0 | 0 | モック Zotero |
| システム／受入れ | test_ui_cli_acceptance | 8 | 8 | 0 | 0 | AppTest・CLI、LaTeX 1 |
| **モック・オフライン計** | | **144** | **144** | **0** | **0** | 13.2 秒 |
| ライブ（ADS） | test_live_ads | 0 | 0 | 0 | **2** | ADS_API_TOKEN 未設定・ADS 到達不可のため未実施 |

その他の検証:
- 静的解析: `ruff check src tests scripts` → All checks passed、`ruff format --check` → 整形済み、`mypy src` → no issues（28 ファイル）
- 性能・容量（[verification/benchmark.md](verification/benchmark.md)）: 300 論文 保存 1.84 秒・読込 0.02 秒・HTML 生成 0.06 秒、2000 論文 12.97 秒・0.51 秒・0.02 秒、5000 論文 33.84 秒・2.48 秒・0.03 秒、DB 4.26 MB。目標を満たす。初回測定（v0.1.0）では 5000 論文に 156 秒かかり二次的に増加していたため修正（ADR-012）。ブラウザ描画時間・メモリは未測定。
- 脆弱性: `pip-audit`（uv.lock の実行時依存）→ No known vulnerabilities（[verification/pip_audit.txt](verification/pip_audit.txt)）
- ライセンス: [verification/licenses.md](verification/licenses.md)
- クリーン環境（v0.1.0 で実施）: Git 管理対象ファイルのみを別ディレクトリに展開し、README の手順（`uv sync` → `cp .env.example .env` → `pn init-db` → `pytest` → `fetch_aastex.sh` → `pytest -m latex` → `pn apj-build`）を実行し全て成功。v0.1.1 の ZIP でも展開 → `uv sync` → `pytest` を再確認（§9）。
- UI 起動: `pn ui --port 8765` で `/_stcore/health` = ok、待ち受けは 127.0.0.1 のみ（外部インターフェースからは接続拒否）、停止後に再起動しても DB が残ることを確認
- グラフ表示: ヘッドレス Chrome で合成データのグラフ HTML を描画・ノードクリック後の詳細パネルを確認（[画像](verification/graph_demo_synthetic.png)、[クリック後](verification/graph_demo_synthetic_click.png)。v0.1.0 の描画）

## 6. 合格基準（指示書 §9.2）の判定

| # | 基準 | 判定 | 根拠 |
|---|---|---|---|
| 1 | P0 主要ユースケースが UI/CLI から実行可能 | 合格（モック）| UC-01〜05 を CLI・UI で実装、AppTest/CLI テスト。ADS・Zotero 実機は未検証 |
| 2 | 主要な正常系・異常系テストが成功 | 合格 | 144/144 |
| 3 | エッジ方向と References/Citations の意味をテストで保証 | 合格 | `test_edge_direction_references_and_citations` 他 |
| 4 | 重複排除とページングのテスト | 合格 | `test_dedup_*`, `test_paging_*` |
| 5 | SQLite 永続化・再起動後の読込 | 合格 | `test_persistence_across_restart`、UI 再起動確認 |
| 6 | Zotero/BBT の導入・接続・エクスポート方法の文書化 | 合格（文書）| `docs/ZOTERO_BBT_SETUP.md`。実機での手順実行は未実施 |
| 7 | BibTeX 検証と ApJ サンプル文書 | 合格 | `bib-check`、`examples/apj/`、実コンパイル成功 |
| 8 | 秘密情報がソース・ログ・Git に漏れない | 合格 | セキュリティテスト 17 件、`git check-ignore` |
| 9 | README のクリーン環境手順の実行確認 | 合格 | §5 |
| 10 | 仕様チェックリスト全項目の監査 | 合格（監査完了。未達項目あり） | [監査文書](SOFTWARE_SPECIFICATION_CHECKLIST_AUDIT.md)（182 項目すべて判定、未達は同文書に列挙） |

## 7. リリース・受入れの判定条件
リリース可（開発者側）: (1) 全オフラインテスト成功、(2) ruff・mypy エラー 0、(3) pip-audit で既知脆弱性なし、(4) トレーサビリティ表とチェックリスト監査の再生成が成功（参照切れなし、集計の検算一致）、(5) CHANGELOG・版番号の更新。
受入れ（利用者側）: 上記に加え、利用者環境で `pytest -m live` 成功、`pn zotero-status` が想定状態を返す、自分の `.bib` で `bib-check`・`apj-build` が clean、仕様書の承認。

## 8. 不具合の重大度・再テスト・回帰テスト
| 重大度 | 定義 | 対応 |
|---|---|---|
| 致命 | データ破損・秘密情報漏えい・誤った引用関係の保存（エッジ方向の逆転など）・偽の成功表示 | 直ちに修正、リリース不可 |
| 重大 | 主要ユースケースが実行できない | 修正するまでリリース不可 |
| 中 | 回避策のある機能不全、誤解を招く表示 | 次の版で修正、既知の制限に記載 |
| 軽微 | 表記・体裁 | 随時修正 |
修正時は再現テストを先に追加し（回帰テスト）、全テストを再実行する。例: 「欠落フィールドが空でも『未取得』と表示」は軽微として修正、「重複候補検索の二次的な処理時間増加」は中として修正し性能測定を再実行した。

## 9. 配布物の確認
配布 ZIP を空ディレクトリに展開し `uv sync` → `uv run pytest` を実行して確認する（AASTeX 未取得のため LaTeX テストは skip、Git 管理外のため `test_git_check_ignore` は skip となるのが正常）。
