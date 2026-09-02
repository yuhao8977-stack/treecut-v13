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
            self.install_root = self.paths.install_root
        else:
            # db 路径 → data_root/install_root（从 db 位置推导）
            data_root = Path(db_path).parent.parent
            self.paths = type("P", (), {
                "output": data_root / "output",
                "databases": Path(db_path).parent,
                "data_root": data_root,
            })()
            # 安装根：data_root = <install>/runtime_data/temp/batch1 → parents[2] = <install>
            self.install_root = data_root.parents[2] if "TreeCut_v13" in str(data_root) \
                else Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")

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
        """取指定内容类型的素材池（有分析数据，按价值排序）。

        LEGACY_ASSET_LEVEL_PRODUCTION（Phase 1 标记）：
        本方法以 asset_id 为选材单位（整素材截取），不符合 Canonical 设计
        （宪法 2：自动生产最小单位=segment_id）。按架构路线，Phase 6 将
        以 SegmentRepository 替换本链路。Phase 1 仅标记，不重构选材算法。
        """
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

    def produce(self, template_id: str, project_name: str | None = None,
                render: bool = True, narration_text: str | None = None,
                mock_narration: bool = False) -> ProductionResult:
        """按模板生成成片（render=True 时渲染 MP4 + 剪映草稿）。

        V0.8.4：narration_text 提供时走真实 TTS/SRT（ProductionNarrationAdapter）；
        mock_narration=True 时才允许静音占位（显式测试用）；否则不冒充 NARRATION_READY。
        """
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

        has_material = any(p.path for p in picks)
        if not has_material:
            result.message = "素材不足，未生成成片"
            self._save_plan(result)
            return result

        try:
            # 1) 生产计划文件 + 口播脚本
            self._build_plan_files(picks, out_dir, tpl)

            if render:
                # 2) 构建 EditPlan 并渲染
                edit_plan = self._build_edit_plan(picks)
                rendered = self._render(edit_plan, out_dir)
                result.jianying_draft = rendered.get("draft", "")
                result.mp4_path = rendered.get("mp4", "")
                if rendered.get("narration_failed"):
                    # V0.8.4：配音/字幕失败不得标成功
                    result.status = "partial"
                    result.message = (f"成片为 PARTIAL（无真实配音/字幕）: "
                                      f"narration_status={rendered.get('narration_status')}")
                else:
                    result.status = "rendered" if result.mp4_path else "draft_ready"
                    if result.mp4_path:
                        result.message = f"成片已生成: {Path(result.mp4_path).name}"
            else:
                result.status = "draft_ready"
                result.message = "计划已生成（未渲染）"
        except Exception as e:
            result.status = "error"
            result.message = f"生产失败: {type(e).__name__}: {e}"

        self._save_plan(result)
        return result

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _build_edit_plan(self, picks: list[SlotPick]):
        """构建 EditPlan（复用 workflow.EditSegment）。"""
        from treecut.workflow.planning import EditPlan, EditSegment
        segments = []
        timeline = 0.0
        for i, pick in enumerate(picks):
            if not pick.path:
                continue
            duration = pick.duration
            # 从素材取真实时长（ffprobe 粗查，失败用默认）
            real_dur = self._probe_duration(pick.path) or duration
            use_dur = min(duration, max(2.0, real_dur * 0.8))
            segments.append(EditSegment(
                order=i, media_id=pick.media_id, path=pick.path,
                category=pick.role, source_start=0.0, source_end=use_dur,
                timeline_start=timeline, timeline_end=timeline + use_dur,
                match_score=pick.score, matched_terms=(pick.role,),
            ))
            timeline += use_dur
        return EditPlan(
            requested_duration=timeline, planned_duration=timeline,
            complete=True, warnings=(), segments=tuple(segments),
        )

    def _probe_duration(self, path: str) -> float | None:
        """用 ffprobe 查素材时长（失败返回 None）。"""
        try:
            import subprocess
            ffprobe = self._ffmpeg_root() / "ffprobe.exe"
            out = subprocess.run(
                [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=15)
            if out.returncode == 0 and out.stdout.strip():
                return float(out.stdout.strip())
        except Exception:
            pass
        return None

    def _ffmpeg_root(self):
        """定位 tools/win32（含 ffmpeg/ffprobe）。"""
        tools = self.install_root / "tools" / "win32"
        if tools.exists():
            return tools
        return self.install_root

    def _render(self, edit_plan, out_dir: Path) -> dict:
        """渲染 MP4 + 剪映草稿（草稿需 narration/bgm/srt，缺失则跳过）。"""
        from treecut.output.mp4 import render_video_plan
        tools = self._ffmpeg_root()
        ffmpeg = tools / "ffmpeg.exe"
        ffprobe = tools / "ffprobe.exe"

        result = {}
        # MP4 渲染（preview 规格，竖屏 540x960）
        if ffmpeg.exists():
            try:
                mp4_out = out_dir / "preview.mp4"
                render_video_plan(edit_plan, mp4_out, ffmpeg, ffprobe,
                                  profile="preview")
                result["mp4"] = str(mp4_out)
            except Exception as e:
                print(f"  [MP4 渲染跳过] {type(e).__name__}: {e}")
        # 剪映草稿（需 narration/bgm/srt 文件；认知链路无 TTS/选曲时跳过）
        try:
            from treecut.output.jianying import build_jianying_draft
            draft_dir = out_dir / "jianying_draft"
            draft_dir.mkdir(parents=True, exist_ok=True)
            narration = out_dir / "narration.wav"
            bgm = out_dir / "bgm.mp3"
            srt = out_dir / "narration.srt"
            narration_status = "NOT_REQUESTED"
            if narration_text and not narration.exists():
                # V0.8.4：真实 TTS/SRT（不落静音占位）
                from treecut.output.production_narration import ProductionNarrationAdapter
                art = ProductionNarrationAdapter().generate(narration_text, out_dir,
                                                            mock=mock_narration)
                narration_status = art.status
                if art.status == "NARRATION_READY":
                    narration, srt = art.wav, art.srt
                elif not mock_narration:
                    narration_status = art.status or "TTS_GENERATION_FAILED"
                try:
                    (out_dir / "narration_metadata.json").write_text(
                        json.dumps(art.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
                except Exception:
                    pass
            if not narration.exists():
                if mock_narration or not narration_text:
                    # 占位仅保留给显式 MOCK / 计划结构测试（V0.8.4：生产模式禁止静音冒充成功）
                    narration_status = narration_status if narration_status != "NOT_REQUESTED" else (
                        "MOCK" if mock_narration else "NOT_REQUESTED")
                    import subprocess as _sp
                    _sp.run([str(ffmpeg), "-y", "-f", "lavfi", "-i",
                             "anullsrc=r=44100:cl=mono", "-t", "2",
                             str(narration)], capture_output=True, timeout=60)
                else:
                    narration_status = "TTS_GENERATION_FAILED"
            if not bgm.exists():
                # 静音 BGM 占位（BGM 非本阶段目标；保持结构兼容）
                import subprocess as _sp
                _sp.run([str(ffmpeg), "-y", "-f", "lavfi", "-i",
                         "anullsrc=r=44100:cl=mono", "-t", "2",
                         str(bgm)], capture_output=True, timeout=60)
            if not srt.exists():
                if narration_status in ("NARRATION_READY", "SUBTITLE_TEXT_COVERAGE_LOW"):
                    pass  # adapter 已写入真实 SRT
                else:
                    srt.write_text("", encoding="utf-8")
            build_jianying_draft(
                edit_plan, draft_dir,
                narration_wav=narration, bgm=bgm, subtitle_srt=srt,
                ffmpeg=ffmpeg,
            )
            result["draft"] = str(draft_dir)
            result["narration_status"] = narration_status
            result["narration_failed"] = narration_status in (
                "TTS_GENERATION_FAILED", "SUBTITLE_GENERATION_FAILED", "TTS_DURATION_ANOMALY")
            if result["narration_failed"]:
                result["draft"] = ""
        except Exception as e:
            print(f"  [剪映草稿跳过] {type(e).__name__}: {e}")
        return result

    def _build_plan_files(self, picks: list[SlotPick], out_dir: Path,
                          tpl: dict) -> None:
        """生产计划 JSON + 口播脚本（原 produce 的落盘逻辑）。"""
        materials = [{"order": i, "role": p.role, "path": p.path,
                      "duration": p.duration, "hint": p.narration_hint}
                     for i, p in enumerate(picks) if p.path]
        plan_path = out_dir / "production_plan.json"
        plan_path.write_text(json.dumps({
            "project": str(out_dir.parent.name),
            "template_id": tpl["template_id"],
            "template_name": tpl.get("template_name", ""),
            "materials": materials,
            "total_duration": round(sum(m["duration"] for m in materials), 1),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        script = out_dir / "narration_script.txt"
        lines = ["# 成片口播脚本建议", ""]
        for i, pick in enumerate(picks):
            lines.append(f"[{i + 1}] {pick.time_range} {pick.role}: "
                         f"{pick.narration_hint or '（结合素材内容口播）'}")
        script.write_text("\n".join(lines), encoding="utf-8")

    def _save_plan(self, result: ProductionResult) -> None:
        conn = sqlite3.connect(str(self.store.db_path), timeout=30)
        conn.execute(
            "INSERT OR REPLACE INTO production_plans(project_id,template_id,content_type,"
            "plan_json,status,output_dir,created_time) VALUES(?,?,?,?,?,?,?)",
            (result.project_id, result.template_id, result.content_type,
             json.dumps(result.to_dict(), ensure_ascii=False),
             result.status, result.output_dir, time.time()))
        conn.commit()
        conn.close()

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
