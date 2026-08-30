"""XHS Work Browser — 错误分类与硬停/自动恢复策略（§23-25）。

至少定义：
NETWORK_TIMEOUT / PAGE_LOAD_TIMEOUT / SESSION_EXPIRED /
ACCOUNT_IDENTITY_MISMATCH / TREECUT_DISCONNECTED / PAGE_STRUCTURE_CHANGED / UNKNOWN_ERROR
另加 CAPTCHA_VERIFICATION（验证码/人工验证，硬停）。
"""
from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    PAGE_LOAD_TIMEOUT = "PAGE_LOAD_TIMEOUT"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ACCOUNT_IDENTITY_MISMATCH = "ACCOUNT_IDENTITY_MISMATCH"
    TREECUT_DISCONNECTED = "TREECUT_DISCONNECTED"
    PAGE_STRUCTURE_CHANGED = "PAGE_STRUCTURE_CHANGED"
    CAPTCHA_VERIFICATION = "CAPTCHA_VERIFICATION"
    NOTE_ID_MISMATCH = "NOTE_ID_MISMATCH"  # expected note_id ≠ actual（§24 硬停）
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class XhsWorkBrowserError(Exception):
    """V0.1 统一错误基类。携带分类，便于 Retry Policy 与 Task Engine 决策。"""

    category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR

    def __init__(self, message: str, *, category: ErrorCategory | None = None):
        super().__init__(message)
        if category is not None:
            self.category = category


class NetworkTimeoutError(XhsWorkBrowserError):
    category = ErrorCategory.NETWORK_TIMEOUT


class PageLoadTimeoutError(XhsWorkBrowserError):
    category = ErrorCategory.PAGE_LOAD_TIMEOUT


class SessionExpiredError(XhsWorkBrowserError):
    category = ErrorCategory.SESSION_EXPIRED


class AccountIdentityMismatchError(XhsWorkBrowserError):
    category = ErrorCategory.ACCOUNT_IDENTITY_MISMATCH


class TreecutDisconnectedError(XhsWorkBrowserError):
    category = ErrorCategory.TREECUT_DISCONNECTED


class PageStructureChangedError(XhsWorkBrowserError):
    category = ErrorCategory.PAGE_STRUCTURE_CHANGED


class CaptchaVerificationError(XhsWorkBrowserError):
    category = ErrorCategory.CAPTCHA_VERIFICATION


class NoteIdMismatchError(XhsWorkBrowserError):
    """expected note_id ≠ actual（§24/35：媒体/数据身份真实性硬停，绝不猜）。"""
    category = ErrorCategory.NOTE_ID_MISMATCH


# 硬停：不得自动猜测解决，必须 NEEDS_HUMAN（§24）
HARD_STOP_CATEGORIES = frozenset({
    ErrorCategory.SESSION_EXPIRED,
    ErrorCategory.ACCOUNT_IDENTITY_MISMATCH,
    ErrorCategory.CAPTCHA_VERIFICATION,
    ErrorCategory.PAGE_STRUCTURE_CHANGED,
    ErrorCategory.NOTE_ID_MISMATCH,
})

# 允许自动恢复：bounded retry / refresh / renavigate（§25）
AUTO_RECOVER_CATEGORIES = frozenset({
    ErrorCategory.NETWORK_TIMEOUT,
    ErrorCategory.PAGE_LOAD_TIMEOUT,
    ErrorCategory.TREECUT_DISCONNECTED,  # 断开可自动重连（服务恢复后）
})


def classify(error: BaseException) -> ErrorCategory:
    """把任意异常映射为分类（优先取类别上的 category 属性）。"""
    if isinstance(error, XhsWorkBrowserError):
        return error.category
    # 常见第三方异常的保守映射；其余归 UNKNOWN_ERROR（不得过度猜测）。
    name = type(error).__name__.lower()
    message = str(error).lower()
    if any(k in name for k in ("timeout", "timedout", "deadline")) or \
            "timed out" in message or "timeout" in message:
        return ErrorCategory.PAGE_LOAD_TIMEOUT
    if any(k in name for k in ("connectionrefused", "connectionerror", "network")):
        return ErrorCategory.NETWORK_TIMEOUT
    return ErrorCategory.UNKNOWN_ERROR
