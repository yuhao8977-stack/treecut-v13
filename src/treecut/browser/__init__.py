"""TreeCut XHS Work Browser V0.1 — Persistent Account Workspace Foundation.

统一 XHS Work Browser：一个程序，账号经 Workspace/Profile 隔离（§1A/B）。
V0.1 只做：固定工作浏览器 / 持久 Profile / 登录态持久化 / 账号身份检测 /
TreeCut Local 连接 / 极简控制台 / Checkpoint / 安全退出与恢复。
不实现：抓取 / 下载 / 媒体恢复 / Content DNA。
"""
from __future__ import annotations

__version__ = "0.1.0"

from treecut.browser.config import XhsWorkBrowserConfig, load_config
from treecut.browser.workspace_manager import (
    AccountBindingRecord,
    WorkspaceManager,
    default_profile_root,
)
from treecut.browser.account_detector import AccountDetector, AccountIdentity
from treecut.browser.session_detector import SessionDetector, SessionCheckResult
from treecut.browser.task_engine import TaskEngine, TaskResult
from treecut.browser.checkpoint_store import Checkpoint, CheckpointStore
from treecut.browser.retry_policy import BoundedRetry, RetryDecision
from treecut.browser.local_bridge import LocalBridge, LocalServiceStub
from treecut.browser.errors import (
    ErrorCategory,
    XhsWorkBrowserError,
    classify,
)
from treecut.browser.policies import InboxManager, QuarantineEntry
from treecut.browser.adapters import ADAPTERS

__all__ = [
    "__version__",
    "XhsWorkBrowserConfig", "load_config",
    "WorkspaceManager", "AccountBindingRecord", "default_profile_root",
    "AccountDetector", "AccountIdentity",
    "SessionDetector", "SessionCheckResult",
    "TaskEngine", "TaskResult",
    "Checkpoint", "CheckpointStore",
    "BoundedRetry", "RetryDecision",
    "LocalBridge", "LocalServiceStub",
    "ErrorCategory", "XhsWorkBrowserError", "classify",
    "InboxManager", "QuarantineEntry",
    "ADAPTERS",
]
