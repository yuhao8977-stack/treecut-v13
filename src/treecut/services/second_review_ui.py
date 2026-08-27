"""TreeCut Phase 2.5 — SECOND_REVIEW_V1 二次复核 UI。

关键设计：隐藏首次人工答案与 AI 答案（防止锚定），
二次复核结果保存到 human_annotation_v2（不覆盖 v1）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.services.annotation_governance import AnnotationService

SCENES = ("工厂", "工厂展示区", "加工车间", "客户住宅", "展厅", "安装现场", "其他", "UNKNOWN")
PRODUCTS = ("岛台", "伸缩岛台", "悬浮岛台", "落地岛台", "吧台", "餐边柜", "茶桌", "其他", "UNKNOWN")
MATERIALS = ("岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃", "其他", "UNKNOWN")
FUNCTIONS = ("伸缩", "收纳", "用电", "办公", "多人就餐", "水吧", "嵌入电器", "其他", "UNKNOWN")
ACTIONS = ("拉出", "展开", "收起", "打开抽屉", "关闭抽屉", "打开柜门", "插电", "人物讲解", "静态展示", "其他", "UNKNOWN")
SHOT_TYPES = ("全景", "中景", "近景", "特写", "人物讲解", "功能演示", "空间扫镜", "其他", "UNKNOWN")
PEOPLE = ("yes", "no", "unknown")
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
REVIEW_STATUS = ("REVIEWED", "NEEDS_SECOND_REVIEW", "GOLD", "EXCLUDED")

# Phase 2.5.1 空提交治理：关键人工字段全空禁止 REVIEWED
REQUIRED_KEYS = ("scene", "product", "material", "function", "action",
                 "shot_type", "people_presence")


def validate_submission(values: dict, human_confidence: str,
                        review_status: str) -> tuple[bool, str, str]:
    """审核提交校验（Phase 2.5.1）。

    返回 (是否通过, 错误/提示信息, 调整后的 review_status)。
    规则：
      1) human_confidence / review_status 必选（禁止无感默认）；
      2) 关键字段全空 → 禁止 REVIEWED，自动降级 NEEDS_SECOND_REVIEW；
      3) EXCLUDED 仅当备注含 UNPLAYABLE（视频无法播放）允许空字段。
    """
    conf = (human_confidence or "").strip().upper()
    status = (review_status or "").strip().upper()
    if conf not in CONFIDENCE:
        return False, "必须主动选择人工置信度（HIGH/MEDIUM/LOW）", status
    if status not in REVIEW_STATUS:
        return False, "必须主动选择审核状态", status
    filled = sum(1 for k in REQUIRED_KEYS if (values.get(k) or "").strip() not in ("", "UNKNOWN"))
    if filled == 0:
        note = (values.get("comment") or "").upper()
        if status == "EXCLUDED" and ("UNPLAYABLE" in note or "无法播放" in (values.get("comment") or "")):
            return True, "EXCLUDED（UNPLAYABLE）", status
        if status == "REVIEWED" or status == "GOLD":
            return False, "关键字段全空，禁止 REVIEWED/GOLD；已自动置为 NEEDS_SECOND_REVIEW", "NEEDS_SECOND_REVIEW"
        return True, "关键字段全空，仅允许 NEEDS_SECOND_REVIEW/EXCLUDED", status
    return True, "", status


class SecondReviewApp(tk.Tk):
    """SECOND_REVIEW_V1 二次复核界面。"""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self.svc = AnnotationService(self.db_path)
        self.manifest = self._load_manifest()
        self.queue = [s for s in self.manifest["segments"]
                      if not self._already_v2(s)]
        self.idx = 0
        self.current_seg: str | None = None
        self.current_v1_id = 0

        self.title("TreeCut Phase 2.5 - SECOND_REVIEW_V1 二次复核")
        self.geometry("1400x900")
        self.configure(bg="#f0f0f0")
        self._build_layout()
        if self.queue:
            self._load(0)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_manifest(self) -> dict:
        mf = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\SECOND_REVIEW_V1_MANIFEST.json")
        if mf.exists():
            return json.loads(mf.read_text(encoding="utf-8"))
        return {"segments": []}

    def _already_v2(self, seg_id: str) -> bool:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        n = conn.execute("SELECT COUNT(*) FROM human_annotation_v2 WHERE segment_id=?",
                         (seg_id,)).fetchone()[0]
        conn.close()
        return n > 0

    def _build_layout(self) -> None:
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill=tk.X, padx=8, pady=6)
        self.pos = tk.Label(top, text="", bg="#f0f0f0",
                            font=("Microsoft YaHei", 11, "bold"))
        self.pos.pack(side=tk.LEFT)
        done = sum(1 for s in self.manifest["segments"] if self._already_v2(s))
        self.progress = tk.Label(top, text=f"二次复核 {done}/60",
                                 bg="#f0f0f0", font=("Microsoft YaHei", 10))
        self.progress.pack(side=tk.LEFT, padx=16)
        ttk.Button(top, text="上一题", command=lambda: self._load(self.idx - 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="跳过", command=lambda: self._load(self.idx + 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="✓ 保存二次复核", command=self._save).pack(side=tk.RIGHT, padx=8)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(paned, width=420)
        paned.add(left, weight=0)
        self.info = tk.Text(left, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.info.pack(fill=tk.BOTH, expand=True)
        ttk.Button(left, text="▶ 播放视频（±3s）", command=self._play).pack(fill=tk.X, padx=6, pady=4)

        right = ttk.Frame(paned, width=480)
        paned.add(right, weight=0)
        tk.Label(right, text="二次复核（隐藏首答与AI答案）",
                 bg="#f0f0f0", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W)
        self.vars = {}
        form = ttk.Frame(right)
        form.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        fields = [("scene", "场景", SCENES), ("product", "产品", PRODUCTS),
                  ("material", "材质", MATERIALS), ("function", "功能", FUNCTIONS),
                  ("action", "动作", ACTIONS), ("shot_type", "镜头类型", SHOT_TYPES)]
        for i, (key, label, options) in enumerate(fields):
            tk.Label(form, text=label, bg="#f0f0f0").grid(row=i, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar()
            ttk.Combobox(form, textvariable=var, values=options, width=24).grid(
                row=i, column=1, padx=4)
            self.vars[key] = var
        row = len(fields)
        tk.Label(form, text="人物", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.vars["people_presence"] = tk.StringVar()
        ttk.Combobox(form, textvariable=self.vars["people_presence"], values=PEOPLE, width=24).grid(
            row=row, column=1, padx=4)
        row += 1
        tk.Label(form, text="人工置信度*", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.vars["human_confidence"] = tk.StringVar()
        ttk.Combobox(form, textvariable=self.vars["human_confidence"], values=CONFIDENCE, width=24).grid(
            row=row, column=1, padx=4)
        row += 1
        tk.Label(form, text="审核状态*", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.vars["review_status"] = tk.StringVar()
        ttk.Combobox(form, textvariable=self.vars["review_status"], values=REVIEW_STATUS, width=24).grid(
            row=row, column=1, padx=4)
        row += 1
        tk.Label(form, text="备注", bg="#f0f0f0").grid(row=row, column=0, sticky=tk.W)
        self.vars["comment"] = tk.StringVar()
        tk.Entry(form, textvariable=self.vars["comment"], width=30).grid(row=row, column=1, padx=4)

    def _load(self, idx: int) -> None:
        if not self.queue:
            self.pos.config(text="二次复核全部完成")
            return
        self.idx = idx % len(self.queue)
        seg_id = self.queue[self.idx]
        self.current_seg = seg_id
        self.pos.config(text=f"{self.idx + 1}/{len(self.queue)}  {seg_id[:16]}")
        # 显示基本信息（不含 AI/首答）
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute("SELECT asset_id, start_ms, end_ms FROM segments WHERE segment_id=?", (seg_id,)).fetchone()
        conn.close()
        info = [f"segment: {seg_id}"]
        if row:
            info.append(f"asset: {row[0][:14]}")
            info.append(f"range: {row[1]}-{row[2]}ms")
        self.info.delete("1.0", tk.END)
        self.info.insert(tk.END, "\n".join(info))
        for v in self.vars.values():
            v.set("")
        # 记录 v1 annotation id
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        r = conn.execute("SELECT annotation_id FROM human_annotations WHERE target_id=?", (seg_id,)).fetchone()
        conn.close()
        self.current_v1_id = r[0] if r else 0

    def _play(self) -> None:
        if not self.current_seg:
            return
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute("SELECT asset_id FROM segments WHERE segment_id=?", (self.current_seg,)).fetchone()
        conn.close()
        if row:
            from treecut.services.identity import AssetRepository
            path = AssetRepository(self.db_path).resolve_path(row[0])
            if path and os.path.exists(path):
                os.startfile(path)  # type: ignore[attr-defined]

    def _save(self) -> None:
        if not self.current_seg:
            return
        values = {k: v.get() for k, v in self.vars.items()}
        ok, msg, status = validate_submission(
            values,
            self.vars["human_confidence"].get(),
            self.vars["review_status"].get())
        if not ok:
            messagebox.showerror("提交被拒绝", msg)
            return
        if msg:
            messagebox.showwarning("状态调整", msg)
        self.svc.save_v2(self.current_seg, self.current_v1_id, values,
                         human_confidence=self.vars["human_confidence"].get(),
                         review_status=status,
                         operator=os.environ.get("USERNAME", ""))
        done = sum(1 for s in self.manifest["segments"] if self._already_v2(s))
        self.progress.config(text=f"二次复核 {done}/60")
        self._load(self.idx + 1)


if __name__ == "__main__":
    app = SecondReviewApp()
    app.mainloop()
