"""XHS Work Browser V0.1 — 数据与策略常量（§28-30/38-40）。

只定义 policy/schema，不实现业务抓取。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---- §28 Inbox 标准目录 ----
INBOX_SUBDIRS = (
    "creator",
    "spotlight",
    "media_metadata",
    "published_media",
    "processed",
    "quarantine",
)

# ---- §38 RAW SNAPSHOT = IMMUTABLE ----
RAW_SNAPSHOT_POLICY = (
    "RAW SNAPSHOT = IMMUTABLE：任何采集产生的原始快照一经落盘不得覆盖、不得原地修改；"
    "后续处理只能产生新的派生文件。"
)

# ---- §39 媒体原子文件：filename.mp4.part → 完成并验证 → filename.mp4 ----
MEDIA_ATOMIC_FILE_POLICY = (
    "MEDIA ATOMIC FILE：下载一律先写 <name>.part，完成并通过验证后才原子重命名为最终文件。"
    "V0.1 不下载任何媒体，仅建立策略。"
)


def atomic_partial_name(final_name: str) -> str:
    return f"{final_name}.part"


# ---- §40 Validation Gate：Browser 产物 → Inbox → 校验 → PASS→TreeCut / FAIL→Quarantine ----
VALIDATION_GATE_POLICY = (
    "VALIDATION GATE：Browser 产物只进 Local Inbox，不直接写入核心 DB；"
    "经 Validation Gate 校验：PASS → TreeCut，FAIL → quarantine/。"
)

# ---- §30 Idempotency ----
IDEMPOTENCY_POLICY = (
    "IDEMPOTENCY：同一 task（同一 idempotency_key）重复执行不得产生多个重复业务 Commit。"
    "V0.1 设计 idempotency_key 字段，不实现完整业务去重。"
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- §29 Quarantine metadata schema ----
@dataclass
class QuarantineEntry:
    reason: str
    source: str
    workspace: str
    task_id: str = ""
    timestamp: str = field(default_factory=utcnow_iso)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "source": self.source,
            "workspace": self.workspace,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "extra": self.extra,
        }


# ---- §28 InboxManager：只建目录与接口，V0.1 可全空 ----
class InboxManager:
    def __init__(self, inbox_root: Path):
        self.root = Path(inbox_root)

    def ensure(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in INBOX_SUBDIRS:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        return self.root

    def quarantine_path(self) -> Path:
        return self.root / "quarantine"

    def published_media_path(self, workspace_id: str) -> Path:
        """§18：正式媒体不进桌面/Downloads → treecut_inbox/published_media/{workspace}/"""
        path = self.root / "published_media" / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_quarantine(self, entry: QuarantineEntry) -> Path:
        """异常数据不得直接丢失，统一进入 quarantine/（§29）。"""
        self.ensure()
        path = self.quarantine_path() / f"{entry.timestamp.replace(':', '-')}_{entry.workspace}_{len(list(self.quarantine_path().glob('*.json')))}.json"
        path.write_text(
            __import__("json").dumps(entry.to_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return path
