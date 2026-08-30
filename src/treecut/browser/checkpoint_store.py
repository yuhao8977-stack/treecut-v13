"""XHS Work Browser V0.1 — Checkpoint Store（§20/21/47）。

任何任务必须支持 checkpoint；最小字段：
task_id / workspace_id / task_type / state / step / target / attempt / created_at / updated_at / last_error
不保存敏感凭证。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from treecut.browser.policies import utcnow_iso


@dataclass
class Checkpoint:
    task_id: str
    workspace_id: str
    task_type: str
    state: str = "RUNNING"
    step: str = "START"
    target: str = ""
    attempt: int = 1
    idempotency_key: str = ""
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)
    last_error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        allowed = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in allowed})


class CheckpointStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def save(self, checkpoint: Checkpoint) -> Path:
        checkpoint.updated_at = utcnow_iso()
        path = self.path_for(checkpoint.task_id)
        path.write_text(
            json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return path

    def load(self, task_id: str) -> Checkpoint | None:
        path = self.path_for(task_id)
        if not path.is_file():
            return None
        try:
            return Checkpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def unfinished(self, workspace_id: str | None = None) -> list[Checkpoint]:
        """§21 Crash Resume：发现 unfinished task（RUNNING/PAUSED/NEEDS_HUMAN 视为未完成）。"""
        result = []
        for path in sorted(self.root.glob("*.json")):
            cp = self.load(path.stem)
            if cp is None:
                continue
            if workspace_id and cp.workspace_id != workspace_id:
                continue
            if cp.state in {"RUNNING", "PAUSED", "NEEDS_HUMAN"}:
                result.append(cp)
        return result

    def clear(self, task_id: str) -> None:
        self.path_for(task_id).unlink(missing_ok=True)

    def last_timestamp(self, workspace_id: str | None = None) -> str | None:
        stamps = [cp.updated_at for cp in self.unfinished(workspace_id)]
        return max(stamps) if stamps else None
