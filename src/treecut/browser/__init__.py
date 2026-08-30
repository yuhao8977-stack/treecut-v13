"""TreeCut XHS Work Browser V0.1.1 — Three-Tab Foundation（PHASE 1 基础设施修订）。

统一 XHS Work Browser：一个 Workspace = 一个 Persistent Profile + 3 固定功能 Tab
（Creator / Spotlight / Frontend）+ Single Worker + Local TreeCut Bridge（§1A/B）。

V0.1.1 只做基础设施：三站登录保持 / 三站 Session 独立检测 / 三身份绑定与核验 /
非阻塞 UI / 日志可见 / 安全退出 / Checkpoint / Retry / Tab 恢复。
不实现：抓取 / 下载 / 媒体恢复 / Content DNA。
"""
from __future__ import annotations

__version__ = "0.1.1"

from treecut.browser.config import XhsWorkBrowserConfig, load_config
from treecut.browser.workspace_manager import (
    CreatorIdentity,
    FrontendIdentity,
    SpotlightIdentity,
    WorkspaceBinding,
    WorkspaceManager,
    default_profile_root,
)
from treecut.browser.account_detector import (
    CreatorIdentityDetector,
    FrontendIdentityDetector,
    RoleIdentity,
    SpotlightIdentityDetector,
)
from treecut.browser.session_detector import SessionDetector, SessionCheckResult
from treecut.browser.tab_manager import TabManager
from treecut.browser.task_engine import TaskEngine, TaskResult
from treecut.browser.checkpoint_store import Checkpoint, CheckpointStore
from treecut.browser.retry_policy import BoundedRetry, RetryDecision
from treecut.browser.local_bridge import LocalBridge, LocalServiceStub
from treecut.browser.errors import (
    ErrorCategory,
    NoteIdMismatchError,
    XhsWorkBrowserError,
    classify,
)
from treecut.browser.policies import InboxManager, QuarantineEntry
from treecut.browser.adapters import ADAPTERS

__all__ = [
    "__version__",
    "XhsWorkBrowserConfig", "load_config",
    "WorkspaceManager", "WorkspaceBinding",
    "CreatorIdentity", "SpotlightIdentity", "FrontendIdentity", "default_profile_root",
    "CreatorIdentityDetector", "SpotlightIdentityDetector", "FrontendIdentityDetector",
    "RoleIdentity",
    "SessionDetector", "SessionCheckResult",
    "TabManager",
    "TaskEngine", "TaskResult",
    "Checkpoint", "CheckpointStore",
    "BoundedRetry", "RetryDecision",
    "LocalBridge", "LocalServiceStub",
    "ErrorCategory", "NoteIdMismatchError", "XhsWorkBrowserError", "classify",
    "InboxManager", "QuarantineEntry",
    "ADAPTERS",
]
