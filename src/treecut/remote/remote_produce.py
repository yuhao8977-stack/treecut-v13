"""Headless remote production that stays visible in the local desktop UI."""
from __future__ import annotations

import json
import time
import uuid


def _policy_path(paths):
    return paths.data_root / "config" / "remote_policy.json"


def _write_progress(paths, state: str, message: str, percent=None) -> None:
    try:
        policy_path = _policy_path(paths)
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
        except Exception:
            policy = {}
        policy["remote_job_state"] = state
        policy["remote_job_message"] = message
        policy["remote_job_percent"] = percent
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def run_remote_production(payload: dict) -> dict:
    """Run one production job and mirror it into the local job journal + policy file."""
    from treecut.application import CreativeRequest, ProductionService, open_job_journal
    from treecut.bootstrap import bootstrap
    from treecut.library import Catalog

    ctx = bootstrap()
    paths = ctx.paths
    selling = str(payload.get("selling_points", "")).strip()
    narration = str(payload.get("narration", "")).strip()
    if not selling or not narration:
        raise ValueError("卖点或文案不能为空")
    material_source = str(payload.get("material_source", "")).strip()
    if material_source:
        Catalog(paths.databases / "materials.db").scan(material_source)
    request = CreativeRequest(
        selling_points=selling,
        narration=narration,
        target_duration=float(payload.get("target_duration", 30)),
        clip_seconds=float(payload.get("clip_seconds", 4)),
        output_mp4=bool(payload.get("output_mp4", True)),
        output_jianying=bool(payload.get("output_jianying", False)),
        output_preset=payload.get("output_preset", "vertical"),
        narration_speed=float(payload.get("narration_speed", 1.0)),
    )
    journal = open_job_journal(paths.databases)
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "session_id": "remote:" + uuid.uuid4().hex[:8],
        "state": "queued",
        "message": "远程制作已提交",
        "created_at": time.time(),
        "result": None,
        "error": None,
        "percent": None,
        "request": payload,
    }
    journal.save(job, payload)

    def progress(message: str, percent=None) -> None:
        job["state"] = "running"
        job["message"] = message
        job["percent"] = percent
        journal.save(job)
        _write_progress(paths, "running", message, percent)

    try:
        result = ProductionService(ctx).create(request, progress)
        job.update(state="success", message="全部输出完成",
                   result=result.to_dict(), percent=100)
        journal.save(job)
        _write_progress(paths, "success", "远程制作完成", 100)
        return {"ok": True, "project": result.project_dir, "job_id": job_id}
    except Exception as exc:
        job.update(state="failed", message="制作失败",
                   error=f"{type(exc).__name__}: {exc}")
        journal.save(job)
        _write_progress(paths, "failed", str(exc), None)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
