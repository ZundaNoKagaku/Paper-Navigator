# ソフトウェア仕様書チェックリスト監査

`scripts/gen_checklist_audit.py` で生成。手で編集しないこと。

| 項目 | 内容 |
|---|---|
| 監査対象 | 「ソフトウェア仕様書：必要項目チェックリスト」（利用者提供 `software_specification_checklist.md`）。原本の写し: [reference/software_specification_checklist.md](reference/software_specification_checklist.md) |
| 原本の SHA-256 | `b324712f6bf2a1855d0b21bff2e3273a4170fec0962f7b1dd334595ab6a6ea67` |
| 原本の版 | 版番号の記載なし（2026-11-12 受領） |
| 監査日 | 2026-11-12 |
| 監査者 | Claude Opus 5.5（実装担当による自己監査。第三者監査ではない） |
| 監査対象成果物 | Paper Navigator 0.1.1（仕様書 PN-SPEC-001 版 0.2、実装、テスト、運用文書） |

## 判定方法

- 原本の第 0〜18 章のチェック項目 177 件を原文のまま抽出し、`CHK-<章>-<連番>` を付与した。第 16 章はチェック欄のない推奨フォーマットのため、表と推奨事項 4 点から監査項目 5 件（CHK-16-01〜05）を派生させた。項目の結合・省略はしていない。
- `[x]` = 仕様に記載があり、実装・検証が必要な項目はその証拠もある。`[ ]` = 未記載・未実装・未検証または証拠不足。`[N/A]` = 本システムに適用しない（理由を記載）。
- 「仕様記載」はファイル・行・見出し、「実装根拠」はファイル:行と関数、「検証根拠」はテスト名と記録済みの実行結果（[verification/junit.xml](verification/junit.xml)）。これらはスクリプトが実ファイルから解決しており、解決できない参照があると生成に失敗する。
- 「モック検証」= 検証がモックのみで、ライブ API・実機では未検証（`[x]` に含め、未検証件数として別集計）。
- 「是正済み」= 監査開始時点で不足と判断し、本監査中に仕様・実装・テストを追加して再判定した項目。

## 集計

| 章 | 項目数 | [x] | [ ] | [N/A] | うちモック検証のみ |
|---|---:|---:|---:|---:|---:|
| 0. 文書の管理 | 8 | 8 | 0 | 0 | 0 |
| 1. 背景・目的・スコープ | 9 | 9 | 0 | 0 | 0 |
| 2. 利用者・ユースケース・業務フロー | 7 | 6 | 0 | 1 | 0 |
| 3. 機能要件 | 11 | 11 | 0 | 0 | 0 |
| 4. 入力・出力・インターフェース | 16 | 16 | 0 | 0 | 3 |
| 5. データ仕様・データ管理 | 10 | 10 | 0 | 0 | 0 |
| 6. アルゴリズム・計算・ビジネスルール | 8 | 8 | 0 | 0 | 0 |
| 7. システム構成・ソフトウェア設計 | 9 | 9 | 0 | 0 | 0 |
| 8. 実行環境・導入・設定 | 10 | 10 | 0 | 0 | 0 |
| 9. 非機能要件・品質特性 | 15 | 14 | 1 | 0 | 0 |
| 10. セキュリティ・プライバシー（該当する場合） | 10 | 10 | 0 | 0 | 0 |
| 11. エラー処理・ログ・監視 | 9 | 9 | 0 | 0 | 0 |
| 12. テスト・検証・受入れ | 11 | 11 | 0 | 0 | 0 |
| 13. 運用・保守・リリース | 9 | 9 | 0 | 0 | 0 |
| 14. 開発・変更管理 | 7 | 7 | 0 | 0 | 0 |
| 15. 仕様書全体の品質レビュー | 11 | 10 | 1 | 0 | 0 |
| 16. 要件一覧表（推奨フォーマット） | 5 | 4 | 1 | 0 | 0 |
| 17. Claude Opus 5.5で仕様書を作成する際の確認事項 | 9 | 9 | 0 | 0 | 0 |
| 18. 最終判定 | 8 | 7 | 1 | 0 | 0 |
| **合計** | **182** | **177** | **4** | **1** | **3** |

- 検算: [x] 177 + [ ] 4 + [N/A] 1 = 182（抽出項目数 182 と一致）。
- 適用対象項目（N/A を除く）181 件に対する [x] の割合: 177/181 = 97.8%（N/A は分母・分子とも含めない）。
- 未検証（ライブ API・実機での確認待ち）: 3 件（[x] の内数）＋ [ ] のうち検証未了 1 件（CHK-09-06）。
- P0 受入れに影響する未達: 1 件（CHK-18-08）。

**「全項目を確認した」ことと「全項目を満たした」ことは別である。** 全 182 項目を確認したが、4 項目は未達であり、すべてを満たしたとは言えない。

## 未達項目と是正方法

| ID | 項目 | 理由・是正方法 | P0受入れに影響 |
|---|---|---|---|
| CHK-09-06 | **移植性・互換性**：対応環境、旧版・外部システムとの互換性 | 互換性（旧スキーマ移行）は検証済みだが、移植性（macOS・Windows）は未検証。是正: 利用者環境で `uv run pytest` を実行するか、対応 OS を Linux に限定する | なし |
| CHK-15-09 | 仕様書の内容が対象利用者（開発者、テスター、運用者等）に理解可能である | 対象利用者（利用者本人・他の開発者）による読解性の確認が未実施で、作成者自身では判定できない。是正: 利用者が README・仕様書を読んでレビューする | なし |
| CHK-16-05 | 要件の粒度は、原則として一つの検証可能な要求に一つのIDを割り当てる | 監査で PN-ADS-004 を 4 件に分割したが、PN-GRAPH-004（階層・論文数・リクエスト数・期間）、PN-BBT-001（複数の検証規則）、PN-UI-002 などは複数の検証項目を含む。是正: 次版で 1 検証 1 ID に分割 | なし |
| CHK-18-08 | **承認**：必要なレビューと承認が完了している | レビュー・承認は未完了。承認者は利用者であり、Claude は承認済みとしない。是正: 利用者がレビューし承認する | あり（承認待ち） |

## N/A とした項目

| ID | 項目 | 理由・将来必要になった場合 |
|---|---|---|
| CHK-02-06 | 権限や利用者ごとの機能差がある場合、その条件が定義されている | 単一利用者・ローカル専用で権限差がない。複数利用者化する場合はロール定義が必要（仕様書 §17 提案） |

## 是正済み項目（66 件）

監査開始時点（v0.1.0）で不足していた項目。是正後に全テストを再実行し 144 件すべて成功（[TEST_PLAN](TEST_PLAN.md) §5）。主な是正: 仕様書 v0.2 への全面改訂（識別子・命名規則・入出力表・CRUD・状態遷移・測定可能な非機能要件・脅威整理・エラー重大度・自己レビュー）、運用文書と開発文書の新設、要件の細分化と期待動作列の追加、実装の追加（バックアップ、中断ジョブ検出、役割の形と記号による区別、レイアウトのシード固定）、性能測定で発見した処理時間の二次的増加の修正とマイグレーション v2。

