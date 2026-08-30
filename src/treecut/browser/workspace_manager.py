"""XHS Work Browser V0.1 — Workspace Manager（§3/4/6/9/33/34）。

一个统一 Work Browser，账号通过 Workspace/Profile 隔离（§1A/B）。
每账号一个物理隔离 Persistent Profile：cookie/localStorage/sessionStorage/cache/site data/login state。

安全纪律：Binding Record 不含任何凭证。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from treecut.browser.config import XhsWorkBrowserConfig
from treecut.browser.policies import utcnow_iso
from treecut.platform.paths import RuntimePaths
from treecut.platform.single_instance import SingleInstanceLock


def default_profile_root(paths: RuntimePaths | None = None) -> Path:
    """Profile 稳定持久路径：{data_root}/browser_profiles（不随 batch/temp 清理）。"""
    paths = paths or RuntimePaths.discover()
    return paths.data_root / "browser_profiles"


@dataclass
class AccountBindingRecord:
    """第一次真实检测到账号后，用户人工确认一次的绑定记录（§9）。不含凭证。"""
    workspace_id: str
    platform_account_name: str
    xiaohongshu_id: str | None = None
    current_page_indicator: str = ""
    source_page: str = ""
    bound_at: str = field(default_factory=utcnow_iso)
    detector_version: str = "V0.1"

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "platform_account_name": self.platform_account_name,
            "xiaohongshu_id": self.xiaohongshu_id,
            "current_page_indicator": self.current_page_indicator,
            "source_page": self.source_page,
            "bound_at": self.bound_at,
            "detector_version": self.detector_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccountBindingRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class WorkspaceManager:
    """B007 Workspace 生命周期：目录、锁、绑定记录、状态台账。"""

    def __init__(self, config: XhsWorkBrowserConfig,
                 profile_root: Path | None = None,
                 paths: RuntimePaths | None = None):
        self.config = config
        self.paths = paths or RuntimePaths.discover()
        root = Path(config.profile_root) if config.profile_root else default_profile_root(self.paths)
        self.profile_root = root
        self.workspace_dir = root / config.workspace_id
        self._lock: SingleInstanceLock | None = None

    # ---- 目录 ----
    def ensure_workspace(self) -> Path:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        return self.workspace_dir

    def exists(self) -> bool:
        return self.workspace_dir.is_dir()

    # ---- §33/34 Profile Lock（复用现有 SingleInstanceLock） ----
    def acquire_lock(self) -> SingleInstanceLock:
        """同一 Workspace 只允许一个 Active Browser Instance。
        第二次获取 → PROFILE_LOCKED（抛出 RuntimeError，阻止并发控制同一 Profile）。"""
        if self._lock is not None:
            return self._lock
        self.ensure_workspace()
        lock = SingleInstanceLock(self.workspace_dir / ".profile.lock")
        self._lock = lock
        return lock

    def release_lock(self) -> None:
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def locked(self) -> bool:
        if self._lock is not None:
            return True
        lock_path = self.workspace_dir / ".profile.lock"
        if not lock_path.is_file():
            return False
        try:
            SingleInstanceLock(lock_path)
        except RuntimeError:
            return True
        return False

    def profile_health(self) -> dict:
        """§33 Profile Health Check：目录存在 / 可读写 / 是否被占用。"""
        status = {
            "exists": self.exists(),
            "writable": None,
            "locked": self.locked(),
            "lock_state": "PROFILE_LOCKED" if self.locked() else "PROFILE_FREE",
        }
        if status["exists"]:
            probe = self.workspace_dir / ".write_probe"
            try:
                probe.write_text("probe", encoding="utf-8")
                probe.unlink(missing_ok=True)
                status["writable"] = True
            except OSError:
                status["writable"] = False
        return status

    # ---- §9 Account Binding Record（无凭证） ----
    def binding_path(self) -> Path:
        return self.workspace_dir / "account_binding.json"

    def load_binding(self) -> AccountBindingRecord | None:
        path = self.binding_path()
        if not path.is_file():
            return None
        try:
            return AccountBindingRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def save_binding(self, record: AccountBindingRecord) -> Path:
        self.ensure_workspace()
        path = self.binding_path()
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return path

    # ---- 状态台账（供控制面板/日志，无敏感信息） ----
    def workspace_status(self, treecut_status: str = "UNKNOWN",
                         creator_session: str = "UNKNOWN",
                         spotlight_session: str = "UNKNOWN",
                         account: str = "UNKNOWN",
                         task: str = "IDLE",
                         last_checkpoint: str | None = None) -> dict:
        return {
            "workspace_id": self.config.workspace_id,
            "profile_dir": str(self.workspace_dir),
            "profile_exists": self.exists(),
            "creator": creator_session,
            "spotlight": spotlight_session,
            "account": account,
            "treecut_local": treecut_status,
            "current_task": task,
            "last_checkpoint": last_checkpoint,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
