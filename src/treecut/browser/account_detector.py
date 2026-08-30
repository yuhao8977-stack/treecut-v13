"""XHS Work Browser V0.1.1 — Account Detector（三身份）+ Identity Gates（§8/9/10/11）。

三站身份分别检测、分别绑定、分别核验：
- CreatorIdentity  ：XHS ID + Display Name（主身份锚点；ID 不变即仍为 B007，昵称可改）
- SpotlightIdentity：Ad Account ID + Name（名字允许与 Creator 不一致，单独人工确认）
- FrontendIdentity ：User ID + Name（可与 Creator 不一致；未确认不得假装已确认；
                     视频能播放 ≠ 账号正确）

纪律（沿用）：
- 不得仅凭 Profile 目录名认定账号身份（expected 只来自人工确认后的 Binding）。
- 检测不到 → UNKNOWN，绝不猜测、绝不自动把 detected 改成 expected。
- source_page 只取 origin（host），不取 query / signed URL。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from treecut.browser.policies import utcnow_iso
from treecut.browser.workspace_manager import (
    CreatorIdentity,
    FrontendIdentity,
    SpotlightIdentity,
    WorkspaceBinding,
    WorkspaceManager,
)

# 页面上的候选账号名选择器（保守清单；"取到才用"）
ACCOUNT_NAME_SELECTORS = (
    "a[href*='/user/profile/'] .name",
    ".creator-header .nickname",
    "[class*='nickname']",
    "[class*='user-name']",
    "[class*='account-name']",
    "img[alt*='头像']",
)
# 聚光广告账户名选择器候选
AD_ACCOUNT_SELECTORS = (
    "[class*='account-name']",
    "[class*='ad-account']",
    "[class*='company-name']",
    ".user-info .name",
    ".header-user .name",
)
XHS_ID_PATTERNS = (
    r"小红书号[:：]\s*([0-9a-zA-Z]+)",
    r"xiaohongshu[号iI][dD]?[:：]\s*([0-9a-zA-Z]+)",
    r"xhs[_\-]?id[:：]\s*([0-9a-zA-Z]+)",
)
AD_ID_PATTERNS = (
    r"广告账户[ID号号]?[:：\s]*([0-9a-zA-Z]+)",
    r"ad[_\-]?account[_\-]?id[:：\s]*([0-9a-zA-Z]+)",
)


def page_indicator(url: str) -> str:
    host = urlsplit(url or "").hostname or ""
    if "creator" in host:
        return "creator"
    if "ad.xiaohongshu" in host or "spotlight" in host:
        return "spotlight"
    if "xiaohongshu" in host:
        return "frontend"
    return "unknown"


def _safe_source(url: str) -> str:
    return urlsplit(url or "").netloc or "unknown"


def _extract(body: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(1)
    return None


@dataclass
class RoleIdentity:
    """检测到的某站身份（与绑定记录比对前的中性载体）。"""
    role: str  # creator | spotlight | frontend
    primary_id: str | None = None     # xhs_id / ad_account_id / user_id
    display_name: str | None = None
    source_page: str = ""
    detected_at: str = field(default_factory=utcnow_iso)


class _BaseDetector:
    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    @staticmethod
    def _find_text(page, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            try:
                text = page.text_content(selector)
            except Exception:
                continue
            text = (text or "").strip()
            if text and len(text) <= 40 and "登录" not in text:
                return text
        return None

    @staticmethod
    def _body(page) -> str:
        try:
            return page.content() or ""
        except Exception:
            return ""


class CreatorIdentityDetector(_BaseDetector):
    """Creator：主身份锚点。XHS ID 不变 → 仍为 B007。"""

    def detect(self, page) -> RoleIdentity | None:
        try:
            url = page.url or ""
        except Exception:
            url = ""
        body = self._body(page)
        name = self._find_text(page, ACCOUNT_NAME_SELECTORS) or _extract(body, XHS_ID_PATTERNS)
        if not name:
            return None
        xhs_id = _extract(body, XHS_ID_PATTERNS)
        return RoleIdentity(role="creator", primary_id=xhs_id or name,
                            display_name=name, source_page=_safe_source(url))

    def bind(self, detected: RoleIdentity) -> WorkspaceBinding:
        binding = self.workspace.load_binding() or WorkspaceBinding(
            workspace_id=self.workspace.config.workspace_id)
        binding.creator_xhs_id = detected.primary_id or ""
        binding.creator_display_name = detected.display_name or ""
        self.workspace.save_binding(binding)
        return binding

    def gate(self, detected: RoleIdentity | None) -> tuple[str, str | None]:
        binding = self.workspace.load_binding()
        if binding is None or not binding.creator_xhs_id:
            return "ACCOUNT_IDENTITY_UNKNOWN", "尚未绑定 Creator（首次登录后需人工确认）"
        if detected is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "Creator 页面未检测到账号身份"
        # 主锚点：XHS ID 一致即 VALID（昵称可改，ID 不变仍是 B007）
        if detected.primary_id and detected.primary_id == binding.creator_xhs_id:
            return "ACCOUNT_IDENTITY_VALID", None
        if detected.display_name and detected.display_name == binding.creator_display_name:
            return "ACCOUNT_IDENTITY_VALID", None
        return "ACCOUNT_IDENTITY_MISMATCH", (
            f"Creator 检测到 {detected.display_name or detected.primary_id}"
            f"（期望 {binding.creator_display_name}/{binding.creator_xhs_id}），BLOCK_SYNC")


class SpotlightIdentityDetector(_BaseDetector):
    """Spotlight：广告账户单独绑定；名字不需要与 Creator 一致（§10）。"""

    def detect(self, page) -> RoleIdentity | None:
        try:
            url = page.url or ""
        except Exception:
            url = ""
        body = self._body(page)
        name = self._find_text(page, AD_ACCOUNT_SELECTORS)
        ad_id = _extract(body, AD_ID_PATTERNS)
        if not name and not ad_id:
            return None
        return RoleIdentity(role="spotlight", primary_id=ad_id or name,
                            display_name=name, source_page=_safe_source(url))

    def bind(self, detected: RoleIdentity) -> WorkspaceBinding:
        binding = self.workspace.load_binding() or WorkspaceBinding(
            workspace_id=self.workspace.config.workspace_id)
        binding.spotlight_ad_account_id = detected.primary_id or ""
        binding.spotlight_ad_account_name = detected.display_name or ""
        self.workspace.save_binding(binding)
        return binding

    def gate(self, detected: RoleIdentity | None) -> tuple[str, str | None]:
        binding = self.workspace.load_binding()
        if binding is None or not binding.spotlight_ad_account_id:
            return "ACCOUNT_IDENTITY_UNKNOWN", "尚未绑定聚光广告账户"
        if detected is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "聚光页面未检测到广告账户"
        if detected.primary_id and detected.primary_id == binding.spotlight_ad_account_id:
            return "ACCOUNT_IDENTITY_VALID", None
        if detected.display_name and detected.display_name == binding.spotlight_ad_account_name:
            return "ACCOUNT_IDENTITY_VALID", None
        return "ACCOUNT_IDENTITY_MISMATCH", (
            f"聚光检测到 {detected.display_name or detected.primary_id}"
            f"（期望 {binding.spotlight_ad_account_name}），BLOCK_SYNC")


class FrontendIdentityDetector(_BaseDetector):
    """Frontend：前台账号可检测则绑定；检测不到 → 仅 FRONTEND_SESSION_VALID，
    绑定保持 UNCONFIRMED，绝不假装已确认账号对应（§11）。"""

    def detect(self, page) -> RoleIdentity | None:
        try:
            url = page.url or ""
        except Exception:
            url = ""
        body = self._body(page)
        name = self._find_text(page, ACCOUNT_NAME_SELECTORS)
        user_id = _extract(body, XHS_ID_PATTERNS)
        if not name and not user_id:
            return None
        return RoleIdentity(role="frontend", primary_id=user_id or name,
                            display_name=name, source_page=_safe_source(url))

    def confirm(self, detected: RoleIdentity) -> WorkspaceBinding:
        binding = self.workspace.load_binding() or WorkspaceBinding(
            workspace_id=self.workspace.config.workspace_id)
        binding.frontend_user_id = detected.primary_id
        binding.frontend_display_name = detected.display_name
        binding.frontend_confirmed = True
        self.workspace.save_binding(binding)
        return binding

    def gate(self, detected: RoleIdentity | None) -> tuple[str, str | None]:
        binding = self.workspace.load_binding()
        if binding is None or not binding.frontend_confirmed:
            if detected is None:
                return "FRONTEND_IDENTITY_UNCONFIRMED", "未检测到前台账号（未确认，不假装对应）"
            return "FRONTEND_IDENTITY_UNCONFIRMED", (
                f"检测到前台账号 {detected.display_name or detected.primary_id}，待人工确认绑定")
        if detected is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "前台页面未检测到账号身份"
        if detected.primary_id and binding.frontend_user_id and \
                detected.primary_id == binding.frontend_user_id:
            return "ACCOUNT_IDENTITY_VALID", None
        if detected.display_name and binding.frontend_display_name and \
                detected.display_name == binding.frontend_display_name:
            return "ACCOUNT_IDENTITY_VALID", None
        return "ACCOUNT_IDENTITY_MISMATCH", (
            f"前台检测到 {detected.display_name or detected.primary_id}"
            f"（期望 {binding.frontend_display_name}），BLOCK_SYNC")
