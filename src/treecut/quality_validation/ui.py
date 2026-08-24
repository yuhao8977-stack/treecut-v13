"""P2.7: 人工质量审核 UI（tkinter 三栏布局）。

左侧：视频播放器 + 关键帧缩略图
中间：AI 分析结果（Scene 标签/ASR 文本/OCR 文本/Keyframe）
右侧：人工评价（✅/⚠️/❌ + 修改）+ 100 分评分 + 素材状态

数据来源：只读已有分析结果；人工反馈写入新表（human_feedback/asset_quality/asset_status）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.quality_validation.scoring import (
    DIMENSION_LABELS, DIMENSION_DESCRIPTIONS, SCORE_MEANING, score_to_grade,
)
from treecut.quality_validation.store import (
    QualityValidationStore, ASSET_STATUS,
    VERDICT_CORRECT, VERDICT_PARTIAL, VERDICT_WRONG,
)

# 评分维度（UI 顺序）
SCORE_ORDER = ("scene", "product", "function", "value", "business")

# AI 结果类型（供逐项评价）
AI_TYPES = ("scene", "asr", "ocr", "keyframe", "label")


class QualityReviewApp(tk.Tk):
    def __init__(self, db_path: str | Path | None = None,
                 sample_file: str | Path | None = None):
        super().__init__()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self.store = QualityValidationStore(self.db_path)
        self.store.ensure_schema()
        self.operator = os.environ.get("TREECUT_OPERATOR", "admin")

        # 加载抽检队列
        self.queue = self._load_queue(sample_file)
        self.current_index = 0
        self.current_asset: dict | None = None
        self._ai_data: dict = {}

        self.title("TreeCut AI 分析质量验证中心")
        self.geometry("1560x900")
        self.configure(bg="#f0f0f0")

        self._build_layout()
        if self.queue:
            self._load_asset(0)
        else:
            self._show_empty()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # 队列
    # ------------------------------------------------------------------

    def _load_queue(self, sample_file) -> list[dict]:
        if sample_file is None:
            sample_file = self.db_path.parent / "sample_100.json"
        if Path(sample_file).exists():
            with open(sample_file, encoding="utf-8") as f:
                return json.load(f)
        return []

    # ------------------------------------------------------------------
    # UI 布局
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        # 顶部工具条
        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="操作员:").pack(side="left")
        self.operator_var = tk.StringVar(value=self.operator)
        ttk.Entry(toolbar, textvariable=self.operator_var, width=12).pack(side="left", padx=4)
        ttk.Button(toolbar, text="◀ 上一个", command=lambda: self._nav(-1)).pack(side="left", padx=6)
        ttk.Button(toolbar, text="下一个 ▶", command=lambda: self._nav(1)).pack(side="left")
        self.progress_label = ttk.Label(toolbar, text="0 / 0")
        self.progress_label.pack(side="left", padx=16)
        ttk.Button(toolbar, text="刷新 AI 结果", command=self._reload_ai).pack(side="left", padx=6)
        ttk.Button(toolbar, text="保存全部评价", command=self._save_all).pack(side="right")

        # 三栏
        panes = ttk.PanedWindow(main, orient="horizontal")
        panes.pack(fill="both", expand=True)

        # 左栏：视频 + 关键帧
        left = ttk.Frame(panes, padding=4)
        panes.add(left, weight=2)
        self._build_left(left)

        # 中栏：AI 结果
        center = ttk.Frame(panes, padding=4)
        panes.add(center, weight=3)
        self._build_center(center)

        # 右栏：人工评价
        right = ttk.Frame(panes, padding=4)
        panes.add(right, weight=2)
        self._build_right(right)

        self.operator = self.operator_var.get()

    def _build_left(self, parent: ttk.Frame) -> None:
        info = ttk.LabelFrame(parent, text="素材信息", padding=6)
        info.pack(fill="x")
        self.asset_label = ttk.Label(info, text="", wraplength=420)
        self.asset_label.pack(fill="x")

        video = ttk.LabelFrame(parent, text="视频", padding=4)
        video.pack(fill="both", expand=True)
        self.video_canvas = tk.Canvas(video, bg="black", height=320, highlightthickness=0)
        self.video_canvas.pack(fill="both", expand=True)
        btns = ttk.Frame(video)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="播放视频（系统播放器）", command=self._play_video).pack(side="left")
        ttk.Button(btns, text="截取当前帧", command=self._grab_frame).pack(side="left", padx=6)

        kf = ttk.LabelFrame(parent, text="关键帧", padding=4)
        kf.pack(fill="both", expand=True)
        self.kf_canvas = tk.Canvas(kf, bg="#e8e8e8", height=200, highlightthickness=0)
        self.kf_canvas.pack(fill="both", expand=True)

    def _build_center(self, parent: ttk.Frame) -> None:
        # Scene
        scene = ttk.LabelFrame(parent, text="① 场景识别 (Scene)", padding=6)
        scene.pack(fill="x", pady=(0, 6))
        self.scene_text = tk.Text(scene, height=3, wrap="word")
        self.scene_text.pack(fill="x")
        self.scene_text.insert("1.0", "（无场景标签）")

        # Keyframe 描述
        kfd = ttk.LabelFrame(parent, text="② 关键帧 (Keyframe)", padding=6)
        kfd.pack(fill="x", pady=(0, 6))
        self.kf_text = tk.Text(kfd, height=3, wrap="word")
        self.kf_text.pack(fill="x")
        self.kf_text.insert("1.0", "（无关键帧数据）")

        # ASR
        asr = ttk.LabelFrame(parent, text="③ 语音识别 (ASR)", padding=6)
        asr.pack(fill="x", pady=(0, 6))
        self.asr_text = tk.Text(asr, height=6, wrap="word")
        self.asr_text.pack(fill="x")
        self.asr_text.insert("1.0", "（无转写文本）")

        # OCR
        ocr = ttk.LabelFrame(parent, text="④ 文字识别 (OCR)", padding=6)
        ocr.pack(fill="x", pady=(0, 6))
        self.ocr_text = tk.Text(ocr, height=6, wrap="word")
        self.ocr_text.pack(fill="x")
        self.ocr_text.insert("1.0", "（无 OCR 文本）")

        # 标签
        labels = ttk.LabelFrame(parent, text="⑤ 标签 (Labels)", padding=6)
        labels.pack(fill="both", expand=True)
        self.labels_text = tk.Text(labels, height=5, wrap="word")
        self.labels_text.pack(fill="both", expand=True)
        self.labels_text.insert("1.0", "（无标签）")

    def _build_right(self, parent: ttk.Frame) -> None:
        # AI 结果逐项评价
        eval_frame = ttk.LabelFrame(parent, text="AI 结果评价（每项可标 ✅/⚠️/❌）", padding=6)
        eval_frame.pack(fill="x")
        self.verdict_vars: dict[str, tk.StringVar] = {}
        self.human_label_vars: dict[str, tk.StringVar] = {}
        for ai_type, label in (("scene", "场景识别"), ("asr", "语音转写"),
                               ("ocr", "文字识别"), ("keyframe", "关键帧"),
                               ("label", "标签")):
            row = ttk.Frame(eval_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", width=10).pack(side="left")
            var = tk.StringVar(value=VERDICT_CORRECT)
            self.verdict_vars[ai_type] = var
            for verdict, text in ((VERDICT_CORRECT, "✅ 正确"),
                                  (VERDICT_PARTIAL, "⚠️ 部分"),
                                  (VERDICT_WRONG, "❌ 错误")):
                ttk.Radiobutton(row, text=text, value=verdict,
                                variable=var).pack(side="left", padx=2)
            hv = tk.StringVar(value="")
            self.human_label_vars[ai_type] = hv
            ttk.Entry(row, textvariable=hv, width=18).pack(side="left", padx=4)

        # 100 分评分
        score_frame = ttk.LabelFrame(parent, text="素材评分（100 分制，每维 0/10/20）", padding=6)
        score_frame.pack(fill="x", pady=(8, 0))
        self.score_vars: dict[str, tk.IntVar] = {}
        for dim in SCORE_ORDER:
            row = ttk.Frame(score_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{DIMENSION_LABELS[dim]} (20):", width=16).pack(side="left")
            var = tk.IntVar(value=10)
            self.score_vars[dim] = var
            for v in (0, 10, 20):
                ttk.Radiobutton(row, text=str(v), value=v,
                                variable=var).pack(side="left", padx=2)
            ttk.Label(row, text=SCORE_MEANING[v],
                      foreground="gray").pack(side="left", padx=4)
        self.total_label = ttk.Label(score_frame, text="总分: 50 / 100", font=("", 11, "bold"))
        self.total_label.pack(pady=4)
        for dim in SCORE_ORDER:
            self.score_vars[dim].trace_add("write", lambda *_: self._update_total())

        # 素材状态
        status_frame = ttk.LabelFrame(parent, text="素材状态", padding=6)
        status_frame.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="REVIEW")
        for st in ASSET_STATUS:
            ttk.Radiobutton(status_frame, text=st, value=st,
                            variable=self.status_var).pack(side="left", padx=3)

        # 评价备注
        comment_frame = ttk.LabelFrame(parent, text="备注", padding=6)
        comment_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.comment_text = tk.Text(comment_frame, height=4, wrap="word")
        self.comment_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _resolve_video_path(self, asset_id: str) -> str:
        """从数据库解析素材绝对路径。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute("""
            SELECT s.path, m.relative_path FROM assets a
            JOIN media_files m ON m.id=a.media_id
            JOIN sources s ON s.id=m.source_id
            WHERE a.asset_id=?
        """, (asset_id,)).fetchone()
        conn.close()
        if row:
            return os.path.join(row[0], row[1])
        return ""

    def _load_ai_data(self, asset_id: str) -> dict:
        """读取该素材的全部 AI 分析结果（只读）。"""
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        data = {"segments": [], "keyframes": [], "transcripts": [], "ocr": [],
                "labels": [], "scene_state": None}

        for r in conn.execute("SELECT * FROM segments WHERE asset_id=?", (asset_id,)):
            data["segments"].append(dict(r))
        for r in conn.execute("SELECT * FROM keyframes WHERE asset_id=? ORDER BY timestamp_ms", (asset_id,)):
            data["keyframes"].append(dict(r))
        for r in conn.execute("SELECT * FROM transcripts WHERE asset_id=? ORDER BY start_ms", (asset_id,)):
            data["transcripts"].append(dict(r))
        for r in conn.execute("SELECT * FROM ocr_text WHERE asset_id=? ORDER BY id", (asset_id,)):
            data["ocr"].append(dict(r))
        for r in conn.execute("SELECT * FROM labels WHERE asset_id=?", (asset_id,)):
            data["labels"].append(dict(r))
        st = conn.execute(
            "SELECT * FROM asset_processing_state WHERE asset_id=? AND stage='scene'", (asset_id,)).fetchone()
        data["scene_state"] = dict(st) if st else None
        conn.close()
        return data

    def _load_asset(self, index: int) -> None:
        if not self.queue or index >= len(self.queue):
            return
        self.current_index = index
        item = self.queue[index]
        self.current_asset = item
        self.asset_id = item["asset_id"]
        self._ai_data = self._load_ai_data(self.asset_id)
        self._render_asset()
        self.progress_label.config(text=f"{index + 1} / {len(self.queue)}")

    def _render_asset(self) -> None:
        item = self.current_asset
        self.asset_label.config(
            text=f"素材: {item['asset_id'][:16]}\n分类: {item.get('category', '未分类')}\n"
                 f"路径: {item.get('relative_path', '')[:90]}")
        self._render_scene()
        self._render_kf_summary()
        self._render_asr()
        self._render_ocr()
        self._render_labels()
        self._render_keyframe_images()
        self._render_video_preview()
        # 重置评价控件（保留上次？→ 重置为默认）
        for var in self.verdict_vars.values():
            var.set(VERDICT_CORRECT)
        for var in self.human_label_vars.values():
            var.set("")
        for var in self.score_vars.values():
            var.set(10)
        self.comment_text.delete("1.0", "end")
        self.status_var.set("REVIEW")
        self._update_total()

    def _render_scene(self) -> None:
        self.scene_text.delete("1.0", "end")
        st = self._ai_data.get("scene_state")
        segs = self._ai_data.get("segments", [])
        if st:
            self.scene_text.insert("1.0",
                f"算法: {st.get('algorithm_version', '')} | 状态: {st.get('status', '')}\n"
                f"场景段数: {len(segs)}")
            for s in segs[:8]:
                self.scene_text.insert("end",
                    f"  段 {s.get('scene_no')}: {s.get('start_ms')}-{s.get('end_ms')}ms\n")
        else:
            self.scene_text.insert("1.0", "（无场景数据）")

    def _render_kf_summary(self) -> None:
        self.kf_text.delete("1.0", "end")
        kfs = self._ai_data.get("keyframes", [])
        self.kf_text.insert("1.0", f"关键帧数: {len(kfs)}")
        for k in kfs[:5]:
            self.kf_text.insert("end",
                f"\n  {k.get('timestamp_ms')}ms 清晰度={k.get('sharpness', 0):.1f} "
                f"亮度={k.get('brightness', 0):.1f}")

    def _render_asr(self) -> None:
        self.asr_text.delete("1.0", "end")
        trs = self._ai_data.get("transcripts", [])
        if trs:
            full = " ".join(t.get("text_raw", "") for t in trs)
            self.asr_text.insert("1.0", full if full else "（空转写）")
        else:
            self.asr_text.insert("1.0", "（无 ASR 转写）")

    def _render_ocr(self) -> None:
        self.ocr_text.delete("1.0", "end")
        ocrs = self._ai_data.get("ocr", [])
        if ocrs:
            lines = [f"[{o.get('frame_timestamp_ms')}ms] {o.get('text', '')}"
                     for o in ocrs if o.get("text")]
            self.ocr_text.insert("1.0", "\n".join(lines[:30]) if lines else "（空 OCR）")
        else:
            self.ocr_text.insert("1.0", "（无 OCR 文本）")

    def _render_labels(self) -> None:
        self.labels_text.delete("1.0", "end")
        labels = self._ai_data.get("labels", [])
        if labels:
            for l in labels[:20]:
                self.labels_text.insert("end",
                    f"  {l.get('label', '')} [{l.get('source', '')}]\n")
        else:
            self.labels_text.insert("1.0", "（无标签）")

    def _render_keyframe_images(self) -> None:
        self.kf_canvas.delete("all")
        kfs = self._ai_data.get("keyframes", [])
        if not kfs:
            self.kf_canvas.create_text(100, 30, text="无关键帧", fill="gray")
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.kf_canvas.create_text(100, 30, text="PIL 不可用", fill="red")
            return
        x = 4
        y = 4
        self._kf_images = []
        for k in kfs[:6]:
            p = k.get("image_path", "")
            if not p or not os.path.exists(p):
                continue
            try:
                img = Image.open(p)
                img.thumbnail((120, 120))
                photo = ImageTk.PhotoImage(img)
                self._kf_images.append(photo)
                self.kf_canvas.create_image(x, y, image=photo, anchor="nw")
                x += 128
                if x > 380:
                    x = 4
                    y += 128
            except Exception:
                continue

    def _render_video_preview(self) -> None:
        self.video_canvas.delete("all")
        self.video_canvas.create_text(120, 30, text="点击「播放视频」查看",
                                      fill="white")
        path = self._resolve_video_path(self.asset_id)
        self._video_path = path

    def _grab_frame(self) -> None:
        """截取视频首帧显示在视频区。"""
        try:
            import cv2
            cap = cv2.VideoCapture(self._video_path)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                messagebox.showinfo("提示", "无法读取视频帧")
                return
            from PIL import Image, ImageTk
            import numpy as np
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            scale = min(1.0, 500 / w, 300 / h)
            if scale < 1:
                frame_rgb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
            img = Image.fromarray(frame_rgb)
            self._video_img = ImageTk.PhotoImage(img)
            self.video_canvas.delete("all")
            self.video_canvas.create_image(0, 0, image=self._video_img, anchor="nw")
        except Exception as e:
            messagebox.showerror("截图失败", str(e))

    def _play_video(self) -> None:
        path = getattr(self, "_video_path", "")
        if not path or not os.path.exists(path):
            messagebox.showinfo("提示", "视频文件不存在或不可访问")
            return
        os.startfile(path)  # 系统播放器（含声音）

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _update_total(self) -> None:
        total = sum(self.score_vars[d].get() for d in SCORE_ORDER)
        self.total_label.config(text=f"总分: {total} / 100")

    def _save_all(self) -> None:
        """保存当前素材的全部评价 + 评分 + 状态。"""
        if not self.current_asset:
            return
        asset_id = self.asset_id
        operator = self.operator_var.get() or "admin"

        # 逐项反馈
        ai_snippets = {
            "scene": self.scene_text.get("1.0", "end").strip()[:200],
            "asr": self.asr_text.get("1.0", "end").strip()[:200],
            "ocr": self.ocr_text.get("1.0", "end").strip()[:200],
            "keyframe": self.kf_text.get("1.0", "end").strip()[:200],
            "label": self.labels_text.get("1.0", "end").strip()[:200],
        }
        for ai_type in AI_TYPES:
            verdict = self.verdict_vars[ai_type].get()
            human_label = self.human_label_vars[ai_type].get().strip()
            self.store.add_feedback(
                asset_id=asset_id, ai_type=ai_type, verdict=verdict,
                ai_label=ai_snippets.get(ai_type, ""),
                human_label=human_label,
                comment=self.comment_text.get("1.0", "end").strip()[:500],
                operator=operator,
            )

        # 100 分评分
        scores = {d: self.score_vars[d].get() for d in SCORE_ORDER}
        self.store.score_asset(asset_id=asset_id, reviewer=operator,
                               comment=self.comment_text.get("1.0", "end").strip(),
                               **scores)

        # 素材状态
        self.store.set_asset_status(asset_id, self.status_var.get(), source="human")

        # 自动进入下一个
        self._nav(1)
        messagebox.showinfo("已保存", f"素材 {asset_id[:12]} 评价已保存")

    def _nav(self, delta: int) -> None:
        nxt = self.current_index + delta
        if 0 <= nxt < len(self.queue):
            self._load_asset(nxt)

    def _reload_ai(self) -> None:
        if self.current_asset:
            self._ai_data = self._load_ai_data(self.asset_id)
            self._render_asset()

    def _show_empty(self) -> None:
        self.asset_label.config(text="抽检队列为空。请先生成 sample_100.json")

    def _on_close(self) -> None:
        self.destroy()


def main() -> int:
    app = QualityReviewApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
