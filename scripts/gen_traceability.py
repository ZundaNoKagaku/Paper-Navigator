"""Generate docs/TRACEABILITY_MATRIX.md.

Implementation references are resolved to current line numbers via ``ast``; test
references are resolved against docs/verification/junit.xml so the matrix shows the
real recorded outcome. Unknown symbols or tests abort the script (no invented evidence).

Usage: uv run python scripts/gen_traceability.py
"""

from __future__ import annotations

import ast
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - parsing our own junit file
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "paper_navigator"

# Expected behaviour (testable statement) per requirement — checklist §16 column.
EXPECTED = {
    "PN-ADS-001": "DOI/Bibcode/arXiv/タイトルを入力すると種別を判定してADSクエリを生成し、結果を出典付きでDBに保存して一覧表示する",
    "PN-ADS-002": "references(bibcode:X)はXが引用する論文、citations(bibcode:X)はXを引用する論文として取得し、取り違えない",
    "PN-ADS-003": "取得できた項目のみ保存し、無い項目はNULL・欠落フィールドとして記録する。取得元と取得日時(UTC)を必ず記録する",
    "PN-ADS-004": "numFoundに達するまでstartをrowsずつ進めて取得し、件数上限で止めた場合はcomplete=Falseとする",
    "PN-ADS-005": "0件はerror無しの空結果、401/403はAUTH_ERROR、429はRATE_LIMITED、不正応答はINVALID_RESPONSEとして区別する",
    "PN-ADS-006": "トークン未設定・ネットワーク無しでもアプリが落ちずCONFIG_ERRORを表示し、オフラインテストが全て実行できる",
    "PN-ADS-007": "タイムアウト・接続失敗・500/502/503/504を最大3回再試行し、回復しなければTIMEOUT/NETWORK_ERRORを返す",
    "PN-ADS-008": "429ではRetry-After（上限60秒）待って再試行し、X-RateLimit-Remaining=0なら再試行せず停止する",
    "PN-ADS-009": "1ページ目成功・以降失敗の場合、取得済み件数を保持しerrorを付けた部分結果を返す",
    "PN-GRAPH-001": "References取得では起点→参照先、Citations取得では引用元→起点のエッジを作る（A→B=AがBを引用）",
    "PN-GRAPH-002": "同じ論文に複数経路で到達しても1ノードに統合される",
    "PN-GRAPH-003": "共有参照（入次数2以上）と循環を保持し、一部リストの取得失敗時も取得済み部分グラフを表示できる",
    "PN-GRAPH-004": "階層数1〜5・最大論文数・最大リクエスト数・期間を指定でき、上限到達時はtruncated=1と理由を記録しpartialとする",
    "PN-GRAPH-005": "起点★・先行●・後続▲・両方◆で表示し、ノードをクリックするとタイトル・著者・年・雑誌・DOI・Bibcode・Abstract・リンクを表示する",
    "PN-GRAPH-006": "出版年範囲・役割・最大階層でノードを絞り込む（起点は常に表示）",
    "PN-GRAPH-007": "HTML・JSON(node-link)・GraphML・エッジCSVを出力し、JSON/GraphMLは読み戻すと同じノード数・エッジ数になる",
    "PN-GRAPH-008": "同じDB状態から同じジョブのグラフを再生成すると同一のnode-linkデータになる",
    "PN-DB-001": "論文・エッジ・取得履歴・エクスポート記録をSQLiteに保存し、再起動後も読み出せる",
    "PN-DB-002": "DOI→Bibcode→arXivの一致のみ自動統合し、類似タイトルや識別子の衝突は重複候補として記録して統合しない",
    "PN-DB-003": "起動時に未適用のマイグレーションを1件1トランザクションで適用し、ソフトウェアより新しいスキーマは拒否する",
    "PN-DB-004": "DB操作でSQLAlchemyエラー（制約違反・外部キー違反・I/O）が起きたらロールバックし、DATABASE_ERRORを返して変更を残さない",
    "PN-DB-005": "完全取得済みかつTTL内のリストはAPIを呼ばずDBから再利用し、期間指定の取得は完全扱いしない",
    "PN-DB-006": "著者を位置番号付きで保存し、取得時の順序で読み出せる",
    "PN-DB-007": "pn backupで起動中でも整合したDBコピーを作成し、そのコピーから読み出せる",
    "PN-DB-008": "v1スキーマのDBを開くとv2へ自動移行し、既存データを保持する",
    "PN-ZOT-001": "Zotero停止→unavailable、403→local_api_disabled、<10→read_only、10+でキー無し→write_needs_authorization、キー有り→read_writeを返す",
    "PN-ZOT-002": "コレクションのアイテム（ノート・添付を除く）を読み、DOI・引用キー・Extra中のBibcodeを取り出す",
    "PN-ZOT-003": "Zotero 10+かつ許可済みキーがあり同DOIが無い場合のみ追加し、Zoteroが作成キーを返した場合のみcreatedとする",
    "PN-ZOT-004": "リンクした論文の項目ごとにmatch/prefer_zotero/manual_reviewを判定してDBに記録する（Zoteroは変更しない）",
    "PN-BBT-001": "重複キー・重複DOI・必須項目欠落・DOI形式不正・括弧不整合・エントリ外@等を行番号付きで報告する",
    "PN-BBT-002": ".bibを変更せず、前回承認スナップショットと比べて同一DOIのキー変更・キー消失を警告する",
    "PN-BBT-003": "BBT自動エクスポートの設定手順と引用キー運用が文書化されている",
    "PN-APJ-001": "AAS公式.cls/.bstを無改変で使いpdflatex→bibtex→pdflatex×2でPDFと.bblを生成する",
    "PN-APJ-002": ".texの\\cite系コマンドのキーを抽出し、.bibに無いキーと未使用キーを報告する",
    "PN-APJ-003": "未解決引用・BibTeX警告/エラー・スタイル不在を検出し、成功(success)と警告なし(clean)を区別して報告する",
    "PN-UI-001": "UIから検索→起点設定→グラフ作成→詳細表示→BibTeX検証まで一連の操作ができる",
    "PN-UI-002": "成功・部分成功・失敗・0件・キャッシュ・エラー分類コード・打ち切り・進捗を画面で判別できる",
    "PN-UI-003": "既定で127.0.0.1のみで待ち受け、外部インターフェースからは接続できない",
    "PN-SEC-001": "トークン・キーがrepr・ログ・DB・出力・Gitに現れない",
    "PN-SEC-002": "タイトル等に<script>を含んでもHTML内で実行されない（JSONエスケープ・textContent・CSP）",
    "PN-SEC-003": "長さ・範囲・形式・制御文字・URLホストを検証し、不正値は処理開始前に拒否する",
    "PN-OPS-001": "ジョブにUTC日時・条件・件数・リクエスト数・エラー分類・ソフトウェア版を記録する",
    "PN-OPS-002": "空DBからREADME手順でセットアップでき、再起動後もデータが残る",
    "PN-OPS-003": "6時間以上runningのジョブを起動時にfailed/INTERRUPTEDとし、取得済みデータは残す",
    "PN-P1-001": "P0では実装せず、UI・READMEに未実装と明示する",
}