| ID | 是正内容 |
|---|---|
| CHK-00-02 | 監査で識別子・最終更新日を追加 |
| CHK-00-03 | 記載はある。第三者レビュー未実施・未承認であることを明記（承認は CHK-18-08） |
| CHK-00-07 | 命名規則を監査で追加 |
| CHK-01-06 | 監査で追加 |
| CHK-01-09 | 監査で独立節に |
| CHK-02-05 | 監査で追加 |
| CHK-02-07 | 監査で追加 |
| CHK-03-02 | 監査で機能一覧を追加 |
| CHK-03-03 | 監査で追加 |
| CHK-03-10 | 全要件に期待動作と検証方法。曖昧表現は除去（CHK-15-02） |
| CHK-03-11 | 監査で確認結果を記録 |
| CHK-04-01 | 監査で入力表を追加 |
| CHK-04-02 | 必須・既定値・範囲の列 |
| CHK-04-03 | 入力元の列 |
| CHK-04-06 | 記載を追加・明確化 |
| CHK-04-08 | 監査で命名規則を明記 |
| CHK-04-10 | 記載を追加・明確化 |
| CHK-04-11 | 監査で追加 |
| CHK-04-16 | 監査で役割の色以外の区別（形・記号）を実装。WCAG 評価は未実施 |
| CHK-05-04 | 監査で容量の実測値を追加 |
| CHK-05-05 | 監査で追加 |
| CHK-05-07 | 監査で pn backup を実装 |
| CHK-05-09 | 監査中の索引追加を v2 マイグレーションとして実施し移行を検証 |
| CHK-06-02 | 数式・定数（0.90）を監査で明記 |
| CHK-06-03 | 監査で追加 |
| CHK-06-04 | 監査でレイアウトのシードを固定 |
| CHK-06-06 | 監査で表を追加 |
| CHK-06-07 | 記載を追加・明確化 |
| CHK-06-08 | 監査で追加 |
| CHK-07-04 | 監査で追加 |
| CHK-07-06 | 監査で中断ジョブの検出を実装 |
| CHK-07-07 | 仕様は定義。同一 DB での同時ネットワーク構築はテストしていない（想定外と明記） |
| CHK-08-02 | メモリ使用量は未測定と明記 |
| CHK-08-10 | 監査で追加 |
| CHK-09-01 | 監査で数値目標化・測定。二次的増加を発見し修正（ADR-012）。ブラウザ描画は未測定 |
| CHK-09-02 | 20000 件は未測定 |
| CHK-09-08 | WCAG 評価は対象外（要確認事項に記載） |
| CHK-09-14 | 監査で優先度・検証方法の列を追加 |
| CHK-09-15 | 監査で追加 |
| CHK-10-01 | 監査で脅威表を追加 |
| CHK-10-07 | 監査で独立節に |
| CHK-10-09 | 監査で追加 |
| CHK-11-01 | 監査で重要度を追加 |
| CHK-11-06 | ファイル出力しない方針を明記 |
| CHK-12-02 | 監査で追加 |
| CHK-12-07 | 監査で追加 |
| CHK-12-08 | 監査で明記 |
| CHK-12-09 | 監査で追加 |
| CHK-12-10 | 監査で追加 |
| CHK-13-01 | 監査で OPERATIONS.md を作成 |
| CHK-13-02 | SemVer |
| CHK-13-03 | 記載を追加・明確化 |
| CHK-13-04 | 記載を追加・明確化 |
| CHK-13-05 | 記載を追加・明確化 |
| CHK-13-06 | 記載を追加・明確化 |
| CHK-13-07 | サポート対象は定義。保守終了時期は未決（利用者が決定） |
| CHK-13-08 | 運用責任は利用者。保守担当は未決 |
| CHK-13-09 | 第三者の条件は確認済み。本ソフトウェアのライセンスは未決 |
| CHK-14-02 | 方針は定義。本作業ではコミットしていない（利用者の指示がないため） |
| CHK-14-03 | 記載を追加・明確化 |
| CHK-14-04 | 記載を追加・明確化 |
| CHK-14-05 | 記載を追加・明確化 |
| CHK-14-06 | 記載を追加・明確化 |
| CHK-15-02 | 「適切に・十分に・高速に・なるべく・できるだけ・実用・など」を検索。要件文の 1 件（PN-DB-004）を具体化。残りは説明文・運用手順のみ |
| CHK-15-04 | 記載を追加・明確化 |
| CHK-16-01 | 監査で「要件・期待動作」列を追加し推奨フォーマットに一致 |

## モック検証のみの項目

CHK-04-13, CHK-04-14, CHK-04-15（ADS・Zotero 実機での確認は仕様書 §16 の要確認事項）

## 第 18 章 最終判定（個別評価）

| 観点 | 判定 | 説明 |
|---|---|---|
| 目的・スコープ | [x] | 満たす |
| 機能 | [x] | 満たす |
| 環境 | [x] | 満たす |
| 品質 | [x] | 具体化済み。移植性の検証は未了（CHK-09-06） |
| 検証 | [x] | 満たす |
| 未決事項 | [x] | 満たす |
| 追跡可能性 | [x] | 満たす |
| 承認 | [ ] | レビュー・承認は未完了。承認者は利用者であり、Claude は承認済みとしない。是正: 利用者がレビューし承認する |

判定の目安（原本）に照らすと: **作成開始可能**・**実装開始可能**の条件は満たす。**リリース判定可能**は、重要要件の検証結果・既知の制限・運用/復旧手順は確認できるが、承認が未了で、ライブ API・実機の検証結果がないため未達。

## 監査表（全項目）

