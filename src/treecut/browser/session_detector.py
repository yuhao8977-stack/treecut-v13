"""XHS Work Browser V0.1.1 — Session Detector（三站独立，§6/7/11/12/23/27）。

三站 Session 分别检测：Creator / Spotlight / Frontend 互不影响。
（Creator 掉登录不应把 Spotlight/Frontend 一起判失效，反之亦然。）

状态：SESSION_VALID / SESSION_EXPIRED / LOGIN_REQUIRED / SESSION_UNKNOWN

判定分层（消除 V0.1 误报：已登录页常见"登录"字样出现于页脚/浮层，
不得据此判 EXPIRED）：
  1. expired markers（强信号："登录已过期/请重新登录/..."） → SESSION_EXPIRED
  2. valid markers 命中                              → SESSION_VALID
  3. 仅 login markers 命中                            → LOGIN_REQUIRED
  4. 无信号                                        → SESSION_UNKNOWN

纪律：页面能打开 ≠ SESSION_VALID（§11）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

SESSION_VALID = "SESSION_VALID"
SESSION_EXPIRED = "SESSION_EXPIRED"
LOGIN_REQUIRED = "LOGIN_REQUIRED"
SESSION_UNKNOWN = "SESSION_UNKNOWN"

KINDS = ("creator", "spotlight", "frontend")


@dataclass
class SessionCheckResult:
    kind: str  # creator | spotlight | frontend
    status: str
    matched_expired: list[str] = field(default_factory=list)
    matched_login: list[str] = field(default_factory=list)
    matched_valid: list[str] = field(default_factory=list)
    source_page: str = ""


class SessionDetector:
    def __init__(self, config):
        self.config = config

    def check(self, page, kind: str) -> SessionCheckResult:
        if kind not in KINDS:
            return SessionCheckResult(kind=kind, status=SESSION_UNKNOWN)
        markers = (self.config.session_markers or {}).get(kind) or {}
        try:
            body = (page.content() or "") + "\n" + (page.title() or "")
        except Exception:
            body = ""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        source = urlsplit(url).netloc or "unknown"

        expired_hits = [m for m in markers.get("expired", []) if m and m in body]
        login_hits = [m for m in markers.get("login", []) if m and m in body]
        valid_hits = [m for m in markers.get("valid", []) if m and m in body]

        if expired_hits:
            status = SESSION_EXPIRED
        elif valid_hits:
            status = SESSION_VALID
        elif login_hits:
            status = LOGIN_REQUIRED
        else:
            status = SESSION_UNKNOWN
        return SessionCheckResult(kind=kind, status=status,
                                  matched_expired=expired_hits,
                                  matched_login=login_hits,
                                  matched_valid=valid_hits,
                                  source_page=source)
