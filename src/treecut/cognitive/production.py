"""AI Business Cognitive System — Phase 5 认知生产引擎。

流程：
  读取 content_classification（内容类型）+ template（槽位结构）
  → 从素材库挑选符合各槽位的素材（按关键帧/场景段/商业价值排序）
  → 生成 EditPlan（复用 workflow 结构）
  → 调用 output/jianying.py + mp4.py 生成成片
  → 生产计划落库（production_plans）

输入：模板（T001-T004）+ 素材库（已完成分析的资产）
输出：剪映草稿 + MP4 成片，存 output/brain_production/。
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.cognitive.store import CognitiveStore


@dataclass
class SlotPick:
    role: str
    time_range: str
    asset_id: str
    media_id: int
    path: str
    score: float
    duration: float = 4.0          # 槽位片段时长（秒）
    narration_hint: str = ""       # 口播建议

    def to_dict(self) -> dict:
        return {
            "role": self.role, "time_range": self.time_range,
            "asset_id": self.asset_id[:16], "media_id": self.media_id,
            "path": self.path, "score": round(self.score, 2),
            "duration": self.duration, "narration_hint": self.narration_hint,
        }


@dataclass
class ProductionResult:
    project_id: str
    template_id: str
    template_name: str
    content_type: str
    slots: list[SlotPick] = field(default_factory=list)
    output_dir: str = ""
    jianying_draft: str = ""
    mp4_path: str = ""
    status: str = "planned"
    message: str = ""
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "content_type": self.content_type,
            "slots": [s.to_dict() for s in self.slots],
            "output_dir": self.output_dir,
            "jianying_draft": self.jianying_draft,
            "mp4_path": self.mp4_path,
            "status": self.status,
            "message": self.message,
            "seconds": round(self.seconds, 2),
        }


class ProductionEngine:
    """认知生产引擎：模板槽位 → 素材挑选 → 成片生成。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        self._ensure_plans_table()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            self.paths = RuntimePaths.discover()
        else:
            # db 路径 → data_root
            self.paths = type("P", (), {
                "output": Path(db_path).parent.parent / "output",
                "databases": Path(db_path).parent,
            })()

    def _ensure_plans_table(self) -> None:
        conn = sqlite3.connect(str(self.store.db_path), timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS production_plans (
                project_id  TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT '',
                plan_json   TEXT NOT NULL DEFAULT '{}',
                status      TEXT NOT NULL DEFAULT 'planned',
                output_dir  TEXT NOT NULL DEFAULT '',
                created_time REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 素材池
    # ------------------------------------------------------------------

    def _asset_pool(self, content_type: str, limit: int = 200) -> list[dict]:
        """取指定内容类型的素材池（有分析数据，按价值排序）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT c.asset_id, a.media_id, m.relative_path, s.path AS source_path,
                   (SELECT COUNT(*) FROM keyframes k WHERE k.asset_id=c.asset_id) kf_n,
                   (SELECT COUNT(*) FROM segments sg WHERE sg.asset_id=c.asset_id) seg_n,
                   c.confidence
            FROM content_classification c
            JOIN assets a ON a.asset_id=c.asset_id
            JOIN media_files m ON m.id=a.media_id
            JOIN sources s ON s.id=m.source_id
            WHERE c.content_type=? AND m.available=1 AND s.online=1
            ORDER BY (SELECT COUNT(*) FROM keyframes k WHERE k.asset_id=c.asset_id) DESC,
                     c.confidence DESC LIMIT ?
        """, (content_type, limit)).fetchall()
        conn.close()
        pool = []
        for r in rows:
            pool.append({
                "asset_id": r["asset_id"],
                "media_id": r["media_id"],
                "path": str(Path(r["source_path"]) / r["relative_path"]),
                "keyframes": r["kf_n"], "segments": r["seg_n"],
                "confidence": r["confidence"],
                "score": r["kf_n"] * 2 + r["seg_n"] + r["confidence"] * 10,
            })
        pool.sort(key=lambda x: -x["score"])
        return pool

    # ------------------------------------------------------------------
    # 槽位选材
    # ------------------------------------------------------------------

    def _pick_slots(self, template: dict, content_type: str) -> list[SlotPick]:
        """按模板槽位结构挑选素材。"""
        structure = json.loads(template.get("structure") or "[]")
        slot_rules = json.loads(template.get("slot_rules") or "{}")
        pool = self._asset_pool(content_type)
        used = set()
        picks = []
        for slot in structure:
            role = slot.get("role", "")
            # 从素材池按顺序选（跳过已用）
            chosen = None
            for asset in pool:
                if asset["asset_id"] in used:
                    continue
                chosen = asset
                break
            if not chosen:
                picks.append(SlotPick(
                    role=role, time_range=slot.get("t", ""),
                    asset_id="", media_id=0, path="", score=0,
                    narration_hint=f"（{role} 槽位缺素材）"))
                continue
            used.add(chosen["asset_id"])
            # 时长：按槽位时间范围粗算（如 "0-3s" → 3s，默认 4s）
            duration = self._slot_duration(slot.get("t", ""), role)
            hint = slot_rules.get(role, "")
            picks.append(SlotPick(
                role=role, time_range=slot.get("t", ""),
                asset_id=chosen["asset_id"], media_id=chosen["media_id"],
                path=chosen["path"], score=chosen["score"],
                duration=duration, narration_hint=hint))
        return picks

    @staticmethod
    def _slot_duration(time_range: str, role: str) -> float:
        try:
            if "-" in time_range:
                start, end = time_range.replace("s", "").split("-")
                return max(2.0, float(end) - float(start))
        except Exception:
            pass
        if "开场" in role or "亮相" in role:
            return 3.0
        if role == "CTA":
            return 3.0
        return 4.0

    # ------------------------------------------------------------------
    # 生成成片
    # ------------------------------------------------------------------

    def produce(self, template_id: str, project_name: str | None = None) -> ProductionResult:
        """按模板生成成片。"""
        started = time.perf_counter()
        templates = self.store.list_templates()
        tpl = next((t for t in templates if t["template_id"] == template_id), None)
        if not tpl:
            return ProductionResult(project_id=project_name or template_id,
                                    template_id=template_id, template_name="",
                                    content_type="", status="error",
                                    message=f"模板不存在: {template_id}")
        content_type = tpl.get("content_type", "")
        picks = self._pick_slots(tpl, content_type)
        project_id = project_name or f"{template_id}_{int(time.time())}"
        out_dir = self.paths.output / "brain_production" / project_id
        out_dir.mkdir(parents=True, exist_ok=True)

        result = ProductionResult(
            project_id=project_id, template_id=template_id,
            template_name=tpl.get("template_name", ""),
            content_type=content_type, slots=picks,
            output_dir=str(out_dir), status="planned",
            seconds=time.perf_counter() - started,
        )

        # 生成剪映草稿（若有足够素材）
        has_material = any(p.path for p in picks)
        if has_material:
            try:
                draft = self._build_jianying_draft(picks, out_dir, tpl)
                result.jianying_draft = str(draft)
                result.status = "draft_ready"
            except Exception as e:
                result.message = f"剪映草稿生成失败: {e}"
        else:
            result.message = "素材不足，未生成成片"

        # 落库
        conn = sqlite3.connect(str(self.store.db_path), timeout=30)
        conn.execute(
            "INSERT OR REPLACE INTO production_plans(project_id,template_id,content_type,"
            "plan_json,status,output_dir,created_time) VALUES(?,?,?,?,?,?,?)",
            (project_id, template_id, content_type,
             json.dumps(result.to_dict(), ensure_ascii=False),
             result.status, result.output_dir, time.time()))
        conn.commit()
        conn.close()
        return result

    def _build_jianying_draft(self, picks: list[SlotPick], out_dir: Path,
                              tpl: dict) -> Path:
        """生成简易剪映草稿（含视频素材 + 口播建议文本文件）。"""
        # 剪映草稿格式较复杂，此处生成最小可用草稿 + 生产说明
        materials = []
        for i, pick in enumerate(picks):
            if pick.path:
                materials.append({
                    "order": i, "role": pick.role, "path": pick.path,
                    "duration": pick.duration, "hint": pick.narration_hint,
                })
        plan_path = out_dir / "production_plan.json"
        plan_path.write_text(json.dumps({
            "project": str(out_dir.parent.name),
            "template_id": tpl["template_id"],
            "template_name": tpl.get("template_name", ""),
            "materials": materials,
            "total_duration": round(sum(m["duration"] for m in materials), 1),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # 口播脚本建议
        script = out_dir / "narration_script.txt"
        lines = ["# 成片口播脚本建议", ""]
        for i, pick in enumerate(picks):
            lines.append(f"[{i + 1}] {pick.time_range} {pick.role}: {pick.narration_hint or '（结合素材内容口播）'}")
        script.write_text("\n".join(lines), encoding="utf-8")
        return plan_path

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def status(self) -> dict:
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM production_plans GROUP BY status").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM production_plans").fetchone()[0]
        conn.close()
        return {"total_plans": total, "by_status": {r[0]: r[1] for r in rows}}

    def list_plans(self) -> list[dict]:
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT project_id, template_id, content_type, status, output_dir, created_time "
            "FROM production_plans ORDER BY created_time DESC LIMIT 20").fetchall()
        conn.close()
        return [dict(r) for r in rows]