### 0. 文書の管理

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-00-01 | 文書名、対象ソフトウェア名が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L7（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L8（0. 文書管理） | —（文書項目） | — |  |
| CHK-00-02 | 文書の識別子、バージョン、作成日、最終更新日が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L9（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L10（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L11（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L12（0. 文書管理） | —（文書項目） | — | 監査で識別子・最終更新日を追加（是正済み） |
| CHK-00-03 | 作成者、レビュー担当者、承認者（必要な場合）が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L13（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L14（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L15（0. 文書管理） | —（文書項目） | — | 記載はある。第三者レビュー未実施・未承認であることを明記（承認は CHK-18-08）（是正済み） |
| CHK-00-04 | 文書の状態（草案、レビュー中、承認済み等）が分かる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L16（0. 文書管理） | —（文書項目） | — | 草案（利用者レビュー待ち） |
| CHK-00-05 | 変更履歴と変更理由が記録されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L18（0.1 変更履歴）<br>`CHANGELOG.md` L3（[0.1.1] - 2026-11-12 — 仕様書チェックリスト監査に基づく是…） | —（文書項目） | — |  |
| CHK-00-06 | 関連文書、参考資料、外部規格への参照がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L27（0.2 関連文書・参考資料・外部規格）<br>`docs/EXTERNAL_SPECS.md` L6（1. NASA ADS API） | —（文書項目） | — |  |
| CHK-00-07 | 用語、略語、記号、命名規則が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L41（0.4 用語・略語・記号）<br>`docs/SYSTEM_SPECIFICATION.md` L59（0.5 命名規則） | —（文書項目） | — | 命名規則を監査で追加（是正済み） |
| CHK-00-08 | 未決事項、仮定、判断待ちの事項が区別されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L36（0.3 記述区分）<br>`docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項） | —（文書項目） | — |  |

### 1. 背景・目的・スコープ

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-01-01 | 開発の背景と解決したい課題が説明されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L74（1.1 背景と課題） | —（文書項目） | — |  |
| CHK-01-02 | ソフトウェアの目的と期待する成果が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L78（1.2 目的と期待する成果） | —（文書項目） | — |  |
| CHK-01-03 | 対象となる利用者・利用場面が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L83（1.3 対象利用者・利用場面） | —（文書項目） | — |  |
| CHK-01-04 | 対象範囲（実装するもの）が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L86（1.4 対象範囲（P0）） | —（文書項目） | — |  |
| CHK-01-05 | 対象外の機能・責任範囲が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L89（1.5 対象外の機能・責任範囲） | `src/paper_navigator/ui/streamlit_app.py` | — | UI サイドバーに P1 未実装を表示 |
| CHK-01-06 | 利用者の前提知識や権限が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L93（1.6 利用者の前提知識と権限） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-01-07 | 成功条件・受入れの考え方が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L98（1.7 成功条件・受入れの考え方）<br>`docs/TEST_PLAN.md` L82（6. 合格基準（指示書 §9.2）の判定） | —（文書項目） | — |  |
| CHK-01-08 | 前提条件、依存条件、既知の制約が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L102（1.8 前提条件・依存条件・既知の制約） | —（文書項目） | — |  |
| CHK-01-09 | 関連する業務・研究・運用プロセスとの関係が説明されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L107（1.9 関連する研究プロセスとの関係） | —（文書項目） | — | 監査で独立節に（是正済み） |

### 2. 利用者・ユースケース・業務フロー

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-02-01 | 利用者の種類・役割が整理されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L113（2.1 利用者の種類・役割） | —（文書項目） | — | 単一の役割（研究者＝所有者） |
| CHK-02-02 | 主要なユースケースまたは利用シナリオが列挙されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L116（2.2 ユースケース） | —（文書項目） | — | UC-01〜05 |
| CHK-02-03 | 各シナリオの開始条件、入力、処理、結果が分かる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L118（2.2 ユースケース） | —（文書項目） | — |  |
| CHK-02-04 | 正常系だけでなく、異常系・境界条件のシナリオが検討されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L118（2.2 ユースケース） | —（文書項目） | `test_network::test_partial_failure_keeps_fetched_part` PASS<br>`test_normalize::test_detect_input_rejects` PASS<br>`test_network::test_seed_not_found` PASS<br>`test_network::test_zero_references` PASS |  |
| CHK-02-05 | 利用者による操作とシステムの自動処理が区別されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L126（2.3 利用者による操作とシステムの自動処理） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-02-06 | 権限や利用者ごとの機能差がある場合、その条件が定義されている | **[N/A]** | `docs/SYSTEM_SPECIFICATION.md` L114（2.1 利用者の種類・役割） | —（文書項目） | — | 単一利用者・ローカル専用で権限差がない。複数利用者化する場合はロール定義が必要（仕様書 §17 提案） |
| CHK-02-07 | ユースケース間の前後関係・依存関係が整理されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L137（2.4 ユースケース間の前後関係・依存関係） | —（文書項目） | — | 監査で追加（是正済み） |

### 3. 機能要件

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-03-01 | 機能が一意に識別できるIDまたは名称を持つ | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 要件 ID の重複は生成スクリプトが検出して停止 |
| CHK-03-02 | 各機能の目的と責務が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L151（機能一覧（目的・責務・起動条件・前提条件）） | —（文書項目） | — | 監査で機能一覧を追加（是正済み） |
| CHK-03-03 | 各機能の起動条件・前提条件が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L153（機能一覧（目的・責務・起動条件・前提条件）） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-03-04 | 入力、処理、出力が具体的に定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L165（3.1 F-SEARCH 論文検索（PN-ADS-001〜009））<br>`docs/SYSTEM_SPECIFICATION.md` L225（4.1 入力）<br>`docs/SYSTEM_SPECIFICATION.md` L252（4.2 出力） | —（文書項目） | — |  |
| CHK-03-05 | 処理手順、条件分岐、繰り返し、終了条件が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L177（3.2 F-NETWORK 引用ネットワーク構築（PN-GRAPH-001〜00…）<br>`docs/SYSTEM_SPECIFICATION.md` L184（3.2 F-NETWORK 引用ネットワーク構築（PN-GRAPH-001〜00…） | `graph/builder.py:96` build_network | `test_network::test_shared_reference_and_cycle_kept_as_digraph` PASS |  |
| CHK-03-06 | 期待される結果と成功条件が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L185（3.2 F-NETWORK 引用ネットワーク構築（PN-GRAPH-001〜00…）<br>`docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — |  |
| CHK-03-07 | 無効な入力や処理失敗時の動作が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L227（4.1 入力）<br>`docs/SYSTEM_SPECIFICATION.md` L537（11.1 エラー分類・重要度・動作） | —（文書項目） | `test_network::test_param_validation` PASS<br>`test_ads_client::test_invalid_response_shapes` PASS |  |
| CHK-03-08 | 機能間の依存関係と実行順序が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L137（2.4 ユースケース間の前後関係・依存関係）<br>`docs/SYSTEM_SPECIFICATION.md` L433（7.3 状態管理・状態遷移・初期化・終了） | —（文書項目） | — |  |
| CHK-03-09 | 必須機能と任意機能、初期リリース対象と将来候補が区別されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L146（3.0 優先度・状態の区分）<br>`docs/SYSTEM_SPECIFICATION.md` L89（1.5 対象外の機能・責任範囲） | —（文書項目） | — |  |
| CHK-03-10 | 各要件が曖昧でなく、検証可能な表現になっている | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 全要件に期待動作と検証方法。曖昧表現は除去（CHK-15-02）（是正済み） |
| CHK-03-11 | 重複・矛盾・相互に成立しない要件がないか確認されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L215（3.8 要件の重複・矛盾の確認結果） | —（文書項目） | — | 監査で確認結果を記録（是正済み） |

