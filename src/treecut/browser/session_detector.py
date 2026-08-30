"""XHS Work Browser V0.1 — Session Detector（§7/11/12）。

状态：SESSION_VALID / SESSION_EXPIRED / LOGIN_REQUIRED / SESSION_UNKNOWN

纪律：
- 不得因为"页面能打开"就判定 SESSION_VALID（§11）。
- 必须基于真实登录页面状态判断（登录态 marker vs 登录页 marker）。
- 判定基于页面可见文本/元素标记；标记未命中 → SESSION_UNKNOWN（绝不乐观假设）。
"""
from __future__ import annotations

from dataclasses import dataclass

SESSION_VALID = "SESSION_VALID"
SESSION_EXPIRED = "SESSION_EXPIRED"
LOGIN_REQUIRED = "LOGIN_REQUIRED"
SESSION_UNKNOWN = "SESSION_UNKNOWN"


@dataclass
class SessionCheckResult:
    kind: str  # creator | spotlight
    status: str
    matched_login: list[str] = ()
    matched_valid: list[str] = ()
    source_page: str = ""


class SessionDetector:
    def __init__(self, config):
        self.config = config

    def check(self, page, kind: str) -> SessionCheckResult:
        markers = (self.config.session_markers or {}).get(kind)
        if not markers:
            return SessionCheckResult(kind=kind, status=SESSION_UNKNOWN)
        try:
            body = (page.content() or "") + "\n" + (page.title() or "")
        except Exception:
            body = ""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        from urllib.parse import urlsplit
        source = urlsplit(url).netloc or "unknown"

        login_hits = [m for m in markers.get("login", []) if m and m in body]
        valid_hits = [m for m in markers.get("valid", []) if m and m in body]

        if valid_hits and not login_hits:
            status = SESSION_VALID
        elif login_hits and not valid_hits:
            status = LOGIN_REQUIRED  # 登录页：需人工登录（§7/12）
        elif login_hits and valid_hits:
            status = SESSION_EXPIRED  # 混合：可能弹出重新登录
        else:
            status = SESSION_UNKNOWN
        return SessionCheckResult(kind=kind, status=status,
                                  matched_login=login_hits, matched_valid=valid_hits,
                                  source_page=source)
