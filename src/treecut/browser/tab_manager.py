"""XHS Work Browser V0.1.1 — Tab Manager（§13/14/15/16/25/26/32）。

3 Fixed Functional Tabs，长期存在，不反复关闭：
  CREATOR   → creator_home_url     （内容身份 + 内容表现 Truth）
  SPOTLIGHT → spotlight_home_url   （投流表现 Truth）
  FRONTEND  → frontend_home_url    （真实发布媒体 Truth）

EXPECTED_TAB_COUNT = 3；允许 1 个临时弹窗（平台自弹）。
Tab 崩溃 → 重建对应功能 Tab（§25 自动恢复）。
reconcile：tab 数 > 预期+弹窗时才收束，且只关闭"我们创建的空页/约 blank"，
绝不盲目关闭用户页面（§14）。
"""
from __future__ import annotations

import logging

from treecut.browser.config import XhsWorkBrowserConfig

log = logging.getLogger("treecut.browser.tabs")

ROLE_HOME = {
    "CREATOR": "creator_home_url",
    "SPOTLIGHT": "spotlight_home_url",
    "FRONTEND": "frontend_home_url",
}


class TabManager:
    def __init__(self, context, config: XhsWorkBrowserConfig):
        self._context = context
        self.config = config
        self.tabs: dict[str, object] = {}  # role -> page
        self._ours: set = set()  # 我们创建的 page（用于保守收束）

    # ---- 创建/恢复 3 个固定 Tab ----
    def create_fixed_tabs(self) -> dict[str, object]:
        """建立 3 个固定 Tab 并导航到各自 origin（登录态由持久 Profile 恢复）。"""
        initial = list(self._context.pages)
        for index, (role, attr) in enumerate(ROLE_HOME.items()):
            url = getattr(self.config, attr)
            if index < len(initial):
                page = initial[index]
            else:
                page = self._context.new_page()
            self.tabs[role] = page
            self._ours.add(page)
            try:
                page.goto(url, timeout=60000)
            except Exception as error:
                log.warning("%s TAB_NAVIGATE_FAILED %s: %s", role, url, str(error)[:120])
        return self.tabs

    # ---- 获取/健康 ----
    def get(self, role: str):
        return self.tabs.get(role)

    def health(self, role: str) -> dict:
        page = self.tabs.get(role)
        alive = page is not None and not page.is_closed()
        url = ""
        if alive:
            try:
                url = page.url
            except Exception:
                url = ""
        return {"role": role, "tab_alive": alive, "url": url}

    # ---- §25 Tab 崩溃 → 重建对应功能 Tab ----
    def rebuild(self, role: str):
        old = self.tabs.get(role)
        if old is not None and not old.is_closed():
            try:
                old.close()
            except Exception:  # pragma: no cover
                pass
        page = self._context.new_page()
        self.tabs[role] = page
        self._ours.add(page)
        page.goto(getattr(self.config, ROLE_HOME[role]), timeout=60000)
        log.info("%s TAB_REBUILT", role)
        return page

    # ---- §14 严格限制 Tab 数（保守收束） ----
    def reconcile(self) -> dict:
        """超过 expected+popup 时：只关闭空白临时页（about:/newtab，几乎必为我方/弹窗残留），
        有真实内容的页面（用户页/平台弹窗）一律不盲目关闭（§14）。返回收束结果。"""
        allowed = self.config.expected_tab_count + self.config.allow_temporary_popup
        pages = list(self._context.pages)
        closed = []
        left = []
        if len(pages) > allowed:
            for page in pages:
                if page in self.tabs.values():
                    continue  # 固定功能 Tab 永不关闭
                if self._is_blank(page):
                    try:
                        page.close()
                        closed.append("blank-temp")
                    except Exception:  # pragma: no cover
                        left.append("close-failed")
                else:
                    left.append("user/unknown")  # 非空白页 → 不盲目关闭
        return {"expected": self.config.expected_tab_count,
                "allowed_with_popup": allowed,
                "actual": len(self._context.pages),
                "closed_extras": closed,
                "left_untouched": len(left)}

    @staticmethod
    def _is_blank(page) -> bool:
        try:
            return (page.url or "").startswith("about:") or page.url == "chrome://newtab/"
        except Exception:
            return False

    def count(self) -> int:
        return len(self._context.pages)