### 4. 入力・出力・インターフェース

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-04-01 | 入力項目、データ型、形式、単位が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L227（4.1 入力） | —（文書項目） | — | 監査で入力表を追加（是正済み） |
| CHK-04-02 | 必須・任意、既定値、許容範囲、桁数・サイズ制限が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L227（4.1 入力） | —（文書項目） | `test_config_security::test_defaults_are_small_and_configurable` PASS | 必須・既定値・範囲の列（是正済み） |
| CHK-04-03 | 入力元（利用者、ファイル、API、センサー等）が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L227（4.1 入力） | —（文書項目） | — | 入力元の列（是正済み） |
| CHK-04-04 | 欠損値、空値、異常値、重複値、形式不正への対応が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L250（4.1 入力） | `repository.py:124` _apply_record | `test_db_repository::test_none_does_not_erase_known_values` PASS<br>`test_ads_client::test_mapping_bad_values_flagged` PASS |  |
| CHK-04-05 | 入力値の検証・正規化方法が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L351（6.1 正規化） | `normalize.py:19` normalize_doi<br>`ads/query.py:40` detect_input | `test_normalize::test_normalize_doi` PASS<br>`test_normalize::test_detect_input_rejects` PASS |  |
| CHK-04-06 | 出力項目、データ型、形式、単位、精度が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L254（4.2 出力）<br>`docs/SYSTEM_SPECIFICATION.md` L266（4.2 出力） | —（文書項目） | — | （是正済み） |
| CHK-04-07 | 出力先（画面、ファイル、DB、API等）が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L254（4.2 出力） | `graph/view.py:344` export_all | `test_network::test_filter_and_exports` PASS |  |
| CHK-04-08 | 出力ファイルの命名規則・ディレクトリ構成が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L59（0.5 命名規則）<br>`docs/SYSTEM_SPECIFICATION.md` L254（4.2 出力） | —（文書項目） | — | 監査で命名規則を明記（是正済み） |
| CHK-04-09 | 成功・失敗・部分成功を利用者が判別できる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L267（4.2 出力） | `src/paper_navigator/ui/streamlit_app.py` | `test_ui_cli_acceptance::test_ui_shows_partial_status` PASS |  |
| CHK-04-10 | 出力が存在しない場合や一部欠落する場合の動作が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L268（4.2 出力） | —（文書項目） | `test_network::test_zero_references` PASS | （是正済み） |
| CHK-04-11 | 出力の互換性・バージョン管理が必要な場合、その方針がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L269（4.2 出力）<br>`docs/OPERATIONS.md` L14（2. リリース物・版番号） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-04-12 | UI、CLI、API、通信プロトコル等の対象インターフェースが列挙されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L273（4.3.1 インターフェース一覧と外部 API 仕様） | —（文書項目） | — |  |
| CHK-04-13 | API等では、エンドポイント、引数、戻り値、ステータス、認証方式が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L275（4.3.1 インターフェース一覧と外部 API 仕様）<br>`docs/EXTERNAL_SPECS.md` L6（1. NASA ADS API） | —（文書項目） | `test_ads_client::test_http_error_classification` PASS | 外部 API の仕様。検証はモックのみ（モック検証） |
| CHK-04-14 | タイムアウト、再試行、レート制限、通信失敗時の動作が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L275（4.3.1 インターフェース一覧と外部 API 仕様）<br>`docs/SYSTEM_SPECIFICATION.md` L537（11.1 エラー分類・重要度・動作） | `ads/client.py:132` ADSClient._get | `test_ads_client::test_rate_limit_retries_then_fails` PASS<br>`test_ads_client::test_timeout_and_network_errors` PASS | 検証はモックのみ（モック検証） |
| CHK-04-15 | 外部システムとの契約・互換性条件が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L283（4.3.1 インターフェース一覧と外部 API 仕様） | —（文書項目） | `test_zotero::test_status_versions` PASS | 版条件は一次資料で確認。実機での確認は要確認事項（モック検証） |
| CHK-04-16 | UIがある場合、画面・操作・表示状態・入力制約・アクセシビリティが必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L285（4.3.2 UI 画面・操作・表示状態・入力制約・アクセシビリティ） | `graph/view.py:28` ROLE_STYLE | `test_network::test_roles_distinguishable_without_colour_and_layout_seeded` PASS<br>`test_ui_cli_acceptance::test_ui_end_to_end_search_graph_detail_bib` PASS | 監査で役割の色以外の区別（形・記号）を実装。WCAG 評価は未実施（是正済み） |

### 5. データ仕様・データ管理

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-05-01 | 扱うデータの種類、構造、スキーマが定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L299（5.1 データの種類・構造・スキーマ）<br>`docs/ARCHITECTURE.md` L70（4. DB 設計（スキーマ v2）） | `db.py:25` SCHEMA_V1 | `test_db_repository::test_migrations_create_schema_matching_orm` PASS |  |
| CHK-05-02 | データ形式、文字コード、日時・タイムゾーン、単位等が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L302（5.2 形式・文字コード・日時・単位） | `models.py:18` utcnow_iso | — |  |
| CHK-05-03 | データの出典、取得方法、所有者、利用条件が必要に応じて記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L305（5.3 出典・取得方法・所有者・利用条件） | —（文書項目） | — |  |
| CHK-05-04 | データの保存場所、保存期間、容量上限が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L314（5.4 保存場所・保存期間・容量） | —（文書項目） | scripts/benchmark.py（docs/verification/benchmark.md） | 監査で容量の実測値を追加（是正済み） |
| CHK-05-05 | 作成・読込・更新・削除のルールが定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L319（5.5 作成・読込・更新・削除のルール） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-05-06 | データの整合性、重複排除、検証方法が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L331（5.6 整合性・重複排除・検証） | `repository.py:207` upsert_paper | `test_db_repository::test_dedup_by_doi_bibcode_and_arxiv` PASS<br>`test_db_repository::test_identifier_conflict_recorded_not_merged` PASS |  |
| CHK-05-07 | バックアップ、復元、移行、削除の方針が必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L334（5.7 バックアップ・復元・移行・削除）<br>`docs/OPERATIONS.md` L20（3. 設定・データの移行、バックアップ・復元、削除） | `db.py:242` Database.backup | `test_db_repository::test_backup_is_consistent_copy` PASS<br>`test_ui_cli_acceptance::test_cli_backup` PASS | 監査で pn backup を実装（是正済み） |
| CHK-05-08 | 機密情報・個人情報・認証情報の扱いが定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L340（5.8 機密情報・個人情報・認証情報） | `config.py:17` Secret | `test_config_security::test_secret_masked_in_repr` PASS |  |
| CHK-05-09 | スキーマ変更や旧データとの互換性の方針がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L343（5.9 スキーマ変更と互換性） | `db.py:200` migrate | `test_db_repository::test_upgrade_from_v1_database` PASS<br>`test_db_repository::test_newer_schema_refused` PASS | 監査中の索引追加を v2 マイグレーションとして実施し移行を検証（是正済み） |
| CHK-05-10 | テスト用・サンプルデータの入手方法と利用制約が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L346（5.10 テスト用・サンプルデータ） | —（文書項目） | — |  |

### 6. アルゴリズム・計算・ビジネスルール

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-06-01 | 重要な処理ロジックと判断ルールが説明されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L357（6.2 重複候補の判定）<br>`docs/SYSTEM_SPECIFICATION.md` L364（6.4 Zotero との不一致判定）<br>`docs/SYSTEM_SPECIFICATION.md` L374（6.5 BibTeX 検証規則） | `repository.py:180` _detect_candidates<br>`zotero/sync.py:40` compare_fields | — |  |
| CHK-06-02 | 数式、単位、記号、変数、定数の意味が定義されている（該当する場合） | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L358（6.2 重複候補の判定） | `normalize.py:72` title_similarity | `test_normalize::test_title_normalization_and_similarity` PASS | 数式・定数（0.90）を監査で明記（是正済み） |
| CHK-06-03 | 丸め、数値精度、許容誤差、オーバーフロー等の扱いが定義されている（該当する場合） | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L379（6.6 数値精度・丸め） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-06-04 | 乱数を使う場合、シードや再現性の方針が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L382（6.7 乱数と再現性） | `graph/view.py:243` _TEMPLATE | `test_network::test_roles_distinguishable_without_colour_and_layout_seeded` PASS | 監査でレイアウトのシードを固定（是正済み） |
| CHK-06-05 | 外部モデル・ライブラリ・サービスを利用する場合、名称、バージョン、設定、制約が記載されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L385（6.8 外部ライブラリ・サービス）<br>`docs/EXTERNAL_SPECS.md` L57（5. 採用ライブラリ（uv.lock で固定）） | —（文書項目） | — |  |
| CHK-06-06 | 結果に影響するパラメータ、既定値、調整範囲が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L388（6.9 結果に影響するパラメータ） | `graph/builder.py:37` NetworkParams | `test_network::test_param_validation` PASS | 監査で表を追加（是正済み） |
| CHK-06-07 | 重要な判断・計算結果を検証する方法や参照値がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L400（6.10 検証方法・参照値） | —（文書項目） | `test_network::test_edge_direction_references_and_citations` PASS | （是正済み） |
| CHK-06-08 | アルゴリズムの適用限界や想定外入力が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L403（6.11 適用限界・想定外入力） | —（文書項目） | — | 監査で追加（是正済み） |

