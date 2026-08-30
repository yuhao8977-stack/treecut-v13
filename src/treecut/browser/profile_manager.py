"""XHS Work Browser V0.1 — Profile Manager（§2/4/6/15/32）。

Persistent Chromium/Edge Context：每账号一个 user_data_dir（物理隔离），
关闭后不删除，重开复用 → 登录状态持久化。

Playwright 延迟导入：无 playwright 环境下（纯单元测试）不报错。
"""
from __future__ import annotations

from pathlib import Path

from treecut.browser.config import XhsWorkBrowserConfig
from treecut.browser.errors import XhsWorkBrowserError
from treecut.browser.workspace_manager import WorkspaceManager


class ProfileManager:
    def __init__(self, config: XhsWorkBrowserConfig, workspace: WorkspaceManager):
        self.config = config
        self.workspace = workspace
        self._context = None
        self._playwright = None

    @property
    def user_data_dir(self) -> Path:
        return self.workspace.ensure_workspace()

    # ---- §33 健康检查 ----
    def check_health(self) -> dict:
        return self.workspace.profile_health()

    # ---- §2 启动 Persistent Context（channel=msedge，无需下载 Chromium） ----
    def launch_persistent_context(self, headless: bool | None = None,
                                  executable_path: str | None = None):
        """返回 (context, browser)。context 绑定固定 user_data_dir，关闭后数据保留。

        若 Profile 已被另一实例占用（PROFILE_LOCKED），由调用方先行 acquire_lock。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:  # pragma: no cover
            raise XhsWorkBrowserError("未安装 playwright，无法启动 Work Browser") from error

        self.workspace.ensure_workspace()
        headless = self.config.headless if headless is None else headless
        pw = sync_playwright().start()
        self._playwright = pw
        kwargs = {
            "user_data_dir": str(self.user_data_dir),
            "headless": headless,
            "viewport": None,
        }
        if executable_path:
            kwargs["executable_path"] = executable_path
        elif self.config.browser_channel:
            kwargs["channel"] = self.config.browser_channel
        try:
            context = pw.chromium.launch_persistent_context(**kwargs)
        except Exception as error:  # pragma: no cover — 环境相关
            pw.stop()
            raise XhsWorkBrowserError(
                f"无法启动 Persistent Browser Context（channel={self.config.browser_channel}）：{error}"
            ) from error
        self._context = context
        return context, context.browser

    # ---- §32 资源管理：关闭即释放，不累积 Context/后台 Worker ----
    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:  # pragma: no cover
                pass
            self._context = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # pragma: no cover
                pass
            self._playwright = None
