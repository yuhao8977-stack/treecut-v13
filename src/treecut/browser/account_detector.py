"""XHS Work Browser V0.1 — Account Detector + Identity Gate（§8/9/10/44/45）。

必须尝试获取：platform_account_name / xiaohongshu_id（页面可安全取得时）/
current page account indicator / source page / detected_at。

纪律：
- 不得仅根据 Profile 目录名认定账号身份（expected 只来自人工确认后的 Binding Record）。
- 检测不到真实账号 → UNKNOWN（绝不猜测、绝不自动把 detected 改成 expected）。
- source_page 只取 origin（host），不取 query / signed URL。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from treecut.browser.policies import utcnow_iso
from treecut.browser.workspace_manager import AccountBindingRecord, WorkspaceManager

# 页面上的候选账号名选择器（保守清单；V0.1 采用"取到才用"策略）
ACCOUNT_NAME_SELECTORS = (
    "a[href*='/user/profile/'] .name",
    ".creator-header .nickname",
    "[class*='nickname']",
    "[class*='user-name']",
    "[class*='account-name']",
    "img[alt*='头像']",
)
XHS_ID_PATTERNS = (r"小红书号[:：]\s*([0-9a-zA-Z]+)", r"xiaohongshu[号iI][dD]?[:：]\s*([0-9a-zA-Z]+)")


@dataclass
class AccountIdentity:
    platform_account_name: str
    xiaohongshu_id: str | None = None
    current_page_indicator: str = ""
    source_page: str = ""
    detected_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict:
        return {
            "platform_account_name": self.platform_account_name,
            "xiaohongshu_id": self.xiaohongshu_id,
            "current_page_indicator": self.current_page_indicator,
            "source_page": self.source_page,
            "detected_at": self.detected_at,
        }


class AccountDetector:
    """page 需提供最小接口：url / title / content() / text_content(selector) 或等效。

    测试可用 FakePage；真实 Playwright Page 原生兼容。
    """

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    @staticmethod
    def _page_indicator(url: str) -> str:
        host = urlsplit(url or "").hostname or ""
        if "creator" in host:
            return "creator"
        if "ad.xiaohongshu" in host or "spotlight" in host:
            return "spotlight"
        if "xiaohongshu" in host:
            return "xhs"
        return "unknown"

    def detect(self, page) -> AccountIdentity | None:
        """尽力检测当前真实账号。取不到账号名 → None（= UNKNOWN，绝不猜测）。"""
        try:
            url = page.url or ""
        except Exception:
            url = ""
        indicator = self._page_indicator(url)
        source = urlsplit(url).netloc or "unknown"

        name = self._find_account_name(page)
        if not name:
            return None
        xhs_id = self._find_xhs_id(page)
        return AccountIdentity(
            platform_account_name=name,
            xiaohongshu_id=xhs_id,
            current_page_indicator=indicator,
            source_page=source,
        )

    def _find_account_name(self, page) -> str | None:
        for selector in ACCOUNT_NAME_SELECTORS:
            try:
                text = page.text_content(selector)
            except Exception:
                continue
            text = (text or "").strip()
            if text and len(text) <= 40 and "登录" not in text:
                return text
        return None

    def _find_xhs_id(self, page) -> str | None:
        try:
            body = page.content() or ""
        except Exception:
            return None
        import re
        for pattern in XHS_ID_PATTERNS:
            match = re.search(pattern, body)
            if match:
                return match.group(1)
        return None

    # ---- §10 Account Identity Gate ----
    def gate(self, detected: AccountIdentity | None) -> tuple[str, str | None]:
        """expected 只来自 Binding Record（人工确认）；绝不读 Profile 目录名。

        返回 (状态, reason)：ACCOUNT_IDENTITY_VALID / ACCOUNT_IDENTITY_MISMATCH / ACCOUNT_IDENTITY_UNKNOWN
        """
        binding = self.workspace.load_binding()
        if binding is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "尚未绑定账号（首次登录后需人工确认一次）"
        if detected is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "页面未检测到账号身份"
        if detected.platform_account_name == binding.platform_account_name:
            return "ACCOUNT_IDENTITY_VALID", None
        return (
            "ACCOUNT_IDENTITY_MISMATCH",
            f"检测到 {detected.platform_account_name}（期望 {binding.platform_account_name}），BLOCK_SYNC",
        )

    # ---- §9 首次绑定（用户人工确认后调用，保存 Binding Record，不含凭证） ----
    def bind(self, detected: AccountIdentity) -> AccountBindingRecord:
        record = AccountBindingRecord(
            workspace_id=self.workspace.config.workspace_id,
            platform_account_name=detected.platform_account_name,
            xiaohongshu_id=detected.xiaohongshu_id,
            current_page_indicator=detected.current_page_indicator,
            source_page=detected.source_page,
        )
        self.workspace.save_binding(record)
        return record