### 7. システム構成・ソフトウェア設計

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-07-01 | 全体構成図または構成の説明がある | **[x]** | `docs/ARCHITECTURE.md` L3（1. 構成図） | —（文書項目） | — |  |
| CHK-07-02 | 主なモジュール・コンポーネントと責務が定義されている | **[x]** | `docs/ARCHITECTURE.md` L42（2. モジュール責務） | —（文書項目） | — |  |
| CHK-07-03 | モジュール間の依存関係、データの流れが分かる | **[x]** | `docs/ARCHITECTURE.md` L62（3. データフロー）<br>`docs/ARCHITECTURE.md` L44（2. モジュール責務） | —（文書項目） | — |  |
| CHK-07-04 | 公開インターフェースと内部実装の境界が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L415（7.2 公開インターフェースと内部実装の境界） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-07-05 | 主要なクラス、関数、サービス、プロセス等の設計が必要に応じて記載されている | **[x]** | `docs/ARCHITECTURE.md` L42（2. モジュール責務）<br>`docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 主要関数とその行番号はトレーサビリティ表 |
| CHK-07-06 | 状態管理、状態遷移、初期化、終了処理が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L420（7.3 状態管理・状態遷移・初期化・終了） | `repository.py:333` mark_stale_jobs | `test_db_repository::test_stale_running_jobs_marked_interrupted` PASS | 監査で中断ジョブの検出を実装（是正済み） |
| CHK-07-07 | 並列処理、非同期処理、競合、排他制御がある場合、その仕様がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L436（7.4 並行処理・競合・排他） | `db.py:173` _set_sqlite_pragmas | `test_db_repository::test_edges_unique_and_directed` PASS | 仕様は定義。同一 DB での同時ネットワーク構築はテストしていない（想定外と明記）（是正済み） |
| CHK-07-08 | 拡張・差し替え・設定変更が想定される箇所が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L441（7.5 拡張・差し替え・設定変更の箇所）<br>`docs/ARCHITECTURE.md` L114（6. P1 拡張ポイント） | —（文書項目） | — |  |
| CHK-07-09 | 設計上の重要な判断と、その理由・代替案が必要に応じて記録されている | **[x]** | `docs/DECISIONS.md` L5（ADR-001 新規リポジトリとして実装） | —（文書項目） | — | ADR-001〜012（理由・代替案） |

### 8. 実行環境・導入・設定

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-08-01 | 対応OS・バージョンが明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L451（8. 実行環境・導入・設定） | —（文書項目） | — | Linux のみ検証、macOS・Windows は未検証と明記（CHK-09-06） |
| CHK-08-02 | ハードウェア要件（CPU、メモリ、GPU、ストレージ等）が必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L452（8. 実行環境・導入・設定） | —（文書項目） | — | メモリ使用量は未測定と明記（是正済み） |
| CHK-08-03 | 言語・ランタイム・コンパイラ等のバージョンが明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L453（8. 実行環境・導入・設定） | —（文書項目） | — |  |
| CHK-08-04 | 外部ライブラリ、パッケージ、サービスとバージョン・取得方法が列挙されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L454（8. 実行環境・導入・設定）<br>`docs/EXTERNAL_SPECS.md` L57（5. 採用ライブラリ（uv.lock で固定）） | —（文書項目） | — | uv.lock で固定 |
| CHK-08-05 | 環境変数、設定ファイル、起動引数の仕様が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L456（8. 実行環境・導入・設定）<br>`.env.example` L4（NASA ADS API token (https://ui.adsabs.ha…） | `config.py:117` load_settings | `test_config_security::test_dotenv_parsing_and_env_precedence` PASS |  |
| CHK-08-06 | インストール、ビルド、初期設定の手順がある | **[x]** | `README.md` L42（セットアップ） | —（文書項目） | クリーン環境で README 手順を実行（TEST_PLAN §5） |  |
| CHK-08-07 | 起動、停止、通常実行、終了の手順がある | **[x]** | `README.md` L55（起動・停止）<br>`docs/OPERATIONS.md` L28（4. 定常運用） | `cli.py:330` cmd_ui | pn ui の起動・ヘルスチェック・停止・再起動を確認（TEST_PLAN §5） |  |
| CHK-08-08 | 必要な権限、ネットワーク、外部サービス、ライセンス条件が明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L460（8. 実行環境・導入・設定）<br>`docs/SYSTEM_SPECIFICATION.md` L461（8. 実行環境・導入・設定） | —（文書項目） | — |  |
| CHK-08-09 | クリーンな環境からセットアップ・実行できることを確認する方法がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L462（8. 実行環境・導入・設定）<br>`docs/TEST_PLAN.md` L110（9. 配布物の確認） | —（文書項目） | — |  |
| CHK-08-10 | 開発環境と本番・利用環境の差異が必要に応じて明記されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L463（8. 実行環境・導入・設定） | —（文書項目） | — | 監査で追加（是正済み） |

### 9. 非機能要件・品質特性

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-09-01 | **性能**：応答時間、処理時間、スループット、同時利用数等 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L471（9. 非機能要件・品質特性） | `repository.py:180` _detect_candidates | scripts/benchmark.py: 300 論文 1.84 秒＋0.08 秒 | 監査で数値目標化・測定。二次的増加を発見し修正（ADR-012）。ブラウザ描画は未測定（是正済み） |
| CHK-09-02 | **容量・拡張性**：データ量、ユーザー数、将来の拡張条件 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L472（9. 非機能要件・品質特性） | —（文書項目） | scripts/benchmark.py: 5000 論文 33.84 秒 | 20000 件は未測定（是正済み） |
| CHK-09-03 | **信頼性**：失敗率、耐障害性、データ損失防止 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L473（9. 非機能要件・品質特性） | `db.py:260` Database.session | `test_db_repository::test_rollback_on_error_leaves_db_unchanged` PASS<br>`test_network::test_partial_failure_keeps_fetched_part` PASS |  |
| CHK-09-04 | **可用性**：稼働時間、停止許容時間、復旧目標（必要な場合） | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L474（9. 非機能要件・品質特性） | —（文書項目） | `test_ui_cli_acceptance::test_ui_without_token_shows_config_error_and_does_not_crash` PASS | 常時稼働は要求しないことを要件として明記 |
| CHK-09-05 | **保守性**：診断容易性、ログ、コード構造、更新容易性 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L475（9. 非機能要件・品質特性） | —（文書項目） | ruff・mypy エラー 0（TEST_PLAN §5） |  |
| CHK-09-06 | **移植性・互換性**：対応環境、旧版・外部システムとの互換性 | **[ ]** | `docs/SYSTEM_SPECIFICATION.md` L476（9. 非機能要件・品質特性） | —（文書項目） | `test_db_repository::test_upgrade_from_v1_database` PASS | 互換性（旧スキーマ移行）は検証済みだが、移植性（macOS・Windows）は未検証。是正: 利用者環境で `uv run pytest` を実行するか、対応 OS を Linux に限定する |
| CHK-09-07 | **ユーザビリティ**：学習容易性、操作性、エラー表示 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L477（9. 非機能要件・品質特性） | `errors.py:30` USER_MESSAGES | `test_ui_cli_acceptance::test_ui_shows_partial_status` PASS |  |
| CHK-09-08 | **アクセシビリティ**：必要な利用者に対する操作・表示の配慮 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L478（9. 非機能要件・品質特性） | `graph/view.py:28` ROLE_STYLE | `test_network::test_roles_distinguishable_without_colour_and_layout_seeded` PASS | WCAG 評価は対象外（要確認事項に記載）（是正済み） |
| CHK-09-09 | **安全性**：危険な操作、誤操作、異常動作への対策（該当する場合） | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L479（9. 非機能要件・品質特性） | `zotero/client.py:308` ZoteroLocalClient.create_item | `test_bibliography::test_unicode_preserved_file_not_modified` PASS<br>`test_zotero::test_write_refused_on_old_zotero_without_posting` PASS |  |
| CHK-09-10 | **セキュリティ**：認証、認可、暗号化、脆弱性対策等 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L480（9. 非機能要件・品質特性）<br>`docs/SYSTEM_SPECIFICATION.md` L492（10. セキュリティ・プライバシー） | —（文書項目） | `test_config_security::test_no_secret_in_logs_during_retries` PASS<br>`test_network::test_html_escapes_untrusted_metadata` PASS |  |
| CHK-09-11 | **プライバシー**：個人情報の最小化、目的制限、保護、削除 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L481（9. 非機能要件・品質特性）<br>`docs/SYSTEM_SPECIFICATION.md` L524（10.8 個人情報） | `ads/client.py:188` ADSClient.search_page | — | 検証はコードレビュー（外部送信は ADS への検索クエリのみ） |
| CHK-09-12 | **相互運用性**：他システム・データ形式との連携 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L482（9. 非機能要件・品質特性） | `graph/view.py:190` write_graphml | `test_network::test_filter_and_exports` PASS |  |
| CHK-09-13 | **再現性**：同一条件での結果再現が必要な場合の条件 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L483（9. 非機能要件・品質特性） | `graph/view.py:61` load_job_graph | `test_network::test_reproducible_regeneration` PASS |  |
| CHK-09-14 | 各品質要件に優先度と検証方法がある | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L469（9. 非機能要件・品質特性） | —（文書項目） | — | 監査で優先度・検証方法の列を追加（是正済み） |
| CHK-09-15 | 要件同士のトレードオフが必要に応じて説明されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L485（9.1 トレードオフ） | —（文書項目） | — | 監査で追加（是正済み） |

### 10. セキュリティ・プライバシー（該当する場合）

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-10-01 | 保護対象となるデータ・資産と脅威が整理されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L494（10.1 保護対象と脅威） | —（文書項目） | — | 監査で脅威表を追加（是正済み） |
| CHK-10-02 | 認証・認可・ロール・権限の仕様が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L505（10.2 認証・認可・ロール） | `zotero/client.py:279` ZoteroLocalClient.request_authorization | `test_zotero::test_authorize_flow` PASS | アプリ内ロールは不要と理由付きで定義、外部認証を定義 |
| CHK-10-03 | 秘密情報、鍵、トークン、パスワードの保存・受け渡し方法が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L508（10.3 秘密情報の保存・受け渡し） | `app.py:48` write_key_file | `test_config_security::test_key_file_written_owner_only` PASS<br>`test_ads_client::test_auth_header_sent_and_token_not_in_repr` PASS |  |
| CHK-10-04 | 通信時・保存時の保護要件が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L511（10.4 通信時・保存時の保護） | —（文書項目） | — | 保存時は暗号化しない方針を明記（OS のディスク暗号化を推奨） |
| CHK-10-05 | 入力検証、出力処理、依存関係の脆弱性対策が検討されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L514（10.5 入力検証・出力処理・依存関係） | `graph/view.py:231` _safe_json | `test_network::test_html_escapes_untrusted_metadata` PASS<br>`test_config_security::test_invalid_config_is_config_error` PASS<br>pip-audit: 既知脆弱性なし |  |
| CHK-10-06 | 監査ログの対象と、記録してはいけない情報が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L517（10.6 監査ログと記録してはいけない情報） | `logging_utils.py:23` RedactingFilter | `test_config_security::test_redaction_patterns` PASS |  |
| CHK-10-07 | セッション、アクセス拒否、アカウント・権限変更の動作が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L521（10.7 セッション・アクセス拒否・権限変更） | `config.py:109` is_loopback_url | `test_config_security::test_streamlit_config_binds_loopback` PASS<br>外部インターフェースからの UI 接続が拒否されることを確認 | 監査で独立節に（是正済み） |
| CHK-10-08 | 個人情報の収集目的、利用範囲、保持期間、削除方法が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L524（10.8 個人情報） | —（文書項目） | — |  |
| CHK-10-09 | セキュリティ事故の検知・対応方法が必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L529（10.9 セキュリティ事故の検知・対応） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-10-10 | 適用される法令、規格、組織ポリシーを確認している | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L532（10.10 適用される法令・規約・ポリシー） | —（文書項目） | — | 所属組織固有のポリシーは利用者確認が必要（仮定として明記） |

### 11. エラー処理・ログ・監視

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-11-01 | エラーの種類・分類・重要度が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L537（11.1 エラー分類・重要度・動作） | `errors.py:12` ErrorCode | — | 監査で重要度を追加（是正済み） |
| CHK-11-02 | エラーコードや識別可能なメッセージが必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L539（11.1 エラー分類・重要度・動作） | `errors.py:30` USER_MESSAGES | — |  |
| CHK-11-03 | 各エラー発生時の継続・中断・再試行・復旧動作が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L539（11.1 エラー分類・重要度・動作） | `graph/builder.py:96` build_network | `test_network::test_auth_error_aborts` PASS<br>`test_ads_client::test_transient_5xx_recovers` PASS |  |
| CHK-11-04 | 利用者向けメッセージと開発者向け診断情報が区別されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L559（11.2 利用者向けメッセージと開発者向け診断） | `errors.py:49` PNError | `test_ui_cli_acceptance::test_cli_setup_from_empty_db_and_restart` PASS |  |
| CHK-11-05 | ログに記録するイベント、レベル、形式、出力先が定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L562（11.3 ログ） | `logging_utils.py:57` setup_logging | — |  |
| CHK-11-06 | ログのローテーション、保存期間、容量制御が必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L566（11.3 ログ） | —（文書項目） | — | ファイル出力しない方針を明記（是正済み） |
| CHK-11-07 | 機密情報・個人情報がログに不用意に出力されない | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L567（11.3 ログ） | `logging_utils.py:23` RedactingFilter | `test_config_security::test_no_secret_in_logs_during_retries` PASS |  |
| CHK-11-08 | 進捗表示、ヘルスチェック、メトリクス、アラートが必要に応じて定義されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L569（11.4 進捗・ヘルスチェック・メトリクス） | `src/paper_navigator/ui/streamlit_app.py` | /_stcore/health = ok を確認 | メトリクス・アラートは不要と理由付き |
| CHK-11-09 | 障害の再現・切り分けに必要な情報が取得できる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L572（11.5 障害の再現・切り分け） | `services.py:152` _finish | — |  |

### 12. テスト・検証・受入れ

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-12-01 | 各要件に対応する検証方法が定義されている | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 58 要件すべてに検証方法 |
| CHK-12-02 | テスト対象範囲と対象外範囲が明確である | **[x]** | `docs/TEST_PLAN.md` L15（1.1 対象範囲と対象外） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-12-03 | 単体・結合・システム・受入れテストの必要性が検討されている | **[x]** | `docs/TEST_PLAN.md` L5（1. テスト分類） | —（文書項目） | — |  |
| CHK-12-04 | 正常系、異常系、境界値、極端な入力のテストがある | **[x]** | `docs/TEST_PLAN.md` L29（4. 観点と期待結果（合否基準）） | —（文書項目） | `test_normalize::test_detect_input_rejects` PASS<br>`test_network::test_max_papers_truncation_recorded` PASS | 極端な入力（501 文字、5000 論文）を含む |
| CHK-12-05 | テスト環境・依存条件・テストデータが定義されている | **[x]** | `docs/TEST_PLAN.md` L20（2. テスト環境）<br>`docs/TEST_PLAN.md` L24（3. テストデータ） | —（文書項目） | — |  |
| CHK-12-06 | 期待結果と合否判定基準が具体的である | **[x]** | `docs/TEST_PLAN.md` L31（4. 観点と期待結果（合否基準）） | —（文書項目） | — |  |
| CHK-12-07 | 性能、セキュリティ、互換性等の非機能要件を検証する方法がある | **[x]** | `docs/TEST_PLAN.md` L49（4.1 非機能要件の検証方法） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-12-08 | 乱数・外部サービス等で結果が変動する場合、判定方法が定義されている | **[x]** | `docs/TEST_PLAN.md` L52（4.2 外部サービスで結果が変動する場合の判定） | —（文書項目） | — | 監査で明記（是正済み） |
| CHK-12-09 | 不具合の重大度、修正後の再テスト、回帰テストの方針がある | **[x]** | `docs/TEST_PLAN.md` L101（8. 不具合の重大度・再テスト・回帰テスト） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-12-10 | リリース・受入れの判定条件が明記されている | **[x]** | `docs/TEST_PLAN.md` L97（7. リリース・受入れの判定条件） | —（文書項目） | — | 監査で追加（是正済み） |
| CHK-12-11 | 要件とテストケースの対応関係を追跡できる | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 生成スクリプトで参照切れを検出 |

### 13. 運用・保守・リリース

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-13-01 | 配布・インストール・更新・アンインストール方法が定義されている | **[x]** | `docs/OPERATIONS.md` L5（1. 配布・インストール・更新・アンインストール） | —（文書項目） | — | 監査で OPERATIONS.md を作成（是正済み） |
| CHK-13-02 | リリース物、成果物、バージョン付与規則が明確である | **[x]** | `docs/OPERATIONS.md` L14（2. リリース物・版番号） | —（文書項目） | — | SemVer（是正済み） |
| CHK-13-03 | 設定・データの移行手順が必要に応じて定義されている | **[x]** | `docs/OPERATIONS.md` L20（3. 設定・データの移行、バックアップ・復元、削除） | `db.py:200` migrate | `test_db_repository::test_upgrade_from_v1_database` PASS | （是正済み） |
| CHK-13-04 | バックアップ・復元・障害復旧方法が必要に応じて定義されている | **[x]** | `docs/OPERATIONS.md` L25（3. 設定・データの移行、バックアップ・復元、削除） | `db.py:242` Database.backup | `test_db_repository::test_backup_is_consistent_copy` PASS | （是正済み） |
| CHK-13-05 | 定常運用、定期処理、監視の手順がある | **[x]** | `docs/OPERATIONS.md` L28（4. 定常運用） | —（文書項目） | — | （是正済み） |
| CHK-13-06 | 既知の制限、既知の不具合、回避策が記録されている | **[x]** | `docs/OPERATIONS.md` L43（6. 既知の制限・既知の不具合・回避策） | —（文書項目） | — | （是正済み） |
| CHK-13-07 | サポート対象バージョンと保守終了条件が必要に応じて定義されている | **[x]** | `docs/OPERATIONS.md` L55（7. サポート対象・保守終了） | —（文書項目） | — | サポート対象は定義。保守終了時期は未決（利用者が決定）（是正済み） |
| CHK-13-08 | 問い合わせ先、担当者、運用責任が必要に応じて明記されている | **[x]** | `docs/OPERATIONS.md` L38（5. 問い合わせ・責任） | —（文書項目） | — | 運用責任は利用者。保守担当は未決（是正済み） |
| CHK-13-09 | ライセンス、著作権、第三者コンポーネントの利用条件が確認されている | **[x]** | `docs/OPERATIONS.md` L59（8. ライセンス・著作権・第三者コンポーネント）<br>`docs/verification/licenses.md` L11（） | —（文書項目） | pip-licenses の結果を記録 | 第三者の条件は確認済み。本ソフトウェアのライセンスは未決（是正済み） |

### 14. 開発・変更管理

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-14-01 | 要件・設計・実装・テストの識別子と対応関係が管理されている | **[x]** | `docs/DEVELOPMENT.md` L3（1. 識別子と対応関係） | —（文書項目） | — |  |
| CHK-14-02 | ソースコードの管理方法とブランチ・レビュー方針が必要に応じて定義されている | **[x]** | `docs/DEVELOPMENT.md` L8（2. ソースコード管理） | —（文書項目） | `test_config_security::test_git_check_ignore` PASS | 方針は定義。本作業ではコミットしていない（利用者の指示がないため）（是正済み） |
| CHK-14-03 | コーディング規約、命名規則、フォーマット方針が必要に応じて定義されている | **[x]** | `docs/DEVELOPMENT.md` L13（3. コーディング規約・フォーマット）<br>`pyproject.toml` L41（） | —（文書項目） | ruff check / ruff format --check 合格 | （是正済み） |
| CHK-14-04 | 変更要求の評価・承認・記録方法がある | **[x]** | `docs/DEVELOPMENT.md` L28（4. 変更要求の評価・承認・記録） | —（文書項目） | — | （是正済み） |
| CHK-14-05 | 変更による影響範囲を特定できる | **[x]** | `docs/DEVELOPMENT.md` L34（5. 影響範囲の特定） | —（文書項目） | — | （是正済み） |
| CHK-14-06 | 仕様と実装が食い違った場合の扱いが定義されている | **[x]** | `docs/DEVELOPMENT.md` L37（6. 仕様と実装が食い違った場合） | —（文書項目） | — | （是正済み） |
| CHK-14-07 | 未実装事項、技術的負債、将来の改善案が区別して記録されている | **[x]** | `TODO.md` L3（P0 の未完了・未検証（優先））<br>`TODO.md` L11（技術的負債）<br>`TODO.md` L19（P1 以降（未実装・今回は意図的に対象外）） | —（文書項目） | — |  |

### 15. 仕様書全体の品質レビュー

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-15-01 | 各要件が明確・一意・矛盾なし・実現可能・検証可能である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L584（15. 自己レビュー結果（2026-11-12）） | —（文書項目） | — | 自己レビューのみ（第三者レビュー未実施）。検証可能性は全要件の検証方法で確認 |
| CHK-15-02 | 「適切に」「十分に」「高速に」など、基準のない曖昧な表現が残っていない | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L586（15. 自己レビュー結果（2026-11-12）） | —（文書項目） | — | 「適切に・十分に・高速に・なるべく・できるだけ・実用・など」を検索。要件文の 1 件（PN-DB-004）を具体化。残りは説明文・運用手順のみ（是正済み） |
| CHK-15-03 | 略語、用語、単位、日付・時刻、数値表記が文書内で一貫している | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L587（15. 自己レビュー結果（2026-11-12））<br>`docs/SYSTEM_SPECIFICATION.md` L41（0.4 用語・略語・記号） | —（文書項目） | — |  |
| CHK-15-04 | 機能間・モジュール間・外部システム間の矛盾がない | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L215（3.8 要件の重複・矛盾の確認結果） | —（文書項目） | — | （是正済み） |
| CHK-15-05 | 正常時だけでなく、異常時・境界条件・復旧時の動作が扱われている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L589（15. 自己レビュー結果（2026-11-12）） | —（文書項目） | — |  |
| CHK-15-06 | 重要な要件に優先度が付いている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L146（3.0 優先度・状態の区分） | —（文書項目） | — | 全要件に MUST/SHOULD/WON'T |
| CHK-15-07 | 各要件の根拠・出典・決定理由が必要に応じて追跡できる | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧））<br>`docs/DECISIONS.md` L5（ADR-001 新規リポジトリとして実装） | —（文書項目） | — |  |
| CHK-15-08 | 未確定事項が確定事項のように書かれていない | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L590（15. 自己レビュー結果（2026-11-12））<br>`docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項） | —（文書項目） | — | モックのみの検証は「検証済み（モック）／ライブ未検証」と表記 |
| CHK-15-09 | 仕様書の内容が対象利用者（開発者、テスター、運用者等）に理解可能である | **[ ]** | `docs/SYSTEM_SPECIFICATION.md` L591（15. 自己レビュー結果（2026-11-12）） | —（文書項目） | — | 対象利用者（利用者本人・他の開発者）による読解性の確認が未実施で、作成者自身では判定できない。是正: 利用者が README・仕様書を読んでレビューする |
| CHK-15-10 | 仕様書から実装・テスト・受入れ判断へ進めるだけの情報がある | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧））<br>`docs/TEST_PLAN.md` L97（7. リリース・受入れの判定条件） | —（文書項目） | — | 要件・期待動作・検証方法・受入れ条件がそろう |
| CHK-15-11 | 文書のレビュー結果、残課題、承認状態が明確である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L14（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L15（0. 文書管理）<br>`docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項） | —（文書項目） | — | 状態（レビュー未実施・未承認・残課題）を明記 |

### 16. 要件一覧表（推奨フォーマット）

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-16-01 | 要件一覧表が推奨フォーマット（ID・要件名・要件・期待動作・優先度・根拠・出典・検証方法・状態）で管理されている | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 監査で「要件・期待動作」列を追加し推奨フォーマットに一致（是正済み） |
| CHK-16-02 | IDは一意で、変更後も追跡できるようにする | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L63（0.5 命名規則） | —（文書項目） | — | 再利用禁止を命名規則に明記。重複はスクリプトが検出 |
| CHK-16-03 | 優先度はプロジェクト内で定義した区分を用いる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L146（3.0 優先度・状態の区分） | —（文書項目） | — | MUST/SHOULD/WON'T(P0) |
| CHK-16-04 | 状態は「未着手／検討中／確定／実装済み／検証済み」等の定義した区分を用いる | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L146（3.0 優先度・状態の区分） | —（文書項目） | — | 実装状態と検証状態を別列で管理 |
| CHK-16-05 | 要件の粒度は、原則として一つの検証可能な要求に一つのIDを割り当てる | **[ ]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 監査で PN-ADS-004 を 4 件に分割したが、PN-GRAPH-004（階層・論文数・リクエスト数・期間）、PN-BBT-001（複数の検証規則）、PN-UI-002 などは複数の検証項目を含む。是正: 次版で 1 検証 1 ID に分割 |

### 17. Claude Opus 5.5で仕様書を作成する際の確認事項

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-17-01 | 依頼内容にない要件、数値、機能、外部サービス、技術選定を事実として捏造していない | **[x]** | `docs/EXTERNAL_SPECS.md` L6（1. NASA ADS API）<br>`docs/SYSTEM_SPECIFICATION.md` L346（5.10 テスト用・サンプルデータ） | —（文書項目） | — | 外部仕様は URL・確認日付き。テストデータは合成と明記、ApJ 書誌は公式サンプルから転記。未検証の記述（.bst 名に関する推測）は発見して削除（CHANGELOG） |
| CHK-17-02 | 不明点を「要確認」「仮定」「提案」に分け、確定事項と混同していない | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L36（0.3 記述区分）<br>`docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項） | —（文書項目） | — |  |
| CHK-17-03 | 入力資料・既存コード・関連文書が提供されている場合、それらを確認したうえで記述している | **[x]** | `docs/SURVEY.md` L10（添付資料） | —（文書項目） | — | 指示書・チェックリストを全文確認。既存コードは無し |
| CHK-17-04 | 仕様の根拠となる情報と、AIによる提案・推測が区別されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L36（0.3 記述区分）<br>`docs/SYSTEM_SPECIFICATION.md` L608（17. 提案（将来）） | —（文書項目） | — |  |
| CHK-17-05 | 不足情報があっても、作成可能な範囲の草案と未決事項一覧を提示している | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項） | —（文書項目） | — |  |
| CHK-17-06 | 仕様の内部矛盾、実現可能性、テスト可能性を自己レビューしている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L584（15. 自己レビュー結果（2026-11-12））<br>`docs/SYSTEM_SPECIFICATION.md` L215（3.8 要件の重複・矛盾の確認結果） | —（文書項目） | — |  |
| CHK-17-07 | 実装済みと断定する場合、コードや実行結果などの根拠がある | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — | 実装済みの記載は実装ファイル:行と JUnit 結果を自動で紐付け |
| CHK-17-08 | 外部情報や技術仕様の確認が必要な場合、信頼できる一次資料を優先している | **[x]** | `docs/EXTERNAL_SPECS.md` L8（1. NASA ADS API） | —（文書項目） | — | 公式ページ・公式リポジトリを優先 |
| CHK-17-09 | 最終出力がMarkdownとして読みやすく、見出し・表・コード表記が適切である | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L3（0. 文書管理） | —（文書項目） | — | 見出し・表・コード表記を使用 |