# (id, requirement, priority, rationale, impl [(file, symbol)], tests [test ids], method,
#  impl_state, verify_state)
REQS = [
    (
        "PN-ADS-001",
        "タイトル・DOI・Bibcode（・arXiv）でADS検索",
        "MUST",
        "P0-A",
        [
            ("ads/query.py", "detect_input"),
            ("ads/query.py", "build_search_query"),
            ("services.py", "search_papers"),
        ],
        [
            "test_normalize::test_detect_input_kinds",
            "test_normalize::test_query_building_escapes_quotes",
            "test_network::test_search_service_statuses",
        ],
        "モックAPIテスト",
        "実装済み",
        "検証済み（モック）／ライブ未検証",
    ),
    (
        "PN-ADS-002",
        "References/Citations取得（意味の区別）",
        "MUST",
        "P0-A, §3.3",
        [
            ("ads/query.py", "references_query"),
            ("ads/query.py", "citations_query"),
            ("graph/builder.py", "build_network"),
        ],
        [
            "test_normalize::test_reference_and_citation_query_semantics",
            "test_network::test_edge_direction_references_and_citations",
        ],
        "エッジ方向テスト",
        "実装済み",
        "検証済み（モック）／ライブ未検証",
    ),
    (
        "PN-ADS-003",
        "メタデータ項目と出典（取得元・日時・欠落・状態）の記録、推測値を入れない",
        "MUST",
        "P0-A, §4.1",
        [("ads/mapping.py", "ads_doc_to_record"), ("records.py", "PaperRecord")],
        [
            "test_ads_client::test_mapping_full_record",
            "test_ads_client::test_mapping_missing_fields_are_null_not_guessed",
            "test_ads_client::test_mapping_bad_values_flagged",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-ADS-004",
        "ページング（start/rows）で全件取得し、上限で止めた場合は完全と表示しない",
        "MUST",
        "P0-A, §3.3",
        [("ads/client.py", "ADSClient.search")],
        [
            "test_ads_client::test_paging_fetches_all_and_marks_complete",
            "test_ads_client::test_max_results_limit_is_not_reported_complete",
        ],
        "モックAPIテスト",
        "実装済み",
        "検証済み（モック）／ライブ未検証",
    ),
    (
        "PN-ADS-007",
        "タイムアウト・通信失敗・5xxを再試行し、回復しなければ分類して報告",
        "MUST",
        "P0-A",
        [("ads/client.py", "ADSClient._get")],
        [
            "test_ads_client::test_transient_5xx_recovers",
            "test_ads_client::test_timeout_and_network_errors",
        ],
        "モックAPIテスト",
        "実装済み",
        "検証済み（モック）／ライブ未検証",
    ),
    (
        "PN-ADS-008",
        "レート制限（429）でRetry-Afterに従い再試行、日次上限枯渇時は即停止",
        "MUST",
        "P0-A",
        [("ads/client.py", "ADSClient._get")],
        [
            "test_ads_client::test_rate_limit_retries_then_fails",
            "test_ads_client::test_quota_exhausted_does_not_retry",
            "test_ads_client::test_rate_limit_headers_captured",
        ],
        "モックAPIテスト",
        "実装済み",
        "検証済み（モック）／ライブ未検証",
    ),
    (
        "PN-ADS-009",
        "2ページ目以降の失敗は取得済みを保持して部分成功とする",
        "MUST",
        "P0-A, §3.3",
        [("ads/client.py", "ADSClient.search")],
        ["test_ads_client::test_failure_after_first_page_is_partial"],
        "モックAPIテスト",
        "実装済み",
        "検証済み（モック）",
    ),
    (
        "PN-ADS-005",
        "0件と通信/認証/レート制限エラーの区別、エラー分類",
        "MUST",
        "§3.3, §8.1",
        [("errors.py", "ErrorCode"), ("ads/client.py", "ADSClient._get")],
        [
            "test_ads_client::test_zero_results_is_not_an_error",
            "test_ads_client::test_http_error_classification",
            "test_ads_client::test_timeout_and_network_errors",
            "test_ads_client::test_invalid_response_shapes",
        ],
        "モックAPIテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-ADS-006",
        "APIキー未設定・ネットワーク無しでもテスト可能",
        "MUST",
        "P0-A",
        [("app.py", "AppContext.ads")],
        [
            "test_ui_cli_acceptance::test_cli_setup_from_empty_db_and_restart",
            "test_ads_client::test_empty_token_is_config_error",
        ],
        "オフラインテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-001",
        "有向引用グラフ（A→B＝AがBを引用）",
        "MUST",
        "P0-B",
        [("graph/builder.py", "build_network"), ("graph/view.py", "load_job_graph")],
        [
            "test_network::test_edge_direction_references_and_citations",
            "test_db_repository::test_edges_unique_and_directed",
        ],
        "グラフ単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-002",
        "重複ノード統合",
        "MUST",
        "P0-B",
        [("repository.py", "upsert_paper")],
        [
            "test_network::test_shared_reference_and_cycle_kept_as_digraph",
            "test_db_repository::test_dedup_by_doi_bibcode_and_arxiv",
        ],
        "重複排除テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-003",
        "共有参照・循環・不完全データを破壊せず保持",
        "MUST",
        "P0-B",
        [("graph/builder.py", "build_network"), ("graph/view.py", "graph_summary")],
        [
            "test_network::test_shared_reference_and_cycle_kept_as_digraph",
            "test_network::test_partial_failure_keeps_fetched_part",
        ],
        "グラフ単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-004",
        "階層数・最大論文数・最大リクエスト数・期間を設定可能、打ち切りを記録",
        "MUST",
        "P0-B, §5.1",
        [("graph/builder.py", "NetworkParams"), ("config.py", "load_settings")],
        [
            "test_network::test_max_papers_truncation_recorded",
            "test_network::test_max_requests_truncation",
            "test_network::test_param_validation",
            "test_config_security::test_defaults_are_small_and_configurable",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-005",
        "ブラウザ表示、起点/先行/後続の区別、ノード選択で詳細",
        "MUST",
        "P0-B, §5.2",
        [("graph/view.py", "render_html"), ("graph/view.py", "ROLE_STYLE")],
        ["test_network::test_filter_and_exports"],
        "HTML出力テスト＋ヘッドレスChromeでのスクリーンショット確認",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-006",
        "出版年・階層・役割によるフィルタ",
        "MUST",
        "P0-B",
        [("graph/view.py", "filter_graph")],
        ["test_network::test_filter_and_exports"],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-007",
        "HTML・再現可能データ（JSON/GraphML/CSV）でエクスポート",
        "MUST",
        "P0-B",
        [("graph/view.py", "export_all")],
        ["test_network::test_filter_and_exports"],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-GRAPH-008",
        "同じDB状態からグラフを再生成",
        "SHOULD",
        "§8.3",
        [("graph/view.py", "load_job_graph")],
        [
            "test_network::test_reproducible_regeneration",
            "test_network::test_cache_reuse_avoids_api_calls",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-001",
        "論文・引用関係・取得履歴・エクスポート情報の永続化",
        "MUST",
        "P0-C",
        [("db.py", "SCHEMA_V1"), ("repository.py", "add_edge"), ("graph/view.py", "export_all")],
        [
            "test_db_repository::test_persistence_across_restart",
            "test_db_repository::test_migrations_create_schema_matching_orm",
        ],
        "DB結合テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-002",
        "識別子優先の重複排除、曖昧一致は候補のみ",
        "MUST",
        "P0-C, §4.4",
        [("repository.py", "upsert_paper"), ("repository.py", "_detect_candidates")],
        [
            "test_db_repository::test_similar_titles_become_candidates_not_merged",
            "test_db_repository::test_identifier_conflict_recorded_not_merged",
        ],
        "重複排除テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-003",
        "スキーマ変更の管理（マイグレーション）",
        "MUST",
        "P0-C",
        [("db.py", "migrate")],
        [
            "test_db_repository::test_migrate_is_idempotent",
            "test_db_repository::test_newer_schema_refused",
        ],
        "DBテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-004",
        "整合性制約・トランザクション・ロールバック",
        "MUST",
        "P0-C",
        [("db.py", "Database.session")],
        [
            "test_db_repository::test_rollback_on_error_leaves_db_unchanged",
            "test_db_repository::test_foreign_keys_enforced",
        ],
        "DBテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-005",
        "キャッシュ再利用で不要なAPIアクセスを避ける",
        "MUST",
        "P0-C",
        [("graph/builder.py", "build_network"), ("services.py", "search_papers")],
        [
            "test_network::test_cache_reuse_avoids_api_calls",
            "test_network::test_year_filtered_fetch_is_not_cached_as_complete",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-006",
        "著者を順序付きで保持（1文字列に潰さない）",
        "MUST",
        "§4.1",
        [("models.py", "PaperAuthor")],
        ["test_db_repository::test_upsert_creates_and_preserves_author_order"],
        "DBテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-ZOT-001",
        "Zotero接続状態の判定（停止・API無効・版・認可）",
        "MUST",
        "P0-D, §6.1",
        [("zotero/client.py", "ZoteroLocalClient.status")],
        [
            "test_zotero::test_status_unavailable_when_zotero_not_running",
            "test_zotero::test_status_local_api_disabled",
            "test_zotero::test_status_versions",
        ],
        "APIモックテスト",
        "実装済み",
        "検証済み（モック）／実Zotero未検証",
    ),
    (
        "PN-ZOT-002",
        "ライブラリ／コレクションの書誌読み取り",
        "MUST",
        "P0-D",
        [
            ("zotero/client.py", "ZoteroLocalClient.collection_items"),
            ("zotero/client.py", "parse_item"),
        ],
        [
            "test_zotero::test_read_collections_and_items_skip_notes",
            "test_zotero::test_parse_item_handles_missing_fields",
        ],
        "APIモックテスト",
        "実装済み",
        "検証済み（モック）／実Zotero未検証",
    ),
    (
        "PN-ZOT-003",
        "追加（10+・要認可・重複防止・偽の成功なし）",
        "SHOULD",
        "P0-D, §6.1",
        [
            ("zotero/client.py", "ZoteroLocalClient.create_item"),
            ("zotero/client.py", "ZoteroLocalClient.request_authorization"),
        ],
        [
            "test_zotero::test_write_refused_on_old_zotero_without_posting",
            "test_zotero::test_write_needs_authorization_without_key",
            "test_zotero::test_write_duplicate_doi_not_added",
            "test_zotero::test_write_success_and_headers",
            "test_zotero::test_write_failures_never_report_success",
            "test_zotero::test_authorize_flow",
        ],
        "APIモックテスト",
        "実装済み",
        "検証済み（モック）／実Zotero未検証",
    ),
    (
        "PN-ZOT-004",
        "ADSとZoteroの不一致を検出し採用/要確認を記録",
        "MUST",
        "P0-D",
        [("zotero/sync.py", "compare_fields"), ("zotero/sync.py", "sync_collection")],
        ["test_zotero::test_sync_links_and_reconciles"],
        "結合テスト（モック）",
        "実装済み",
        "検証済み（モック）",
    ),
    (
        "PN-BBT-001",
        "Better BibTeX .bib検証（構文・重複キー/DOI・必須項目・DOI形式）",
        "MUST",
        "P0-E, §6.2",
        [("bibliography/bibcheck.py", "check_bib")],
        [
            "test_bibliography::test_good_bib_has_no_errors",
            "test_bibliography::test_bad_bib_detects_every_defect",
            "test_bibliography::test_non_utf8_reported",
        ],
        "BibTeXテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-BBT-002",
        "既存引用キーを変更しない・変更を検出",
        "MUST",
        "P0-D",
        [("bibliography/bibcheck.py", "compare_with_snapshot")],
        [
            "test_bibliography::test_snapshot_detects_key_change",
            "test_bibliography::test_unicode_preserved_file_not_modified",
        ],
        "BibTeXテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-BBT-003",
        "自動エクスポートの設定・運用手順の文書化",
        "MUST",
        "P0-D",
        [],
        [],
        "文書レビュー（docs/ZOTERO_BBT_SETUP.md）",
        "文書化済み",
        "実機未検証",
    ),
    (
        "PN-APJ-001",
        "AAS公式スタイルでのサンプルコンパイル検証",
        "MUST",
        "P0-E, §6.3",
        [("bibliography/latex.py", "build")],
        [
            "test_bibliography::test_apj_sample_compiles_with_official_style",
            "test_ui_cli_acceptance::test_cli_apj_build",
        ],
        "コンパイルテスト",
        "実装済み",
        "検証済み（v7.0.1）／v7.0.2未検証",
    ),
    (
        "PN-APJ-002",
        "\\citep/\\citet と .bib キーの整合検査",
        "MUST",
        "P0-E",
        [("bibliography/cites.py", "check_citations")],
        [
            "test_bibliography::test_extract_citations_variants",
            "test_bibliography::test_check_citations_missing_and_unused",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-APJ-003",
        "ログ中の未解決引用・警告・スタイル不在の検出",
        "MUST",
        "§6.3",
        [("bibliography/latex.py", "build")],
        [
            "test_bibliography::test_apj_build_reports_undefined_citation",
            "test_bibliography::test_apj_build_missing_style_reported",
            "test_bibliography::test_apj_build_with_missing_doi_still_builds",
        ],
        "コンパイルテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-UI-001",
        "ローカルUIから検索・グラフ・詳細・BibTeX検証",
        "MUST",
        "P0-F",
        [("ui/streamlit_app.py", "show_error")],
        ["test_ui_cli_acceptance::test_ui_end_to_end_search_graph_detail_bib"],
        "受入れテスト（AppTest）",
        "実装済み",
        "検証済み（モックADS）",
    ),
    (
        "PN-UI-002",
        "処理中・成功・失敗・部分成功・キャッシュ・認証不足の表示",
        "MUST",
        "P0-F",
        [("ui/streamlit_app.py", "show_error")],
        [
            "test_ui_cli_acceptance::test_ui_without_token_shows_config_error_and_does_not_crash",
            "test_ui_cli_acceptance::test_ui_shows_partial_status",
        ],
        "受入れテスト（AppTest）",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-UI-003",
        "既定で127.0.0.1のみで待ち受け",
        "MUST",
        "P0-F, §8.2",
        [("cli.py", "cmd_ui")],
        ["test_config_security::test_streamlit_config_binds_loopback"],
        "設定テスト＋起動確認（外部IFで接続拒否）",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-SEC-001",
        "APIキーを秘密管理しログ・Gitに出さない",
        "MUST",
        "§8.2",
        [("config.py", "Secret"), ("logging_utils.py", "RedactingFilter")],
        [
            "test_config_security::test_secret_masked_in_repr",
            "test_config_security::test_redaction_patterns",
            "test_config_security::test_no_secret_in_logs_during_retries",
            "test_config_security::test_gitignore_covers_secrets_and_data",
            "test_config_security::test_no_token_like_strings_in_tracked_sources",
            "test_config_security::test_git_check_ignore",
            "test_config_security::test_key_file_written_owner_only",
        ],
        "セキュリティテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-SEC-002",
        "外部データをHTML表示時に実行しない",
        "MUST",
        "§8.2",
        [("graph/view.py", "_safe_json")],
        ["test_network::test_html_escapes_untrusted_metadata"],
        "セキュリティテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-SEC-003",
        "入力値・URL・パスの検証",
        "MUST",
        "§8.2",
        [("ads/query.py", "detect_input"), ("config.py", "is_loopback_url")],
        [
            "test_normalize::test_detect_input_rejects",
            "test_config_security::test_invalid_config_is_config_error",
            "test_config_security::test_loopback_variants_accepted",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-OPS-001",
        "UTC日時・取得条件・件数・版・結果の記録",
        "MUST",
        "§8.3",
        [
            ("logging_utils.py", "UTCFormatter"),
            ("repository.py", "start_job"),
            ("services.py", "_finish"),
        ],
        [
            "test_network::test_max_papers_truncation_recorded",
            "test_network::test_search_service_statuses",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-OPS-002",
        "空DBからのクリーンセットアップ・再起動後のデータ保持",
        "MUST",
        "§9.1",
        [("cli.py", "cmd_init_db")],
        [
            "test_ui_cli_acceptance::test_cli_setup_from_empty_db_and_restart",
            "test_db_repository::test_persistence_across_restart",
        ],
        "受入れテスト＋クリーンコピーでREADME手順実行",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-007",
        "DBのバックアップ（起動中でも整合したコピー）",
        "SHOULD",
        "チェックリスト5章",
        [("db.py", "Database.backup"), ("cli.py", "cmd_backup")],
        [
            "test_db_repository::test_backup_is_consistent_copy",
            "test_ui_cli_acceptance::test_cli_backup",
        ],
        "DBテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-DB-008",
        "旧スキーマのDBを自動移行しデータを保持",
        "MUST",
        "チェックリスト5章",
        [("db.py", "MIGRATIONS")],
        ["test_db_repository::test_upgrade_from_v1_database"],
        "移行テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-OPS-003",
        "中断したジョブを検出しINTERRUPTEDとして記録（取得済みデータは保持）",
        "SHOULD",
        "チェックリスト7章",
        [("repository.py", "mark_stale_jobs"), ("app.py", "make_context")],
        ["test_db_repository::test_stale_running_jobs_marked_interrupted"],
        "DBテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-001",
        "性能: 300論文のローカル処理≤10秒、読込＋HTML生成≤2秒",
        "SHOULD",
        "仕様§9",
        [("graph/view.py", "render_html")],
        [],
        "scripts/benchmark.py（1.84秒／0.08秒）",
        "実装済み",
        "検証済み（ブラウザ描画は未測定）",
    ),
    (
        "PN-NFR-002",
        "容量: 5000論文で処理完了、ほぼ線形",
        "SHOULD",
        "仕様§9",
        [("repository.py", "_detect_candidates")],
        [],
        "scripts/benchmark.py（33.84秒、DB 4.26MB）",
        "実装済み",
        "検証済み（20000件は未測定）",
    ),
    (
        "PN-NFR-003",
        "信頼性: 失敗時に半端な状態を残さない、取得済みを保持",
        "MUST",
        "仕様§9",
        [("db.py", "Database.session")],
        [
            "test_db_repository::test_rollback_on_error_leaves_db_unchanged",
            "test_network::test_partial_failure_keeps_fetched_part",
        ],
        "テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-004",
        "可用性: 外部サービス停止時もキャッシュ・BibTeX機能を利用可能",
        "MUST",
        "仕様§9",
        [("graph/builder.py", "build_network")],
        [
            "test_network::test_cache_reuse_avoids_api_calls",
            "test_ui_cli_acceptance::test_ui_without_token_shows_config_error_and_does_not_crash",
        ],
        "テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-005",
        "保守性: ruff・mypyエラー0、層分離",
        "MUST",
        "仕様§9",
        [],
        [],
        "静的解析（ruff/mypy、docs/TEST_PLAN.md §5）",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-006",
        "移植性: Python≥3.12のLinux/macOS/Windows",
        "SHOULD",
        "仕様§9",
        [],
        [],
        "Linuxで全テスト",
        "実装済み",
        "Linuxのみ検証、他OS未検証",
    ),
    (
        "PN-NFR-007",
        "ユーザビリティ: 状態をアイコン＋文字、エラーは分類コードと対処説明",
        "SHOULD",
        "仕様§9",
        [("ui/streamlit_app.py", "show_error")],
        ["test_ui_cli_acceptance::test_ui_shows_partial_status"],
        "受入れテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-008",
        "アクセシビリティ: 役割を色以外（形・記号・文字）でも区別",
        "SHOULD",
        "仕様§9",
        [("graph/view.py", "ROLE_STYLE")],
        ["test_network::test_roles_distinguishable_without_colour_and_layout_seeded"],
        "単体テスト",
        "実装済み",
        "検証済み（WCAG評価は未実施）",
    ),
    (
        "PN-NFR-009",
        "安全性: .bibを変更しない、Zotero書き込みは明示操作かつ許可時のみ",
        "MUST",
        "仕様§9",
        [("zotero/client.py", "ZoteroLocalClient.create_item")],
        [
            "test_bibliography::test_unicode_preserved_file_not_modified",
            "test_zotero::test_write_needs_authorization_without_key",
        ],
        "テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-010",
        "セキュリティ: 仕様§10の対策",
        "MUST",
        "仕様§10",
        [("logging_utils.py", "RedactingFilter")],
        ["test_config_security::test_no_secret_in_logs_during_retries"],
        "セキュリティテスト・pip-audit",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-011",
        "プライバシー: 外部送信は検索語のみ、ローカル保存のみ",
        "MUST",
        "仕様§9",
        [("ads/client.py", "ADSClient.search_page")],
        [],
        "コードレビュー",
        "実装済み",
        "検証済み（レビュー）",
    ),
    (
        "PN-NFR-012",
        "相互運用性: JSON/GraphML/CSV/BibTeXで連携",
        "SHOULD",
        "仕様§9",
        [("graph/view.py", "write_graphml")],
        ["test_network::test_filter_and_exports"],
        "読み戻しテスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-NFR-013",
        "再現性: 同一DBから同一グラフ、初期配置シード固定",
        "SHOULD",
        "仕様§9",
        [("graph/view.py", "load_job_graph")],
        [
            "test_network::test_reproducible_regeneration",
            "test_network::test_roles_distinguishable_without_colour_and_layout_seeded",
        ],
        "単体テスト",
        "実装済み",
        "検証済み",
    ),
    (
        "PN-P1-001",
        "日本語翻訳・PDF解析・共引用分析等",
        "WON'T(P0)",
        "§2.3",
        [],
        [],
        "—",
        "対象外",
        "対象外",
    ),
]


def symbol_line(rel: str, symbol: str) -> int:
    path = SRC / rel
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts = symbol.split(".")

    def find(nodes, name):
        for n in nodes:
            if (
                isinstance(n, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef)
                and n.name == name
            ):
                return n
            if (
                isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name)
                and n.target.id == name
            ):
                return n
            if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in n.targets
            ):
                return n
        return None

    node = find(tree.body, parts[0])
    for p in parts[1:]:
        node = find(node.body, p) if node is not None else None
    if node is None:
        sys.exit(f"unknown symbol {rel}:{symbol}")
    return node.lineno


def junit_results() -> dict[str, str]:
    path = ROOT / "docs" / "verification" / "junit.xml"
    res: dict[str, str] = {}
    for tc in ET.parse(path).getroot().iter("testcase"):  # noqa: S314
        mod = tc.get("classname", "").split(".")[-1]
        name = tc.get("name", "").split("[")[0]
        status = "PASS"
        if tc.find("failure") is not None or tc.find("error") is not None:
            status = "FAIL"
        elif tc.find("skipped") is not None:
            status = "SKIP"
        key = f"{mod}::{name}"
        if res.get(key) not in ("FAIL",):
            res[key] = status if res.get(key) in (None, status) else "MIXED"
    return res


def main() -> None:
    results = junit_results()
    lines = [
        "# トレーサビリティ・マトリクス（P0 要件一覧）",
        "",
        "`scripts/gen_traceability.py` で生成（実装の行番号は `ast` で解決、テスト結果は "
        "`docs/verification/junit.xml` から取得）。手で編集しないこと。",
        "",
        "状態の区分: 未着手 / 検討中 / 確定 / 実装済み / 検証済み / 対象外。"
        "「検証済み（モック）」はモックでのみ検証し、ライブ接続では未検証であることを示す。",
        "",
        "優先度: MUST（P0必須）／SHOULD（P0で実装、環境により代替手段を許容）／WON'T(P0)（P1以降）。",
        "",
        "| 要件ID | 要件名 | 要件・期待動作 | 優先度 | 根拠・出典 | 実装（ファイル:行 シンボル） | テスト（結果） | 検証方法 | 実装状態 | 検証状態 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    total_tests = 0
    ids: list[str] = []
    for rid, req, prio, why, impl, tests, method, ist, vst in REQS:
        impl_s = "<br>".join(f"`{f}:{symbol_line(f, s)}` {s}" for f, s in impl) or "—"
        tl = []
        for t in tests:
            if t not in results:
                sys.exit(f"test not found in junit.xml: {t}")
            tl.append(f"`{t}` {results[t]}")
            total_tests += 1
        test_s = "<br>".join(tl) or "—"
        if rid not in EXPECTED and not rid.startswith("PN-NFR-"):
            sys.exit(f"missing expected behaviour for {rid}")
        expected = EXPECTED.get(rid, req)  # NFR names already state target and condition
        lines.append(
            f"| {rid} | {req} | {expected} | {prio} | {why} | {impl_s} | {test_s} "
            f"| {method} | {ist} | {vst} |"
        )
        ids.append(rid)
    if len(set(ids)) != len(ids):
        sys.exit("duplicate requirement IDs")
    lines += ["", f"要件 {len(REQS)} 件、参照テスト {total_tests} 件（重複参照を含む）。"]
    out = ROOT / "docs" / "TRACEABILITY_MATRIX.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
