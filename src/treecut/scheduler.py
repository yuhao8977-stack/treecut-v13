"""Persistent scheduled-production store and daemon thread."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path


class ScheduleStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text(json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")

    def _read(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")).get("items") or []
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, items: list[dict]) -> None:
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[dict]:
        return self._read()

    def add(self, run_at_ts: float, request: dict) -> str:
        item_id = uuid.uuid4().hex
        items = self._read()
        items.append({"id": item_id, "run_at_ts": run_at_ts, "state": "pending", "request": request})
        self._write(items)
        return item_id

    def remove(self, item_id: str) -> None:
        items = [item for item in self._read() if item.get("id") != item_id]
        self._write(items)

    def due(self, now_ts: float) -> list[dict]:
        return [item for item in self._read()
                if item.get("state") == "pending" and float(item.get("run_at_ts") or 0) <= now_ts]

    def mark_done(self, item_id: str) -> None:
        items = self._read()
        for item in items:
            if item.get("id") == item_id:
                item["state"] = "done"
        self._write(items)


class ScheduleThread(threading.Thread):
    def __init__(self, store: ScheduleStore, on_due, interval: float = 30.0):
        super().__init__(daemon=True)
        self.store = store
        self.on_due = on_due
        self.interval = interval

    def run(self) -> None:
        while True:
            for item in self.store.due(time.time()):
                self.store.mark_done(item["id"])
                try:
                    self.on_due(item.get("request") or {})
                except Exception:
                    logging.getLogger("treecut").exception("定时任务执行失败: %s", item.get("id"))
            time.sleep(self.interval)