### 18. 最終判定

| Checklist ID | 元チェック項目 | 判定 | 仕様記載 | 実装根拠 | 検証根拠 | 備考・残課題 |
|---|---|---|---|---|---|---|
| CHK-18-01 | **目的・スコープ**：何を作るか、何を作らないかが明確 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L86（1.4 対象範囲（P0））<br>`docs/SYSTEM_SPECIFICATION.md` L89（1.5 対象外の機能・責任範囲） | —（文書項目） | — |  |
| CHK-18-02 | **機能**：主要機能、入力、出力、異常時の動作が明確 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L151（機能一覧（目的・責務・起動条件・前提条件））<br>`docs/SYSTEM_SPECIFICATION.md` L225（4.1 入力）<br>`docs/SYSTEM_SPECIFICATION.md` L537（11.1 エラー分類・重要度・動作） | —（文書項目） | — |  |
| CHK-18-03 | **環境**：必要環境、依存関係、導入・実行方法が明確 | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L447（8. 実行環境・導入・設定）<br>`README.md` L42（セットアップ） | —（文書項目） | — |  |
| CHK-18-04 | **品質**：必要な性能・安全性・信頼性等が具体化されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L465（9. 非機能要件・品質特性） | —（文書項目） | — | 具体化済み。移植性の検証は未了（CHK-09-06） |
| CHK-18-05 | **検証**：要件を満たしたか判定する方法が定義されている | **[x]** | `docs/TEST_PLAN.md` L29（4. 観点と期待結果（合否基準））<br>`docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — |  |
| CHK-18-06 | **未決事項**：未確定事項、仮定、リスク、対象外事項が明示されている | **[x]** | `docs/SYSTEM_SPECIFICATION.md` L593（16. 未決事項・仮定・要確認事項）<br>`TODO.md` L26（リスク） | —（文書項目） | — |  |
| CHK-18-07 | **追跡可能性**：要件とテスト・実装の対応を確認できる | **[x]** | `docs/TRACEABILITY_MATRIX.md` L9（トレーサビリティ・マトリクス（P0 要件一覧）） | —（文書項目） | — |  |
| CHK-18-08 | **承認**：必要なレビューと承認が完了している | **[ ]** | `docs/SYSTEM_SPECIFICATION.md` L15（0. 文書管理） | —（文書項目） | — | レビュー・承認は未完了。承認者は利用者であり、Claude は承認済みとしない。是正: 利用者がレビューし承認する |

