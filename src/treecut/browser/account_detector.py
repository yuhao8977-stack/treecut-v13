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

import logging
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

log = logging.getLogger("treecut.browser")

# 页面上的候选账号名选择器（保守清单；"取到才用"）
ACCOUNT_NAME_SELECTORS = (
    "a[href*='/user/profile/'] .name",
    ".creator-header .nickname",
    "[class*='nickname']",
    "[class*='user-name']",
    "[class*='account-name']",
    "img[alt*='头像']",
    "[class*='header'] [class*='name']",
    "[class*='user'] [class*='name']",
    "a[href*='user/profile']",
    "[class*='creator'] [class*='name']",
)
# 聚光广告账户名选择器候选
AD_ACCOUNT_SELECTORS = (
    "[class*='account-name']",
    "[class*='ad-account']",
    "[class*='company-name']",
    ".user-info .name",
    ".header-user .name",
    "[class*='account'] [class*='name']",
    "[class*='user-info'] .name",
    "[class*='header'] .name",
    "[class*='advertiser']",
    "[class*='biz-name']",
)
XHS_ID_PATTERNS = (
    r"小红书号[:：]?\s*([0-9a-zA-Z]{6,})",
    r"xiaohongshu[号iI][dD]?[:：]?\s*([0-9a-zA-Z]{6,})",
    r"xhs[_\-]?id[:：]?\s*([0-9a-zA-Z]{6,})",
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
        """逐选择器探测（8s/个：XHS SPA 昵称渲染通常 2-8s；30s 太慢、2s 太激进）。"""
        for selector in selectors:
            try:
                text = page.text_content(selector, timeout=8000)
            except Exception:
                continue
            text = (text or "").strip()
            if text and len(text) <= 40 and "登录" not in text:
                return text
        return None

    @staticmethod
    def _body(page) -> str:
        """轻量读取页面文本：textContent JS 求值（XHS 大页面 content() 需数分钟、
        innerText 触发布局计算也需数十秒；textContent 免布局，数秒内返回）。
        无 evaluate 的测试桩回退到 content()。"""
        if hasattr(page, "evaluate"):
            try:
                value = page.evaluate(
                    "() => document.documentElement ? "
                    "document.documentElement.textContent.slice(0, 150000) : ''")
                if isinstance(value, str) and value.strip():
                    return value
            except Exception:
                pass
        try:
            return page.content() or ""
        except Exception:
            return ""

    @staticmethod
    def _diagnose(page) -> str:
        """检测失败时的真实页面诊断（仅 URL origin / title；无内容、无凭证、无重 DOM 扫描）。"""
        try:
            url = urlsplit(page.url or "").netloc
        except Exception:
            url = "?"
        try:
            title = (page.title() or "")[:60]
        except Exception:
            title = "?"
        return f"url={url} title='{title}'"


class CreatorIdentityDetector(_BaseDetector):
    """Creator：主身份锚点。XHS ID 不变 → 仍为 B007。

    昵称选择器可能未命中真实 DOM，但小红书号（ID）是主锚：
    只要 body 中稳定取得 ID，即可识别与绑定（display_name 可为 None）。
    """

    def detect(self, page) -> RoleIdentity | None:
        try:
            url = page.url or ""
        except Exception:
            url = ""
        body = self._body(page)
        name = self._find_text(page, ACCOUNT_NAME_SELECTORS)
        xhs_id = _extract(body, XHS_ID_PATTERNS)
        if not xhs_id and hasattr(page, "evaluate"):
            # 定向提取：全文搜索"小红书号"（不受截断影响；仅首次绑定慢一次）
            try:
                value = page.evaluate(
                    "() => { const t = document.body ? document.body.innerText : ''; "
                    "const m = t.match(/小红书号[:：]?\\s*([0-9A-Za-z]{6,})/); "
                    "return m ? m[1] : null; }")
                if isinstance(value, str) and value.strip():
                    xhs_id = value.strip()
            except Exception:
                pass
        if not name and not xhs_id:
            log.info("Creator 身份未检测到（诊断：%s）", self._diagnose(page))
            return None
        # 主锚 = ID；ID 缺失时退化为 name（绝不凭空捏造）
        return RoleIdentity(role="creator",
                            primary_id=xhs_id or name,
                            display_name=name,
                            source_page=_safe_source(url))

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
            log.info("聚光广告账户未检测到（诊断：%s）", self._diagnose(page))
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
