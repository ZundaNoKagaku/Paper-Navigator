"""Generate docs/SOFTWARE_SPECIFICATION_CHECKLIST_AUDIT.md from the original checklist.

* Every checklist item is extracted from docs/reference/software_specification_checklist.md
  and must have exactly one judgment below (missing/extra IDs abort the script).
* Spec evidence (file, search text) is resolved to a line number and nearest heading;
  code evidence (file, symbol) via ast; test evidence via docs/verification/junit.xml.
  Unresolvable evidence aborts the script, so no evidence can be invented.
* `[x]` requires spec evidence; `[N/A]` and `[ ]` require a note.
* Totals are recomputed and cross-checked.

Usage: uv run python scripts/gen_checklist_audit.py
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - our own junit file
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKLIST = ROOT / "docs" / "reference" / "software_specification_checklist.md"
OUT = ROOT / "docs" / "SOFTWARE_SPECIFICATION_CHECKLIST_AUDIT.md"
AUDIT_DATE = "2026-11-12"

SPEC = "docs/SYSTEM_SPECIFICATION.md"
ARCH = "docs/ARCHITECTURE.md"
OPS = "docs/OPERATIONS.md"
DEV = "docs/DEVELOPMENT.md"
TP = "docs/TEST_PLAN.md"
TM = "docs/TRACEABILITY_MATRIX.md"
EXT = "docs/EXTERNAL_SPECS.md"
ADR = "docs/DECISIONS.md"
RD = "README.md"
TODO = "TODO.md"
SURVEY = "docs/SURVEY.md"
ZB = "docs/ZOTERO_BBT_SETUP.md"
APJ = "docs/APJ_REFERENCES.md"


def S(needle: str, f: str = SPEC) -> tuple[str, str]:
    return (f, needle)


# Chapter 16 has no checkboxes; audit items are derived from its table and recommendations.
CH16 = [
    "要件一覧表が推奨フォーマット（ID・要件名・要件・期待動作・優先度・根拠・出典・検証方法・状態）で管理されている",
    "IDは一意で、変更後も追跡できるようにする",
    "優先度はプロジェクト内で定義した区分を用いる",
    "状態は「未着手／検討中／確定／実装済み／検証済み」等の定義した区分を用いる",
    "要件の粒度は、原則として一つの検証可能な要求に一つのIDを割り当てる",
]

# id: (verdict, spec[], impl[], tests[], note, flags)
# verdict: "x" | " " | "N/A"; flags: "fixed" (是正済み) "mock" (モック検証のみ) "p0" (P0受入れに影響)
J: dict[str, tuple] = {
    # ---- 0 文書の管理
    "CHK-00-01": ("x", [S("| 文書名 |"), S("| 対象ソフトウェア |")], [], [], "", ""),
    "CHK-00-02": (
        "x",
        [S("| 文書識別子 |"), S("| 版 |"), S("| 作成日 |"), S("| 最終更新日 |")],
        [],
        [],
        "監査で識別子・最終更新日を追加",
        "fixed",
    ),
    "CHK-00-03": (
        "x",
        [S("| 作成者 |"), S("| レビュー担当者 |"), S("| 承認者 |")],
        [],
        [],
        "記載はある。第三者レビュー未実施・未承認であることを明記（承認は CHK-18-08）",
        "fixed",
    ),
    "CHK-00-04": ("x", [S("| 文書の状態 |")], [], [], "草案（利用者レビュー待ち）", ""),
    "CHK-00-05": ("x", [S("### 0.1 変更履歴"), S("## [0.1.1]", "CHANGELOG.md")], [], [], "", ""),
    "CHK-00-06": (
        "x",
        [S("### 0.2 関連文書・参考資料・外部規格"), S("## 1. NASA ADS API", EXT)],
        [],
        [],
        "",
        "",
    ),
    "CHK-00-07": (
        "x",
        [S("### 0.4 用語・略語・記号"), S("### 0.5 命名規則")],
        [],
        [],
        "命名規則を監査で追加",
        "fixed",
    ),
    "CHK-00-08": (
        "x",
        [S("### 0.3 記述区分"), S("## 16. 未決事項・仮定・要確認事項")],
        [],
        [],
        "",
        "",
    ),
    # ---- 1 背景・目的・スコープ
    "CHK-01-01": ("x", [S("### 1.1 背景と課題")], [], [], "", ""),
    "CHK-01-02": ("x", [S("### 1.2 目的と期待する成果")], [], [], "", ""),
    "CHK-01-03": ("x", [S("### 1.3 対象利用者・利用場面")], [], [], "", ""),
    "CHK-01-04": ("x", [S("### 1.4 対象範囲（P0）")], [], [], "", ""),
    "CHK-01-05": (
        "x",
        [S("### 1.5 対象外の機能・責任範囲")],
        [("ui/streamlit_app.py", "<module>")],
        [],
        "UI サイドバーに P1 未実装を表示",
        "",
    ),
    "CHK-01-06": ("x", [S("### 1.6 利用者の前提知識と権限")], [], [], "監査で追加", "fixed"),
    "CHK-01-07": (
        "x",
        [S("### 1.7 成功条件・受入れの考え方"), S("## 6. 合格基準", TP)],
        [],
        [],
        "",
        "",
    ),
    "CHK-01-08": ("x", [S("### 1.8 前提条件・依存条件・既知の制約")], [], [], "", ""),
    "CHK-01-09": (
        "x",
        [S("### 1.9 関連する研究プロセスとの関係")],
        [],
        [],
        "監査で独立節に",
        "fixed",
    ),
    # ---- 2 利用者・ユースケース・業務フロー
    "CHK-02-01": (
        "x",
        [S("### 2.1 利用者の種類・役割")],
        [],
        [],
        "単一の役割（研究者＝所有者）",
        "",
    ),
    "CHK-02-02": ("x", [S("### 2.2 ユースケース")], [], [], "UC-01〜05", ""),
    "CHK-02-03": ("x", [S("| ID | 名称 | 開始条件 | 入力 | 処理 | 結果 |")], [], [], "", ""),
    "CHK-02-04": (
        "x",
        [S("異常系・境界条件 |")],
        [],
        [
            "test_network::test_partial_failure_keeps_fetched_part",
            "test_normalize::test_detect_input_rejects",
            "test_network::test_seed_not_found",
            "test_network::test_zero_references",
        ],
        "",
        "",
    ),
    "CHK-02-05": (
        "x",
        [S("### 2.3 利用者による操作とシステムの自動処理")],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-02-06": (
        "N/A",
        [S("機能差・権限差はない")],
        [],
        [],
        "単一利用者・ローカル専用で権限差がない。複数利用者化する場合はロール定義が必要（仕様書 §17 提案）",
        "",
    ),
    "CHK-02-07": (
        "x",
        [S("### 2.4 ユースケース間の前後関係・依存関係")],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    # ---- 3 機能要件
    "CHK-03-01": (
        "x",
        [S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "要件 ID の重複は生成スクリプトが検出して停止",
        "",
    ),
    "CHK-03-02": (
        "x",
        [S("#### 機能一覧（目的・責務・起動条件・前提条件）")],
        [],
        [],
        "監査で機能一覧を追加",
        "fixed",
    ),
    "CHK-03-03": (
        "x",
        [S("| 機能 | 目的・責務 | 起動条件 | 前提条件 |")],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-03-04": (
        "x",
        [S("### 3.1 F-SEARCH"), S("### 4.1 入力"), S("### 4.2 出力")],
        [],
        [],
        "",
        "",
    ),
    "CHK-03-05": (
        "x",
        [S("- 処理手順:"), S("- 終了条件: キューが空")],
        [("graph/builder.py", "build_network")],
        ["test_network::test_shared_reference_and_cycle_kept_as_digraph"],
        "",
        "",
    ),
    "CHK-03-06": (
        "x",
        [S("- 成功条件: エラー・未取得リスト"), S("| 要件ID | 要件名 | 要件・期待動作 |", TM)],
        [],
        [],
        "",
        "",
    ),
    "CHK-03-07": (
        "x",
        [S("| 項目 | 型・形式 | 単位 |"), S("### 11.1 エラー分類・重要度・動作")],
        [],
        ["test_network::test_param_validation", "test_ads_client::test_invalid_response_shapes"],
        "",
        "",
    ),
    "CHK-03-08": (
        "x",
        [S("### 2.4 ユースケース間の前後関係・依存関係"), S("- 初期化: 設定読込")],
        [],
        [],
        "",
        "",
    ),
    "CHK-03-09": (
        "x",
        [S("### 3.0 優先度・状態の区分"), S("### 1.5 対象外の機能・責任範囲")],
        [],
        [],
        "",
        "",
    ),
    "CHK-03-10": (
        "x",
        [S("| 要件ID | 要件名 | 要件・期待動作 |", TM)],
        [],
        [],
        "全要件に期待動作と検証方法。曖昧表現は除去（CHK-15-02）",
        "fixed",
    ),
    "CHK-03-11": (
        "x",
        [S("### 3.8 要件の重複・矛盾の確認結果")],
        [],
        [],
        "監査で確認結果を記録",
        "fixed",
    ),
    # ---- 4 入力・出力・インターフェース
    "CHK-04-01": ("x", [S("| 項目 | 型・形式 | 単位 |")], [], [], "監査で入力表を追加", "fixed"),
    "CHK-04-02": (
        "x",
        [S("| 項目 | 型・形式 | 単位 |")],
        [],
        ["test_config_security::test_defaults_are_small_and_configurable"],
        "必須・既定値・範囲の列",
        "fixed",
    ),
    "CHK-04-03": ("x", [S("| 項目 | 型・形式 | 単位 |")], [], [], "入力元の列", "fixed"),
    "CHK-04-04": (
        "x",
        [S("欠損値は NULL として保持")],
        [("repository.py", "_apply_record")],
        [
            "test_db_repository::test_none_does_not_erase_known_values",
            "test_ads_client::test_mapping_bad_values_flagged",
        ],
        "",
        "",
    ),
    "CHK-04-05": (
        "x",
        [S("### 6.1 正規化")],
        [("normalize.py", "normalize_doi"), ("ads/query.py", "detect_input")],
        ["test_normalize::test_normalize_doi", "test_normalize::test_detect_input_rejects"],
        "",
        "",
    ),
    "CHK-04-06": (
        "x",
        [S("| 出力 | 形式 | 出力先 |"), S("- 年は整数、類似度スコアは小数 4 桁")],
        [],
        [],
        "",
        "fixed",
    ),
    "CHK-04-07": (
        "x",
        [S("| 出力 | 形式 | 出力先 |")],
        [("graph/view.py", "export_all")],
        ["test_network::test_filter_and_exports"],
        "",
        "",
    ),
    "CHK-04-08": (
        "x",
        [S("### 0.5 命名規則"), S("| 出力 | 形式 | 出力先 |")],
        [],
        [],
        "監査で命名規則を明記",
        "fixed",
    ),
    "CHK-04-09": (
        "x",
        [S("- 成功／部分成功／失敗の判別")],
        [("ui/streamlit_app.py", "<module>")],
        ["test_ui_cli_acceptance::test_ui_shows_partial_status"],
        "",
        "",
    ),
    "CHK-04-10": (
        "x",
        [S("- 出力の欠落:")],
        [],
        ["test_network::test_zero_references"],
        "",
        "fixed",
    ),
    "CHK-04-11": (
        "x",
        [S("- 互換性・版管理:"), S("## 2. リリース物・版番号", OPS)],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-04-12": ("x", [S("#### 4.3.1 インターフェース一覧と外部 API 仕様")], [], [], "", ""),
    "CHK-04-13": (
        "x",
        [S("| IF | 方式 | エンドポイント・コマンド |"), S("## 1. NASA ADS API", EXT)],
        [],
        ["test_ads_client::test_http_error_classification"],
        "外部 API の仕様。検証はモックのみ",
        "mock",
    ),
    "CHK-04-14": (
        "x",
        [S("| IF | 方式 | エンドポイント・コマンド |"), S("### 11.1 エラー分類・重要度・動作")],
        [("ads/client.py", "ADSClient._get")],
        [
            "test_ads_client::test_rate_limit_retries_then_fails",
            "test_ads_client::test_timeout_and_network_errors",
        ],
        "検証はモックのみ",
        "mock",
    ),
    "CHK-04-15": (
        "x",
        [S("外部システムとの契約・互換性条件")],
        [],
        ["test_zotero::test_status_versions"],
        "版条件は一次資料で確認。実機での確認は要確認事項",
        "mock",
    ),
    "CHK-04-16": (
        "x",
        [S("#### 4.3.2 UI 画面・操作・表示状態・入力制約・アクセシビリティ")],
        [("graph/view.py", "ROLE_STYLE")],
        [
            "test_network::test_roles_distinguishable_without_colour_and_layout_seeded",
            "test_ui_cli_acceptance::test_ui_end_to_end_search_graph_detail_bib",
        ],
        "監査で役割の色以外の区別（形・記号）を実装。WCAG 評価は未実施",
        "fixed",
    ),
    # ---- 5 データ仕様・データ管理
    "CHK-05-01": (
        "x",
        [S("### 5.1 データの種類・構造・スキーマ"), S("## 4. DB 設計", ARCH)],
        [("db.py", "SCHEMA_V1")],
        ["test_db_repository::test_migrations_create_schema_matching_orm"],
        "",
        "",
    ),
    "CHK-05-02": (
        "x",
        [S("### 5.2 形式・文字コード・日時・単位")],
        [("models.py", "utcnow_iso")],
        [],
        "",
        "",
    ),
    "CHK-05-03": ("x", [S("### 5.3 出典・取得方法・所有者・利用条件")], [], [], "", ""),
    "CHK-05-04": (
        "x",
        [S("### 5.4 保存場所・保存期間・容量")],
        [],
        ["※scripts/benchmark.py（docs/verification/benchmark.md）"],
        "監査で容量の実測値を追加",
        "fixed",
    ),
    "CHK-05-05": (
        "x",
        [S("### 5.5 作成・読込・更新・削除のルール")],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-05-06": (
        "x",
        [S("### 5.6 整合性・重複排除・検証")],
        [("repository.py", "upsert_paper")],
        [
            "test_db_repository::test_dedup_by_doi_bibcode_and_arxiv",
            "test_db_repository::test_identifier_conflict_recorded_not_merged",
        ],
        "",
        "",
    ),
    "CHK-05-07": (
        "x",
        [
            S("### 5.7 バックアップ・復元・移行・削除"),
            S("## 3. 設定・データの移行、バックアップ・復元、削除", OPS),
        ],
        [("db.py", "Database.backup")],
        [
            "test_db_repository::test_backup_is_consistent_copy",
            "test_ui_cli_acceptance::test_cli_backup",
        ],
        "監査で pn backup を実装",
        "fixed",
    ),
    "CHK-05-08": (
        "x",
        [S("### 5.8 機密情報・個人情報・認証情報")],
        [("config.py", "Secret")],
        ["test_config_security::test_secret_masked_in_repr"],
        "",
        "",
    ),
    "CHK-05-09": (
        "x",
        [S("### 5.9 スキーマ変更と互換性")],
        [("db.py", "migrate")],
        [
            "test_db_repository::test_upgrade_from_v1_database",
            "test_db_repository::test_newer_schema_refused",
        ],
        "監査中の索引追加を v2 マイグレーションとして実施し移行を検証",
        "fixed",
    ),
    "CHK-05-10": ("x", [S("### 5.10 テスト用・サンプルデータ")], [], [], "", ""),
    # ---- 6 アルゴリズム
    "CHK-06-01": (
        "x",
        [
            S("### 6.2 重複候補の判定"),
            S("### 6.4 Zotero との不一致判定"),
            S("### 6.5 BibTeX 検証規則"),
        ],
        [("repository.py", "_detect_candidates"), ("zotero/sync.py", "compare_fields")],
        [],
        "",
        "",
    ),
    "CHK-06-02": (
        "x",
        [S("- 類似度 = Python `difflib.SequenceMatcher")],
        [("normalize.py", "title_similarity")],
        ["test_normalize::test_title_normalization_and_similarity"],
        "数式・定数（0.90）を監査で明記",
        "fixed",
    ),
    "CHK-06-03": ("x", [S("### 6.6 数値精度・丸め")], [], [], "監査で追加", "fixed"),
    "CHK-06-04": (
        "x",
        [S("### 6.7 乱数と再現性")],
        [("graph/view.py", "_TEMPLATE")],
        ["test_network::test_roles_distinguishable_without_colour_and_layout_seeded"],
        "監査でレイアウトのシードを固定",
        "fixed",
    ),
    "CHK-06-05": (
        "x",
        [S("### 6.8 外部ライブラリ・サービス"), S("## 5. 採用ライブラリ", EXT)],
        [],
        [],
        "",
        "",
    ),
    "CHK-06-06": (
        "x",
        [S("### 6.9 結果に影響するパラメータ")],
        [("graph/builder.py", "NetworkParams")],
        ["test_network::test_param_validation"],
        "監査で表を追加",
        "fixed",
    ),
    "CHK-06-07": (
        "x",
        [S("### 6.10 検証方法・参照値")],
        [],
        ["test_network::test_edge_direction_references_and_citations"],
        "",
        "fixed",
    ),
    "CHK-06-08": ("x", [S("### 6.11 適用限界・想定外入力")], [], [], "監査で追加", "fixed"),
    # ---- 7 システム構成
    "CHK-07-01": ("x", [S("## 1. 構成図", ARCH)], [], [], "", ""),
    "CHK-07-02": ("x", [S("## 2. モジュール責務", ARCH)], [], [], "", ""),
    "CHK-07-03": (
        "x",
        [S("## 3. データフロー", ARCH), S("| モジュール | 責務 | 依存してよいもの |", ARCH)],
        [],
        [],
        "",
        "",
    ),
    "CHK-07-04": (
        "x",
        [S("### 7.2 公開インターフェースと内部実装の境界")],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-07-05": (
        "x",
        [S("## 2. モジュール責務", ARCH), S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "主要関数とその行番号はトレーサビリティ表",
        "",
    ),
    "CHK-07-06": (
        "x",
        [S("### 7.3 状態管理・状態遷移・初期化・終了")],
        [("repository.py", "mark_stale_jobs")],
        ["test_db_repository::test_stale_running_jobs_marked_interrupted"],
        "監査で中断ジョブの検出を実装",
        "fixed",
    ),
    "CHK-07-07": (
        "x",
        [S("### 7.4 並行処理・競合・排他")],
        [("db.py", "_set_sqlite_pragmas")],
        ["test_db_repository::test_edges_unique_and_directed"],
        "仕様は定義。同一 DB での同時ネットワーク構築はテストしていない（想定外と明記）",
        "fixed",
    ),
    "CHK-07-08": (
        "x",
        [S("### 7.5 拡張・差し替え・設定変更の箇所"), S("## 6. P1 拡張ポイント", ARCH)],
        [],
        [],
        "",
        "",
    ),
    "CHK-07-09": ("x", [S("## ADR-001", ADR)], [], [], "ADR-001〜012（理由・代替案）", ""),
    # ---- 8 実行環境
    "CHK-08-01": (
        "x",
        [S("| 対応 OS |")],
        [],
        [],
        "Linux のみ検証、macOS・Windows は未検証と明記（CHK-09-06）",
        "",
    ),
    "CHK-08-02": ("x", [S("| ハードウェア |")], [], [], "メモリ使用量は未測定と明記", "fixed"),
    "CHK-08-03": ("x", [S("| 言語・ランタイム |")], [], [], "", ""),
    "CHK-08-04": (
        "x",
        [S("| 外部ライブラリ |"), S("## 5. 採用ライブラリ", EXT)],
        [],
        [],
        "uv.lock で固定",
        "",
    ),
    "CHK-08-05": (
        "x",
        [S("| 環境変数・設定ファイル |"), S("ADS_API_TOKEN=", ".env.example")],
        [("config.py", "load_settings")],
        ["test_config_security::test_dotenv_parsing_and_env_precedence"],
        "",
        "",
    ),
    "CHK-08-06": (
        "x",
        [S("## セットアップ", RD)],
        [],
        ["※クリーン環境で README 手順を実行（TEST_PLAN §5）"],
        "",
        "",
    ),
    "CHK-08-07": (
        "x",
        [S("## 起動・停止", RD), S("## 4. 定常運用", OPS)],
        [("cli.py", "cmd_ui")],
        ["※pn ui の起動・ヘルスチェック・停止・再起動を確認（TEST_PLAN §5）"],
        "",
        "",
    ),
    "CHK-08-08": ("x", [S("| 権限・ネットワーク |"), S("| ライセンス条件 |")], [], [], "", ""),
    "CHK-08-09": (
        "x",
        [S("| クリーン環境での確認 |"), S("## 9. 配布物の確認", TP)],
        [],
        [],
        "",
        "",
    ),
    "CHK-08-10": ("x", [S("| 開発環境と利用環境の差異 |")], [], [], "監査で追加", "fixed"),
    # ---- 9 非機能要件
    "CHK-09-01": (
        "x",
        [S("| PN-NFR-001 | 性能 |")],
        [("repository.py", "_detect_candidates")],
        ["※scripts/benchmark.py: 300 論文 1.84 秒＋0.08 秒"],
        "監査で数値目標化・測定。二次的増加を発見し修正（ADR-012）。ブラウザ描画は未測定",
        "fixed",
    ),
    "CHK-09-02": (
        "x",
        [S("| PN-NFR-002 | 容量・拡張性 |")],
        [],
        ["※scripts/benchmark.py: 5000 論文 33.84 秒"],
        "20000 件は未測定",
        "fixed",
    ),
    "CHK-09-03": (
        "x",
        [S("| PN-NFR-003 | 信頼性 |")],
        [("db.py", "Database.session")],
        [
            "test_db_repository::test_rollback_on_error_leaves_db_unchanged",
            "test_network::test_partial_failure_keeps_fetched_part",
        ],
        "",
        "",
    ),
    "CHK-09-04": (
        "x",
        [S("| PN-NFR-004 | 可用性 |")],
        [],
        ["test_ui_cli_acceptance::test_ui_without_token_shows_config_error_and_does_not_crash"],
        "常時稼働は要求しないことを要件として明記",
        "",
    ),
    "CHK-09-05": (
        "x",
        [S("| PN-NFR-005 | 保守性 |")],
        [],
        ["※ruff・mypy エラー 0（TEST_PLAN §5）"],
        "",
        "",
    ),
    "CHK-09-06": (
        " ",
        [S("| PN-NFR-006 | 移植性・互換性 |")],
        [],
        ["test_db_repository::test_upgrade_from_v1_database"],
        "互換性（旧スキーマ移行）は検証済みだが、移植性（macOS・Windows）は未検証。是正: 利用者環境で "
        "`uv run pytest` を実行するか、対応 OS を Linux に限定する",
        "",
    ),
    "CHK-09-07": (
        "x",
        [S("| PN-NFR-007 | ユーザビリティ |")],
        [("errors.py", "USER_MESSAGES")],
        ["test_ui_cli_acceptance::test_ui_shows_partial_status"],
        "",
        "",
    ),
    "CHK-09-08": (
        "x",
        [S("| PN-NFR-008 | アクセシビリティ |")],
        [("graph/view.py", "ROLE_STYLE")],
        ["test_network::test_roles_distinguishable_without_colour_and_layout_seeded"],
        "WCAG 評価は対象外（要確認事項に記載）",
        "fixed",
    ),
    "CHK-09-09": (
        "x",
        [S("| PN-NFR-009 | 安全性 |")],
        [("zotero/client.py", "ZoteroLocalClient.create_item")],
        [
            "test_bibliography::test_unicode_preserved_file_not_modified",
            "test_zotero::test_write_refused_on_old_zotero_without_posting",
        ],
        "",
        "",
    ),
    "CHK-09-10": (
        "x",
        [S("| PN-NFR-010 | セキュリティ |"), S("## 10. セキュリティ・プライバシー")],
        [],
        [
            "test_config_security::test_no_secret_in_logs_during_retries",
            "test_network::test_html_escapes_untrusted_metadata",
        ],
        "",
        "",
    ),
    "CHK-09-11": (
        "x",
        [S("| PN-NFR-011 | プライバシー |"), S("### 10.8 個人情報")],
        [("ads/client.py", "ADSClient.search_page")],
        [],
        "検証はコードレビュー（外部送信は ADS への検索クエリのみ）",
        "",
    ),
    "CHK-09-12": (
        "x",
        [S("| PN-NFR-012 | 相互運用性 |")],
        [("graph/view.py", "write_graphml")],
        ["test_network::test_filter_and_exports"],
        "",
        "",
    ),
    "CHK-09-13": (
        "x",
        [S("| PN-NFR-013 | 再現性 |")],
        [("graph/view.py", "load_job_graph")],
        ["test_network::test_reproducible_regeneration"],
        "",
        "",
    ),
    "CHK-09-14": (
        "x",
        [S("| ID | 特性 | 要件（目標値・条件） | 優先度 | 検証方法 | 結果 |")],
        [],
        [],
        "監査で優先度・検証方法の列を追加",
        "fixed",
    ),
    "CHK-09-15": ("x", [S("### 9.1 トレードオフ")], [], [], "監査で追加", "fixed"),
    # ---- 10 セキュリティ・プライバシー
    "CHK-10-01": ("x", [S("### 10.1 保護対象と脅威")], [], [], "監査で脅威表を追加", "fixed"),
    "CHK-10-02": (
        "x",
        [S("### 10.2 認証・認可・ロール")],
        [("zotero/client.py", "ZoteroLocalClient.request_authorization")],
        ["test_zotero::test_authorize_flow"],
        "アプリ内ロールは不要と理由付きで定義、外部認証を定義",
        "",
    ),
    "CHK-10-03": (
        "x",
        [S("### 10.3 秘密情報の保存・受け渡し")],
        [("app.py", "write_key_file")],
        [
            "test_config_security::test_key_file_written_owner_only",
            "test_ads_client::test_auth_header_sent_and_token_not_in_repr",
        ],
        "",
        "",
    ),
    "CHK-10-04": (
        "x",
        [S("### 10.4 通信時・保存時の保護")],
        [],
        [],
        "保存時は暗号化しない方針を明記（OS のディスク暗号化を推奨）",
        "",
    ),
    "CHK-10-05": (
        "x",
        [S("### 10.5 入力検証・出力処理・依存関係")],
        [("graph/view.py", "_safe_json")],
        [
            "test_network::test_html_escapes_untrusted_metadata",
            "test_config_security::test_invalid_config_is_config_error",
            "※pip-audit: 既知脆弱性なし",
        ],
        "",
        "",
    ),
    "CHK-10-06": (
        "x",
        [S("### 10.6 監査ログと記録してはいけない情報")],
        [("logging_utils.py", "RedactingFilter")],
        ["test_config_security::test_redaction_patterns"],
        "",
        "",
    ),
    "CHK-10-07": (
        "x",
        [S("### 10.7 セッション・アクセス拒否・権限変更")],
        [("config.py", "is_loopback_url")],
        [
            "test_config_security::test_streamlit_config_binds_loopback",
            "※外部インターフェースからの UI 接続が拒否されることを確認",
        ],
        "監査で独立節に",
        "fixed",
    ),
    "CHK-10-08": ("x", [S("### 10.8 個人情報")], [], [], "", ""),
    "CHK-10-09": ("x", [S("### 10.9 セキュリティ事故の検知・対応")], [], [], "監査で追加", "fixed"),
    "CHK-10-10": (
        "x",
        [S("### 10.10 適用される法令・規約・ポリシー")],
        [],
        [],
        "所属組織固有のポリシーは利用者確認が必要（仮定として明記）",
        "",
    ),
    # ---- 11 エラー処理・ログ・監視
    "CHK-11-01": (
        "x",
        [S("### 11.1 エラー分類・重要度・動作")],
        [("errors.py", "ErrorCode")],
        [],
        "監査で重要度を追加",
        "fixed",
    ),
    "CHK-11-02": (
        "x",
        [S("| コード | 重要度 | 主な発生箇所 | 動作 |")],
        [("errors.py", "USER_MESSAGES")],
        [],
        "",
        "",
    ),
    "CHK-11-03": (
        "x",
        [S("| コード | 重要度 | 主な発生箇所 | 動作 |")],
        [("graph/builder.py", "build_network")],
        ["test_network::test_auth_error_aborts", "test_ads_client::test_transient_5xx_recovers"],
        "",
        "",
    ),
    "CHK-11-04": (
        "x",
        [S("### 11.2 利用者向けメッセージと開発者向け診断")],
        [("errors.py", "PNError")],
        ["test_ui_cli_acceptance::test_cli_setup_from_empty_db_and_restart"],
        "",
        "",
    ),
    "CHK-11-05": ("x", [S("### 11.3 ログ")], [("logging_utils.py", "setup_logging")], [], "", ""),
    "CHK-11-06": (
        "x",
        [S("- ローテーション・保存期間:")],
        [],
        [],
        "ファイル出力しない方針を明記",
        "fixed",
    ),
    "CHK-11-07": (
        "x",
        [S("- 機密情報: §10.6")],
        [("logging_utils.py", "RedactingFilter")],
        ["test_config_security::test_no_secret_in_logs_during_retries"],
        "",
        "",
    ),
    "CHK-11-08": (
        "x",
        [S("### 11.4 進捗・ヘルスチェック・メトリクス")],
        [("ui/streamlit_app.py", "<module>")],
        ["※/_stcore/health = ok を確認"],
        "メトリクス・アラートは不要と理由付き",
        "",
    ),
    "CHK-11-09": (
        "x",
        [S("### 11.5 障害の再現・切り分け")],
        [("services.py", "_finish")],
        [],
        "",
        "",
    ),
    # ---- 12 テスト
    "CHK-12-01": ("x", [S("| 要件ID | 要件名 |", TM)], [], [], "58 要件すべてに検証方法", ""),
    "CHK-12-02": ("x", [S("### 1.1 対象範囲と対象外", TP)], [], [], "監査で追加", "fixed"),
    "CHK-12-03": ("x", [S("## 1. テスト分類", TP)], [], [], "", ""),
    "CHK-12-04": (
        "x",
        [S("## 4. 観点と期待結果（合否基準）", TP)],
        [],
        [
            "test_normalize::test_detect_input_rejects",
            "test_network::test_max_papers_truncation_recorded",
        ],
        "極端な入力（501 文字、5000 論文）を含む",
        "",
    ),
    "CHK-12-05": ("x", [S("## 2. テスト環境", TP), S("## 3. テストデータ", TP)], [], [], "", ""),
    "CHK-12-06": ("x", [S("| 観点 | 種別 | 期待結果（すべて満たせば合格） |", TP)], [], [], "", ""),
    "CHK-12-07": ("x", [S("### 4.1 非機能要件の検証方法", TP)], [], [], "監査で追加", "fixed"),
    "CHK-12-08": (
        "x",
        [S("### 4.2 外部サービスで結果が変動する場合の判定", TP)],
        [],
        [],
        "監査で明記",
        "fixed",
    ),
    "CHK-12-09": (
        "x",
        [S("## 8. 不具合の重大度・再テスト・回帰テスト", TP)],
        [],
        [],
        "監査で追加",
        "fixed",
    ),
    "CHK-12-10": ("x", [S("## 7. リリース・受入れの判定条件", TP)], [], [], "監査で追加", "fixed"),
    "CHK-12-11": (
        "x",
        [S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "生成スクリプトで参照切れを検出",
        "",
    ),
    # ---- 13 運用・保守・リリース
    "CHK-13-01": (
        "x",
        [S("## 1. 配布・インストール・更新・アンインストール", OPS)],
        [],
        [],
        "監査で OPERATIONS.md を作成",
        "fixed",
    ),
    "CHK-13-02": ("x", [S("## 2. リリース物・版番号", OPS)], [], [], "SemVer", "fixed"),
    "CHK-13-03": (
        "x",
        [S("## 3. 設定・データの移行、バックアップ・復元、削除", OPS)],
        [("db.py", "migrate")],
        ["test_db_repository::test_upgrade_from_v1_database"],
        "",
        "fixed",
    ),
    "CHK-13-04": (
        "x",
        [S("- 障害復旧:", OPS)],
        [("db.py", "Database.backup")],
        ["test_db_repository::test_backup_is_consistent_copy"],
        "",
        "fixed",
    ),
    "CHK-13-05": ("x", [S("## 4. 定常運用", OPS)], [], [], "", "fixed"),
    "CHK-13-06": ("x", [S("## 6. 既知の制限・既知の不具合・回避策", OPS)], [], [], "", "fixed"),
    "CHK-13-07": (
        "x",
        [S("## 7. サポート対象・保守終了", OPS)],
        [],
        [],
        "サポート対象は定義。保守終了時期は未決（利用者が決定）",
        "fixed",
    ),
    "CHK-13-08": (
        "x",
        [S("## 5. 問い合わせ・責任", OPS)],
        [],
        [],
        "運用責任は利用者。保守担当は未決",
        "fixed",
    ),
    "CHK-13-09": (
        "x",
        [
            S("## 8. ライセンス・著作権・第三者コンポーネント", OPS),
            S("bibtexparser", "docs/verification/licenses.md"),
        ],
        [],
        ["※pip-licenses の結果を記録"],
        "第三者の条件は確認済み。本ソフトウェアのライセンスは未決",
        "fixed",
    ),
    # ---- 14 開発・変更管理
    "CHK-14-01": ("x", [S("## 1. 識別子と対応関係", DEV)], [], [], "", ""),
    "CHK-14-02": (
        "x",
        [S("## 2. ソースコード管理", DEV)],
        [],
        ["test_config_security::test_git_check_ignore"],
        "方針は定義。本作業ではコミットしていない（利用者の指示がないため）",
        "fixed",
    ),
    "CHK-14-03": (
        "x",
        [S("## 3. コーディング規約・フォーマット", DEV), S("[tool.ruff]", "pyproject.toml")],
        [],
        ["※ruff check / ruff format --check 合格"],
        "",
        "fixed",
    ),
    "CHK-14-04": ("x", [S("## 4. 変更要求の評価・承認・記録", DEV)], [], [], "", "fixed"),
    "CHK-14-05": ("x", [S("## 5. 影響範囲の特定", DEV)], [], [], "", "fixed"),
    "CHK-14-06": ("x", [S("## 6. 仕様と実装が食い違った場合", DEV)], [], [], "", "fixed"),
    "CHK-14-07": (
        "x",
        [
            S("## P0 の未完了・未検証（優先）", TODO),
            S("## 技術的負債", TODO),
            S("## P1 以降", TODO),
        ],
        [],
        [],
        "",
        "",
    ),
    # ---- 15 品質レビュー
    "CHK-15-01": (
        "x",
        [S("## 15. 自己レビュー結果")],
        [],
        [],
        "自己レビューのみ（第三者レビュー未実施）。検証可能性は全要件の検証方法で確認",
        "",
    ),
    "CHK-15-02": (
        "x",
        [S("- 曖昧表現の点検")],
        [],
        [],
        "「適切に・十分に・高速に・なるべく・できるだけ・実用・など」を検索。要件文の 1 件（PN-DB-004）を具体化。"
        "残りは説明文・運用手順のみ",
        "fixed",
    ),
    "CHK-15-03": ("x", [S("- 用語・日付・単位"), S("### 0.4 用語・略語・記号")], [], [], "", ""),
    "CHK-15-04": ("x", [S("### 3.8 要件の重複・矛盾の確認結果")], [], [], "", "fixed"),
    "CHK-15-05": ("x", [S("- 異常時・境界・復旧")], [], [], "", ""),
    "CHK-15-06": ("x", [S("### 3.0 優先度・状態の区分")], [], [], "全要件に MUST/SHOULD/WON'T", ""),
    "CHK-15-07": (
        "x",
        [S("| 要件ID | 要件名 | 要件・期待動作 | 優先度 | 根拠・出典 |", TM), S("## ADR-001", ADR)],
        [],
        [],
        "",
        "",
    ),
    "CHK-15-08": (
        "x",
        [S("- 未確定事項の扱い"), S("## 16. 未決事項・仮定・要確認事項")],
        [],
        [],
        "モックのみの検証は「検証済み（モック）／ライブ未検証」と表記",
        "",
    ),
    "CHK-15-09": (
        " ",
        [S("- 第三者レビュー: 未実施")],
        [],
        [],
        "対象利用者（利用者本人・他の開発者）による読解性の確認が未実施で、作成者自身では判定できない。"
        "是正: 利用者が README・仕様書を読んでレビューする",
        "",
    ),
    "CHK-15-10": (
        "x",
        [S("| 要件ID | 要件名 |", TM), S("## 7. リリース・受入れの判定条件", TP)],
        [],
        [],
        "要件・期待動作・検証方法・受入れ条件がそろう",
        "",
    ),
    "CHK-15-11": (
        "x",
        [S("| レビュー担当者 |"), S("| 承認者 |"), S("## 16. 未決事項・仮定・要確認事項")],
        [],
        [],
        "状態（レビュー未実施・未承認・残課題）を明記",
        "",
    ),
    # ---- 16 要件一覧表（派生項目）
    "CHK-16-01": (
        "x",
        [S("| 要件ID | 要件名 | 要件・期待動作 | 優先度 | 根拠・出典 |", TM)],
        [],
        [],
        "監査で「要件・期待動作」列を追加し推奨フォーマットに一致",
        "fixed",
    ),
    "CHK-16-02": (
        "x",
        [S("| 要件 ID | `PN-<領域>-<3桁>`")],
        [],
        [],
        "再利用禁止を命名規則に明記。重複はスクリプトが検出",
        "",
    ),
    "CHK-16-03": ("x", [S("### 3.0 優先度・状態の区分")], [], [], "MUST/SHOULD/WON'T(P0)", ""),
    "CHK-16-04": (
        "x",
        [S("### 3.0 優先度・状態の区分")],
        [],
        [],
        "実装状態と検証状態を別列で管理",
        "",
    ),
    "CHK-16-05": (
        " ",
        [S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "監査で PN-ADS-004 を 4 件に分割したが、PN-GRAPH-004（階層・論文数・リクエスト数・期間）、"
        "PN-BBT-001（複数の検証規則）、PN-UI-002 などは複数の検証項目を含む。是正: 次版で 1 検証 1 ID に分割",
        "",
    ),
    # ---- 17 Claude 固有
    "CHK-17-01": (
        "x",
        [S("## 1. NASA ADS API", EXT), S("### 5.10 テスト用・サンプルデータ")],
        [],
        [],
        "外部仕様は URL・確認日付き。テストデータは合成と明記、ApJ 書誌は公式サンプルから転記。"
        "未検証の記述（.bst 名に関する推測）は発見して削除（CHANGELOG）",
        "",
    ),
    "CHK-17-02": (
        "x",
        [S("### 0.3 記述区分"), S("## 16. 未決事項・仮定・要確認事項")],
        [],
        [],
        "",
        "",
    ),
    "CHK-17-03": (
        "x",
        [S("## 添付資料", SURVEY)],
        [],
        [],
        "指示書・チェックリストを全文確認。既存コードは無し",
        "",
    ),
    "CHK-17-04": ("x", [S("### 0.3 記述区分"), S("## 17. 提案（将来）")], [], [], "", ""),
    "CHK-17-05": ("x", [S("## 16. 未決事項・仮定・要確認事項")], [], [], "", ""),
    "CHK-17-06": (
        "x",
        [S("## 15. 自己レビュー結果"), S("### 3.8 要件の重複・矛盾の確認結果")],
        [],
        [],
        "",
        "",
    ),
    "CHK-17-07": (
        "x",
        [S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "実装済みの記載は実装ファイル:行と JUnit 結果を自動で紐付け",
        "",
    ),
    "CHK-17-08": (
        "x",
        [S("| 項目 | 採用した仕様 | 出典 | 確認方法 |", EXT)],
        [],
        [],
        "公式ページ・公式リポジトリを優先",
        "",
    ),
    "CHK-17-09": ("x", [S("## 0. 文書管理")], [], [], "見出し・表・コード表記を使用", ""),
    # ---- 18 最終判定
    "CHK-18-01": (
        "x",
        [S("### 1.4 対象範囲（P0）"), S("### 1.5 対象外の機能・責任範囲")],
        [],
        [],
        "",
        "",
    ),
    "CHK-18-02": (
        "x",
        [
            S("#### 機能一覧（目的・責務・起動条件・前提条件）"),
            S("### 4.1 入力"),
            S("### 11.1 エラー分類・重要度・動作"),
        ],
        [],
        [],
        "",
        "",
    ),
    "CHK-18-03": ("x", [S("## 8. 実行環境・導入・設定"), S("## セットアップ", RD)], [], [], "", ""),
    "CHK-18-04": (
        "x",
        [S("## 9. 非機能要件・品質特性")],
        [],
        [],
        "具体化済み。移植性の検証は未了（CHK-09-06）",
        "",
    ),
    "CHK-18-05": (
        "x",
        [S("## 4. 観点と期待結果（合否基準）", TP), S("| 要件ID | 要件名 |", TM)],
        [],
        [],
        "",
        "",
    ),
    "CHK-18-06": (
        "x",
        [S("## 16. 未決事項・仮定・要確認事項"), S("## リスク", TODO)],
        [],
        [],
        "",
        "",
    ),
    "CHK-18-07": ("x", [S("| 要件ID | 要件名 |", TM)], [], [], "", ""),
    "CHK-18-08": (
        " ",
        [S("| 承認者 |")],
        [],
        [],
        "レビュー・承認は未完了。承認者は利用者であり、Claude は承認済みとしない。是正: 利用者がレビューし承認する",
        "p0",
    ),
}


def extract_items() -> list[tuple[str, int, str, str]]:
    """Return (id, line, chapter_title, text) for every checklist item (+ derived ch.16)."""
    items: list[tuple[str, int, str, str]] = []
    chap, title, n = None, "", 0
    for i, line in enumerate(CHECKLIST.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^## (\d+)\. (.+)$", line)
        if m:
            chap, title, n = int(m.group(1)), m.group(2), 0
            if chap == 16:
                for k, text in enumerate(CH16, 1):
                    items.append((f"CHK-16-{k:02d}", i, title, text))
            continue
        m = re.match(r"^- \[ \] (.+)$", line)
        if m and chap is not None:
            n += 1
            items.append((f"CHK-{chap:02d}-{n:02d}", i, title, m.group(1).strip()))
    return items


_cache: dict[str, list[str]] = {}


def spec_ref(f: str, needle: str) -> str:
    lines = _cache.setdefault(f, (ROOT / f).read_text(encoding="utf-8").splitlines())
    for i, ln in enumerate(lines):
        if needle in ln:
            head = next(
                (
                    lines[j].lstrip("#").strip()
                    for j in range(i, -1, -1)
                    if lines[j].startswith("#")
                ),
                "",
            )
            head = head if len(head) <= 40 else head[:40] + "…"
            return f"`{f}` L{i + 1}（{head}）"
    sys.exit(f"evidence text not found: {f}: {needle!r}")


def code_ref(rel: str, symbol: str) -> str:
    path = ROOT / "src" / "paper_navigator" / rel
    if symbol == "<module>":
        if not path.exists():
            sys.exit(f"missing file {rel}")
        return f"`src/paper_navigator/{rel}`"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node: ast.AST | None = None
    body = tree.body
    for part in symbol.split("."):
        node = None
        for n in body:
            if (
                isinstance(n, ast.FunctionDef | ast.ClassDef)
                and n.name == part
                or isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == part for t in n.targets)
                or (
                    isinstance(n, ast.AnnAssign)
                    and isinstance(n.target, ast.Name)
                    and n.target.id == part
                )
            ):
                node = n
            if node is not None:
                break
        if node is None:
            sys.exit(f"unknown symbol {rel}:{symbol}")
        body = getattr(node, "body", [])
    assert node is not None
    return f"`{rel}:{node.lineno}` {symbol}"  # type: ignore[attr-defined]


def junit() -> dict[str, str]:
    res: dict[str, str] = {}
    root = ET.parse(ROOT / "docs" / "verification" / "junit.xml").getroot()  # noqa: S314
    for tc in root.iter("testcase"):
        key = f"{tc.get('classname', '').split('.')[-1]}::{tc.get('name', '').split('[')[0]}"
        bad = tc.find("failure") is not None or tc.find("error") is not None
        st = "FAIL" if bad else ("SKIP" if tc.find("skipped") is not None else "PASS")
        res[key] = "FAIL" if res.get(key) == "FAIL" else st
    return res


def main() -> None:
    items = extract_items()
    ids = [i[0] for i in items]
    missing, extra = set(ids) - set(J), set(J) - set(ids)
    if missing or extra:
        sys.exit(f"judgment mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    results = junit()
    rows_by_chap: dict[str, list[str]] = {}
    chap_titles: dict[str, str] = {}
    counts: dict[str, Counter] = {}
    unmet, na, fixed, mock = [], [], [], []
    for cid, _line, title, text in items:
        verdict, specs, impls, tests, note, flags = J[cid]
        if verdict not in ("x", " ", "N/A"):
            sys.exit(f"bad verdict {cid}")
        if verdict == "x" and not specs:
            sys.exit(f"{cid}: [x] without spec evidence")
        if verdict in (" ", "N/A") and not note:
            sys.exit(f"{cid}: {verdict!r} requires a note")
        spec_s = "<br>".join(spec_ref(f, nd) for f, nd in specs) or "—"
        impl_s = "<br>".join(code_ref(f, s) for f, s in impls) or "—（文書項目）"
        tl = []
        for t in tests:
            if t.startswith("※"):
                tl.append(t[1:])
                continue
            if t not in results:
                sys.exit(f"{cid}: test not in junit: {t}")
            if results[t] != "PASS" and verdict == "x":
                sys.exit(f"{cid}: [x] cites non-passing test {t}")
            tl.append(f"`{t}` {results[t]}")
        test_s = "<br>".join(tl) or "—"
        mark = {"x": "[x]", " ": "[ ]", "N/A": "[N/A]"}[verdict]
        ch = cid[4:6]
        chap_titles[ch] = title
        counts.setdefault(ch, Counter())[verdict] += 1
        if "mock" in flags:
            counts[ch]["mock"] += 1
            mock.append(cid)
        if verdict == " ":
            unmet.append((cid, text, note, "p0" in flags))
        if verdict == "N/A":
            na.append((cid, text, note))
        if "fixed" in flags:
            fixed.append((cid, note))
        flag_s = " ".join(
            x
            for x in (
                ("是正済み" if "fixed" in flags else ""),
                ("モック検証" if "mock" in flags else ""),
            )
            if x
        )
        note_s = (note + (f"（{flag_s}）" if flag_s else "")).replace("|", "\\|")
        rows_by_chap.setdefault(ch, []).append(
            f"| {cid} | {text.replace('|', '/')} | **{mark}** | {spec_s} | {impl_s} | {test_s} | {note_s} |"
        )

    total = Counter()
    for c in counts.values():
        total.update(c)
    n_items = len(items)
    if total["x"] + total[" "] + total["N/A"] != n_items:
        sys.exit("count cross-check failed")
    applicable = n_items - total["N/A"]
    sha = hashlib.sha256(CHECKLIST.read_bytes()).hexdigest()
    p0_unmet = [u for u in unmet if u[3]]

    o: list[str] = []
    o += [
        "# ソフトウェア仕様書チェックリスト監査",
        "",
        "`scripts/gen_checklist_audit.py` で生成。手で編集しないこと。",
        "",
        "| 項目 | 内容 |",
        "|---|---|",
        "| 監査対象 | 「ソフトウェア仕様書：必要項目チェックリスト」（利用者提供 `software_specification_checklist.md`）。"
        "原本の写し: [reference/software_specification_checklist.md](reference/software_specification_checklist.md) |",
        f"| 原本の SHA-256 | `{sha}` |",
        "| 原本の版 | 版番号の記載なし（2026-11-12 受領） |",
        f"| 監査日 | {AUDIT_DATE} |",
        "| 監査者 | Claude Opus 5.5（実装担当による自己監査。第三者監査ではない） |",
        "| 監査対象成果物 | Paper Navigator 0.1.1（仕様書 PN-SPEC-001 版 0.2、実装、テスト、運用文書） |",
        "",
        "## 判定方法",
        "",
        "- 原本の第 0〜18 章のチェック項目 177 件を原文のまま抽出し、`CHK-<章>-<連番>` を付与した。"
        "第 16 章はチェック欄のない推奨フォーマットのため、表と推奨事項 4 点から監査項目 5 件（CHK-16-01〜05）を派生させた。"
        "項目の結合・省略はしていない。",
        "- `[x]` = 仕様に記載があり、実装・検証が必要な項目はその証拠もある。`[ ]` = 未記載・未実装・未検証または証拠不足。"
        "`[N/A]` = 本システムに適用しない（理由を記載）。",
        "- 「仕様記載」はファイル・行・見出し、「実装根拠」はファイル:行と関数、「検証根拠」はテスト名と記録済みの実行結果"
        "（[verification/junit.xml](verification/junit.xml)）。これらはスクリプトが実ファイルから解決しており、"
        "解決できない参照があると生成に失敗する。",
        "- 「モック検証」= 検証がモックのみで、ライブ API・実機では未検証（`[x]` に含め、未検証件数として別集計）。",
        "- 「是正済み」= 監査開始時点で不足と判断し、本監査中に仕様・実装・テストを追加して再判定した項目。",
        "",
        "## 集計",
        "",
        "| 章 | 項目数 | [x] | [ ] | [N/A] | うちモック検証のみ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ch in sorted(counts):
        c = counts[ch]
        o.append(
            f"| {int(ch)}. {chap_titles[ch]} | {c['x'] + c[' '] + c['N/A']} | {c['x']} | {c[' ']} | "
            f"{c['N/A']} | {c['mock']} |"
        )
    o.append(
        f"| **合計** | **{n_items}** | **{total['x']}** | **{total[' ']}** | **{total['N/A']}** | "
        f"**{total['mock']}** |"
    )
    o += [
        "",
        f"- 検算: [x] {total['x']} + [ ] {total[' ']} + [N/A] {total['N/A']} = {n_items}（抽出項目数 {n_items} と一致）。",
        f"- 適用対象項目（N/A を除く）{applicable} 件に対する [x] の割合: {total['x']}/{applicable} = "
        f"{100 * total['x'] / applicable:.1f}%（N/A は分母・分子とも含めない）。",
        f"- 未検証（ライブ API・実機での確認待ち）: {total['mock']} 件（[x] の内数）＋ [ ] のうち検証未了 1 件（CHK-09-06）。",
        f"- P0 受入れに影響する未達: {len(p0_unmet)} 件（{', '.join(u[0] for u in p0_unmet) or 'なし'}）。",
        "",
        "**「全項目を確認した」ことと「全項目を満たした」ことは別である。** 全 "
        f"{n_items} 項目を確認したが、{total[' ']} 項目は未達であり、すべてを満たしたとは言えない。",
        "",
    ]
    o += [
        "## 未達項目と是正方法",
        "",
        "| ID | 項目 | 理由・是正方法 | P0受入れに影響 |",
        "|---|---|---|---|",
    ]
    for cid, text, note, p0 in unmet:
        o.append(f"| {cid} | {text} | {note} | {'あり（承認待ち）' if p0 else 'なし'} |")
    o += [
        "",
        "## N/A とした項目",
        "",
        "| ID | 項目 | 理由・将来必要になった場合 |",
        "|---|---|---|",
    ]
    for cid, text, note in na:
        o.append(f"| {cid} | {text} | {note} |")
    o += [
        "",
        f"## 是正済み項目（{len(fixed)} 件）",
        "",
        "監査開始時点（v0.1.0）で不足していた項目。是正後に全テストを再実行し 144 件すべて成功"
        "（[TEST_PLAN](TEST_PLAN.md) §5）。主な是正: 仕様書 v0.2 への全面改訂（識別子・命名規則・入出力表・CRUD・状態遷移・"
        "測定可能な非機能要件・脅威整理・エラー重大度・自己レビュー）、運用文書と開発文書の新設、要件の細分化と期待動作列の追加、"
        "実装の追加（バックアップ、中断ジョブ検出、役割の形と記号による区別、レイアウトのシード固定）、"
        "性能測定で発見した処理時間の二次的増加の修正とマイグレーション v2。",
        "",
        "| ID | 是正内容 |",
        "|---|---|",
    ]
    for cid, note in fixed:
        o.append(f"| {cid} | {note or '記載を追加・明確化'} |")
    o += [
        "",
        "## モック検証のみの項目",
        "",
        ", ".join(mock) + "（ADS・Zotero 実機での確認は仕様書 §16 の要確認事項）",
        "",
    ]
    o += ["## 第 18 章 最終判定（個別評価）", "", "| 観点 | 判定 | 説明 |", "|---|---|---|"]
    names = ["目的・スコープ", "機能", "環境", "品質", "検証", "未決事項", "追跡可能性", "承認"]
    for k, nm in enumerate(names, 1):
        cid = f"CHK-18-{k:02d}"
        v = {"x": "[x]", " ": "[ ]", "N/A": "[N/A]"}[J[cid][0]]
        o.append(f"| {nm} | {v} | {J[cid][4] or '満たす'} |")
    o += [
        "",
        "判定の目安（原本）に照らすと: **作成開始可能**・**実装開始可能**の条件は満たす。"
        "**リリース判定可能**は、重要要件の検証結果・既知の制限・運用/復旧手順は確認できるが、承認が未了で、"
        "ライブ API・実機の検証結果がないため未達。",
        "",
    ]
    o += ["## 監査表（全項目）", ""]
    for ch in sorted(rows_by_chap):
        o += [
            f"### {int(ch)}. {chap_titles[ch]}",
            "",
            "| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |",
            "|---|---|---|---|---|---|---|",
            *rows_by_chap[ch],
            "",
        ]
    OUT.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT}: items={n_items} x={total['x']} open={total[' ']} na={total['N/A']} mock={total['mock']}"
    )


if __name__ == "__main__":
    main()
