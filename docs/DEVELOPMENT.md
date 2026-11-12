# 開発・変更管理

## 1. 識別子と対応関係
- 要件 `PN-*`、ユースケース `UC-*`、設計判断 `ADR-*`、チェックリスト監査 `CHK-*`（命名規則は [仕様書](SYSTEM_SPECIFICATION.md) §0.5）。
- 要件 → 実装（ファイル:行）→ テスト（結果）の対応は `scripts/gen_traceability.py` が生成する [TRACEABILITY_MATRIX](TRACEABILITY_MATRIX.md)。実装シンボルは `ast` で、テストは JUnit 結果で解決し、存在しない参照があると生成が失敗する。
- チェックリスト監査は `scripts/gen_checklist_audit.py` が原本の全項目と判定データの対応を検査して生成する。

## 2. ソースコード管理
- Git、既定ブランチ `main`。変更は作業ブランチ（`feature/<内容>`、`fix/<内容>`）で行い、テストと静的解析が通った後に `main` へマージする。
- レビュー: 単独開発のため、マージ前のセルフレビュー（下記チェック）を必須とし、仕様・要件に影響する変更は利用者が確認する。
- コミットしてはいけないもの: `.env`、`data/`、`vendor/`、秘密情報（`.gitignore` とテスト `test_git_check_ignore` で確認）。

## 3. コーディング規約・フォーマット
- ruff（`pyproject.toml` の `[tool.ruff]`: 行長 100、E/F/W/I/B/UP/S/SIM 規則）と `ruff format`、mypy（`check_untyped_defs`）。
- 命名: 仕様書 §0.5。日本語の利用者向け文言は `errors.USER_MESSAGES` と UI に集約。
- 層の規則: UI/CLI は業務ロジックを持たず services 層を呼ぶ（[ARCHITECTURE](ARCHITECTURE.md) §2）。
- 外部データは信頼しない（HTML への埋め込みは `_safe_json` と `textContent`）。秘密値は `Secret` で扱う。

マージ前チェック:
```bash
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest -v --junitxml=docs/verification/junit.xml
uv run python scripts/gen_traceability.py
uv run python scripts/gen_checklist_audit.py
```

## 4. 変更要求の評価・承認・記録
1. 変更要求を TODO.md（または Issue）に記録し、影響する要件 ID を特定する。
2. 影響範囲（§5）を評価し、要件の追加・変更が必要なら仕様書と生成スクリプトの要件データを更新（ID は再利用しない）。
3. 仕様・外部仕様に関わる判断は ADR を追加。利用者の判断が必要なもの（スコープ、ライセンス、外部サービスの追加）は利用者の承認を得る。
4. 実装・テスト追加 → §3 のチェック → CHANGELOG に変更内容と理由を記録 → 版番号を更新（[OPERATIONS](OPERATIONS.md) §2）。

## 5. 影響範囲の特定
トレーサビリティ表で要件 → 実装シンボル → テストをたどる。モジュール依存は ARCHITECTURE §2 の表。DB 変更はマイグレーション（新版を追記）として扱い、移行テストを追加。エクスポート形式・CLI の変更は互換性（OPERATIONS §2）を確認。

## 6. 仕様と実装が食い違った場合
1. 外部の一次資料（EXTERNAL_SPECS）と照合し、どちらが正しいかを判断する。
2. 実装が誤り → 実装を修正し回帰テストを追加。仕様が誤り・古い → 仕様を修正し ADR に理由を記録。
3. 判断に利用者の意図が必要な場合は「未決」として仕様書 §16 に記載し、確定するまで現状を変更しない。
4. 例: 指示書の `aasjournal.bst` と AAS 一次資料の相違 → 一次資料を優先（ADR-007）。

## 7. 未実装事項・技術的負債・改善案の区別
[TODO.md](../TODO.md) で「P0 の未完了・未検証」「技術的負債」「P1 以降（未実装）」「リスク」を分けて記録。仕様書 §17 は将来の提案。
