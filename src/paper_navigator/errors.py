"""Error taxonomy shared by every layer (spec §8.1).

User-facing text (``user_message``) and developer diagnostics (``detail``) are kept
separate so the UI never needs to show stack traces or raw API payloads.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    CONFIG_ERROR = "CONFIG_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    NOT_FOUND = "NOT_FOUND"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    DATABASE_ERROR = "DATABASE_ERROR"
    ZOTERO_UNAVAILABLE = "ZOTERO_UNAVAILABLE"
    ZOTERO_AUTH_REQUIRED = "ZOTERO_AUTH_REQUIRED"
    BIBTEX_INVALID = "BIBTEX_INVALID"
    LATEX_BUILD_ERROR = "LATEX_BUILD_ERROR"
    INPUT_ERROR = "INPUT_ERROR"
    INTERRUPTED = "INTERRUPTED"


USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.CONFIG_ERROR: "設定が不足しています（例: ADS_API_TOKEN 未設定）。.env を確認してください。",
    ErrorCode.AUTH_ERROR: "認証に失敗しました。APIトークンが正しいか確認してください。",
    ErrorCode.RATE_LIMITED: "APIのレート制限に達しました。時間をおいて再実行してください。",
    ErrorCode.NETWORK_ERROR: "ネットワーク通信に失敗しました。接続を確認してください。",
    ErrorCode.TIMEOUT: "API応答がタイムアウトしました。",
    ErrorCode.NOT_FOUND: "該当する論文が見つかりませんでした。",
    ErrorCode.INVALID_RESPONSE: "APIから想定外の応答が返されました。",
    ErrorCode.PARTIAL_RESULT: "一部のみ取得できました（未取得範囲あり）。",
    ErrorCode.DATABASE_ERROR: "データベース処理に失敗しました。変更はロールバックされました。",
    ErrorCode.ZOTERO_UNAVAILABLE: "Zoteroに接続できません。Zoteroの起動とLocal API設定を確認してください。",
    ErrorCode.ZOTERO_AUTH_REQUIRED: "Zoteroへの書き込みには利用者の許可が必要です。",
    ErrorCode.BIBTEX_INVALID: "BibTeXファイルに問題があります。",
    ErrorCode.LATEX_BUILD_ERROR: "LaTeX/BibTeXのコンパイルに失敗しました。",
    ErrorCode.INPUT_ERROR: "入力値が不正です。",
    ErrorCode.INTERRUPTED: "前回の処理が途中で終了しました（取得済み部分は保持）。",
}


class PNError(Exception):
    """Base error carrying a classification code."""

    def __init__(self, code: ErrorCode, detail: str = "", *, retry_after: float | None = None):
        self.code = code
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(f"{code}: {detail}" if detail else str(code))

    @property
    def user_message(self) -> str:
        return USER_MESSAGES[self.code]
