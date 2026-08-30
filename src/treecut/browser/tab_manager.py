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
        """建立 3 个固定 Tab 并导航到各自 origin（登录态由持久 Profile 恢复）。
        随后去重：会话恢复/历史残留导致的重复托管页按 origin 关闭（§12）。"""
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
        self.dedupe_managed()
        return self.tabs

    # ---- §12 重复托管页去重：origin 命中托管角色且该角色已有 canonical 页 → 关闭残留 ----
    def dedupe_managed(self) -> dict:
        managed_hosts = {}
        for role, attr in ROLE_HOME.items():
            try:
                from urllib.parse import urlsplit
                managed_hosts[role] = urlsplit(getattr(self.config, attr)).hostname or ""
            except Exception:
                managed_hosts[role] = ""
        closed = []
        for page in list(self._context.pages):
            if page in self.tabs.values():
                continue  # canonical 托管页
            host = ""
            try:
                from urllib.parse import urlsplit
                host = urlsplit(page.url or "").hostname or ""
            except Exception:
                host = ""
            if host and host in managed_hosts.values():
                # 该域是 TreeCut 托管角色域且非 canonical → 确认由 TreeCut 创建的 stale duplicate
                try:
                    page.close()
                    closed.append(host)
                    log.info("TAB_DUPLICATE_CLOSED host=%s", host)
                except Exception:  # pragma: no cover
                    pass
        return {"closed_duplicates": closed,
                "managed": {role: len(self.tabs)}}


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
        """1) 重复托管页去重（§12）；2) 超过 expected+popup 时只关闭空白临时页
        （about:/newtab），有真实内容的页面（用户页/平台弹窗）一律不盲目关闭（§14）。"""
        dedupe = self.dedupe_managed()
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
                "left_untouched": len(left),
                "closed_duplicates": dedupe["closed_duplicates"]}

    @staticmethod
    def _is_blank(page) -> bool:
        try:
            return (page.url or "").startswith("about:") or page.url == "chrome://newtab/"
        except Exception:
            return False

    def count(self) -> int:
        return len(self._context.pages)
