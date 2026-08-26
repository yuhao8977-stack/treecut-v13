"""TreeCut Phase 2 — Segment 认知人工审核 UI。

左：素材信息 + 视频播放（当前 segment ±3s 上下文）
中：L1 机器证据
右：L2 AI 判断 + L3 人工确认（保存人工最终值，不覆盖 L2）
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.services.segment_cognition import SegmentCognitionService

SCENES = ("工厂", "展厅", "安装现场", "厨房空间", "客户家", "其他", "UNKNOWN")
PRODUCTS = ("岛台", "伸缩岛台", "餐边柜", "吧台", "餐桌", "其他", "UNKNOWN")
MATERIALS = ("岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "其他", "UNKNOWN")
FUNCTIONS = ("伸缩", "收纳", "抽屉", "轨道插座", "隐藏电器", "水吧", "其他", "UNKNOWN")
ACTIONS = ("拉出/展开", "收纳/关闭", "讲解/演示", "安装", "其他", "UNKNOWN")
SHOT_TYPES = ("全景", "中景", "近景", "特写", "其他", "UNKNOWN")
PEOPLE = ("yes", "no", "unknown")


class SegmentCognitionReviewApp(tk.Tk):
    """Segment 认知审核界面（L2 vs L3 + Boundary 审核）。"""

    def __init__(self, db_path: str | Path | None = None,
                 queue_limit: int = 300):
        super().__init__()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self.svc = SegmentCognitionService(self.db_path)
        self.queue = self._load_queue(queue_limit)
        self.idx = 0
        self.current: dict | None = None
        self.reviewed_count = self._reviewed_count()

        self.title("TreeCut Phase 2 - Segment 认知人工审核")
        self.geometry("1500x950")
        self.configure(bg="#f0f0f0")
        self._build_layout()
        if self.queue:
            self._load(0)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_queue(self, limit: int) -> list[dict]:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        # 未审核 = 无 human_annotations 记录 或 无 boundary review
        rows = conn.execute(
            "SELECT target_id, target_type FROM semantic_annotations "
            "WHERE target_type='segment' AND status='candidate' "
            "AND target_id NOT IN (SELECT target_id FROM human_annotations) "
            "LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _reviewed_count(self) -> int:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        n = conn.execute(
            "SELECT COUNT(DISTINCT target_id) FROM human_annotations").fetchone()[0]
        conn.close()
        return n

    def _build_layout(self) -> None:
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill=tk.X, padx=8, pady=6)
        self.pos = tk.Label(top, text="", bg="#f0f0f0",
                            font=("Microsoft YaHei", 11, "bold"))
        self.pos.pack(side=tk.LEFT)
        self.progress = tk.Label(top, text=f"已审核 {self.reviewed_count}/300",
                                 bg="#f0f0f0", font=("Microsoft YaHei", 10))
        self.progress.pack(side=tk.LEFT, padx=16)
        ttk.Button(top, text="上一题", command=lambda: self._load(self.idx - 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="下一题", command=lambda: self._load(self.idx + 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="跳过", command=lambda: self._load(self.idx + 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="✓ 保存人工裁决", command=self._save).pack(side=tk.RIGHT, padx=8)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左：素材信息
        left = ttk.Frame(paned, width=400)
        paned.add(left, weight=0)
        self.info = tk.Text(left, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.info.pack(fill=tk.BOTH, expand=True)
        ttk.Button(left, text="▶ 播放视频（含上下文±3s）",
                   command=self._play).pack(fill=tk.X, padx=6, pady=4)

        # 中：L1 证据
        mid = ttk.Frame(paned)
        paned.add(mid, weight=1)
        tk.Label(mid, text="L1 机器证据（不可改）", bg="#e8e8f8",
                 font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W)
        self.ev = tk.Text(mid, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.ev.pack(fill=tk.BOTH, expand=True)

        # 右：L2 vs L3
        right = ttk.Frame(paned, width=460)
        paned.add(right, weight=0)
        tk.Label(right, text="L2 AI 判断（绿） / L3 人工确认（填）",
                 bg="#f0f0f0", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W)

        self.l2_vars = {}
        self.l3_vars = {}
        form = ttk.Frame(right)
        form.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        fields = [("scene", "场景", SCENES), ("product", "产品", PRODUCTS),
                  ("material", "材质", MATERIALS), ("function", "功能", FUNCTIONS),
                  ("action", "动作", ACTIONS), ("shot_type", "镜头类型", SHOT_TYPES)]
        row = 0
        for key, label, options in fields:
            tk.Label(form, text=f"L2 {label}", bg="#d8f0d8",
                     font=("Microsoft YaHei", 8)).grid(row=row, column=0, sticky=tk.W, pady=2)
            v2 = tk.StringVar()
            tk.Entry(form, textvariable=v2, state="readonly", readonlybackground="#eef6ee",
                     width=24).grid(row=row, column=1, padx=4)
            self.l2_vars[key] = v2
            row += 1
            tk.Label(form, text=f"L3 {label}", bg="#f0f0f0",
                     font=("Microsoft YaHei", 8)).grid(row=row, column=0, sticky=tk.W, pady=2)
            v3 = tk.StringVar()
            ttk.Combobox(form, textvariable=v3, values=options, width=22).grid(
                row=row, column=1, padx=4)
            self.l3_vars[key] = v3
            row += 1
        # people + 质量 + 备注
        tk.Label(form, text="L3 人物", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.l3_people = tk.StringVar()
        ttk.Combobox(form, textvariable=self.l3_people, values=PEOPLE, width=22).grid(
            row=row, column=1, padx=4)
        row += 1
        tk.Label(form, text="L3 质量(0-100)", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.l3_quality = tk.IntVar(value=0)
        ttk.Spinbox(form, from_=0, to=100, textvariable=self.l3_quality, width=8).grid(
            row=row, column=1, padx=4)
        row += 1
        tk.Label(form, text="备注", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.l3_comment = tk.StringVar()
        tk.Entry(form, textvariable=self.l3_comment, width=30).grid(row=row, column=1, padx=4)
        row += 1

        # --- Boundary 审核区（Phase 2 Validation Closure） ---
        tk.Label(form, text="— Segment Boundary 审核（是/否） —",
                 bg="#fff3cd", font=("Microsoft YaHei", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        row += 1
        self.boundary_vars = {}
        boundary_fields = [
            ("boundary_start_ok", "起点正常"),
            ("boundary_end_ok", "终点正常"),
            ("action_complete", "动作完整"),
            ("semantic_complete", "语义完整"),
            ("cut_mid_action", "动作被切断"),
            ("cut_mid_sentence", "语句被切断"),
            ("usable_as_edit_unit", "可作为剪辑单位"),
        ]
        for key, label in boundary_fields:
            tk.Label(form, text=label, bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
            var = tk.StringVar()
            ttk.Combobox(form, textvariable=var, values=("是", "否", "待定"), width=22).grid(
                row=row, column=1, padx=4)
            self.boundary_vars[key] = var
            row += 1
        tk.Label(form, text="边界备注", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.boundary_comment = tk.StringVar()
        tk.Entry(form, textvariable=self.boundary_comment, width=30).grid(row=row, column=1, padx=4)

    def _load(self, idx: int) -> None:
        if not self.queue:
            self.pos.config(text="无可审核（已全部裁决）")
            return
        self.idx = idx % len(self.queue)
        q = self.queue[self.idx]
        self.current = q
        seg_id = q["target_id"]
        self.pos.config(text=f"{self.idx + 1}/{len(self.queue)}  {seg_id[:16]}")

        # 证据 + L2
        ev = self.svc.evidence_builder.build(seg_id)
        ann = self.svc.get_annotation(seg_id)
        info = [f"segment: {seg_id}", f"asset: {ev.asset_id if ev else '?'}",
                f"range: {ev.start_ms}-{ev.end_ms}ms" if ev else ""]
        if ev and ev.technical:
            info.append(f"asset dur: {ev.technical.get('asset_duration')}s")
        self.info.delete("1.0", tk.END)
        self.info.insert(tk.END, "\n".join(info))

        ev_txt = []
        if ev:
            ev_txt.append(f"ASR: {ev.asr_text[:200]}")
            ev_txt.append(f"OCR: {ev.ocr_text[:150]}")
            ev_txt.append(f"关键帧: {len(ev.keyframes)} 个 "
                          f"{[k['timestamp_ms'] for k in ev.keyframes[:4]]}")
            ev_txt.append(f"场景语义: {ev.scene_semantics[:3]}")
            ev_txt.append(f"CLIP: {ev.clip_tags[:5]}")
            ev_txt.append(f"技术: {ev.technical}")
        self.ev.delete("1.0", tk.END)
        self.ev.insert(tk.END, "\n".join(ev_txt))

        if ann:
            for key in ("scene", "product", "material", "function", "action", "shot_type"):
                self.l2_vars[key].set(ann.get(key, "") or "UNKNOWN")
                self.l3_vars[key].set("")
            self.l3_people.set("")
            self.l3_quality.set(0)
            self.l3_comment.set("")
            self._ann_id = ann.get("annotation_id", 0)
        else:
            for v in self.l2_vars.values():
                v.set("")
            self._ann_id = 0
        for v in self.boundary_vars.values():
            v.set("待定")
        self.boundary_comment.set("")

    def _play(self) -> None:
        if not self.current:
            return
        ev = self.svc.evidence_builder.build(self.current["target_id"])
        if ev:
            from treecut.services.identity import AssetRepository
            path = AssetRepository(self.db_path).resolve_path(ev.asset_id)
            if path and os.path.exists(path):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo("提示", f"文件不可达: {path}")

    def _save(self) -> None:
        if not self.current or not self._ann_id:
            messagebox.showwarning("提示", "无当前注释")
            return
        values = {k: v.get() for k, v in self.l3_vars.items()}
        values["people_presence"] = self.l3_people.get()
        values["quality_score"] = self.l3_quality.get()
        values["comment"] = self.l3_comment.get()
        self.svc.add_human_adjudication(
            self.current["target_id"], self._ann_id, values,
            operator=os.environ.get("USERNAME", ""))
        # Boundary 审核写入 segment_boundary_reviews
        self._save_boundary(self.current["target_id"], self._ann_id)
        self.reviewed_count += 1
        self.progress.config(text=f"已审核 {self.reviewed_count}/300")
        self._load(self.idx + 1)

    def _save_boundary(self, segment_id: str, annotation_id: int) -> None:
        """保存 Boundary 审核（是=1 否=0 待定=-1）。"""
        import sqlite3
        conv = {"是": 1, "否": 0, "待定": -1}
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute(
            "INSERT OR REPLACE INTO segment_boundary_reviews(segment_id,annotation_id,"
            "boundary_start_ok,boundary_end_ok,action_complete,semantic_complete,"
            "cut_mid_action,cut_mid_sentence,usable_as_edit_unit,boundary_comment,"
            "operator,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (segment_id, annotation_id,
             conv.get(self.boundary_vars["boundary_start_ok"].get(), -1),
             conv.get(self.boundary_vars["boundary_end_ok"].get(), -1),
             conv.get(self.boundary_vars["action_complete"].get(), -1),
             conv.get(self.boundary_vars["semantic_complete"].get(), -1),
             conv.get(self.boundary_vars["cut_mid_action"].get(), -1),
             conv.get(self.boundary_vars["cut_mid_sentence"].get(), -1),
             conv.get(self.boundary_vars["usable_as_edit_unit"].get(), -1),
             self.boundary_comment.get(),
             os.environ.get("USERNAME", ""), time.time()))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    app = SegmentCognitionReviewApp()
    app.mainloop()
