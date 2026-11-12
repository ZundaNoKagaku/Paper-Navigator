# Zotero / Better BibTeX 導入・運用手順

出典は [EXTERNAL_SPECS.md](EXTERNAL_SPECS.md) §2–3（2026-11-12 確認）。実機 Zotero での動作は開発環境に Zotero が無いため**未検証**。

## 1. 対応バージョン

| 機能 | 必要なもの |
|---|---|
| 状態確認・コレクション読取・照合（`zotero-status/collections/sync`） | Zotero 7 以上（Local API） |
| Paper Navigator から Zotero へ追加（`zotero-add`） | **Zotero 10 以上**（Local API 書き込み） |
| `.bib` 自動エクスポート | Better BibTeX（BBT v9 系は Zotero 8 以上が必要） |

## 2. Zotero の Local API を有効にする
1. Zotero を起動 → 設定（macOS は「環境設定」）→「詳細」。
2. 「このコンピュータ上の他のアプリケーションとZoteroが通信することを許可」をオンにする。
3. 確認: `uv run pn zotero-status`
   - `unavailable` → Zotero が起動していない／ポート 23119 に接続できない
   - `local_api_disabled` → 手順2の設定がオフ
   - `read_only` → 読み取り可（Zotero 10 未満、書き込み不可）
   - `write_needs_authorization` → 書き込み可能だが未許可（手順3へ）
   - `read_write` → 読み書き可

Local API は認証なしで読み取れるため、ポート 23119 をネットワークに公開しないでください。
Paper Navigator は `ZOTERO_BASE_URL` にループバック以外を指定すると起動を拒否します。

## 3. 書き込みを許可する（Zotero 10 以上）
1. `uv run pn zotero-authorize` を実行すると Zotero に許可ダイアログが表示されます。
2. 「常に許可（Always Allow）」を選ぶとキーを継続利用できます（「許可」のみの場合は 1 回の書き込みで失効）。
3. キーは `data/zotero_local_api_key`（権限 600、Git 管理外）に保存され、画面・ログには表示しません。
4. 取り消し: Zotero 設定 →「詳細」→「Clear Write Authorizations」、および上記ファイルを削除。

追加: `uv run pn zotero-add <Bibcode|DOI|#id> --collection <コレクションキー>`
- 同じ DOI のアイテムが既にあれば追加しません（`status=exists`）。
- `unsupported` / `needs_authorization` / `failed` のときは追加されていません（成功扱いにしません）。
- Zotero 10 未満では、Zotero の「識別子で追加」（魔法の杖ボタン）に DOI を入力して追加してください。

## 4. Better BibTeX の自動エクスポート
1. Zotero に Better BibTeX をインストールし、Zotero を再起動。
2. 論文用のコレクション（例: `Thesis2026`）を作る。
3. コレクションを右クリック →「コレクションをエクスポート…」→ 形式 **Better BibTeX** → **Keep updated** にチェック → 保存先に原稿ディレクトリの `references.bib` を指定。
4. 以後、そのコレクションの変更で `.bib` が自動更新されます（**Zotero 起動中のみ**）。設定は BBT 設定の「Automatic export」タブで確認・削除できます。
5. `.bib` を手で編集しないでください（次の自動エクスポートで上書きされます）。修正は Zotero 側で行います。

## 5. 引用キーの安定性
- BBT v8.0.0 以降、引用キーは Zotero の引用キーフィールドに保存され常に固定されます（ピン留め操作は廃止）。キー式（例 `auth.lower + year`）は既存キーを変えずに新規アイテムへ適用されます。
- キーの例: `peter2014`。同一著者・同年は BBT が接尾辞で区別します（例 `peter2014a`, `peter2014b`）。
- Paper Navigator での確認:
  ```bash
  uv run pn bib-check references.bib --snapshot data/bib_snapshot.json --accept   # 初回: 承認スナップショット保存
  uv run pn bib-check references.bib --snapshot data/bib_snapshot.json            # 以後: キー変更・消失を警告
  ```
  `KEY_CHANGED`（同じ DOI のキーが変わった）・`KEY_REMOVED` が出たら、原稿で使用中のキーが壊れていないか確認してください。
  同一著者・同年は `SAME_AUTHOR_YEAR`（情報）、同一キーは `DUPLICATE_KEY`（エラー）で検出します。

## 6. ADS と Zotero の不一致の扱い
`uv run pn zotero-sync <コレクションキー>` は Zotero を変更せず、以下を DB（`reconciliations`）に記録します。

| 判定 | 意味 | 対応 |
|---|---|---|
| `match` | 一致 | なし |
| `prefer_zotero` | 表記揺れ（大小文字・句読点、雑誌名略称） | `.bib` は Zotero 値で出力されるため対応不要 |
| `manual_review` | DOI・年・巻・ページ・タイトル本文の相違 | Zotero のアイテムを確認して修正 |

リンクは DOI または Zotero の Extra/URL 中の ADS Bibcode の一致のみ。タイトル類似のみの場合は `possible match` として表示し、リンクしません。
