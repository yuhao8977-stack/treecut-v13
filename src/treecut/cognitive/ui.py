"""AI Business Cognitive System — Phase 3 认知 UI（tkinter 三栏）。

左栏：素材信息 + 视频预览 + 关键帧
中栏：AI 认知结果（AI理解/行业特征/内容类型/账号适配/模板推荐/商业价值）
右栏：人工确认区（内容类型修正/账号确认/模板选择/商业价值微调/备注）

人工修正写入：
  - content_classification（reviewed=1, human 修正）
  - learning_rules（AI vs 人工差异，供 Phase 4 学习）
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.cognitive.brain import Brain
from treecut.cognitive.store import CognitiveStore

CONTENT_TYPES = ("客户案例", "产品介绍", "工厂实力", "装修方案", "避坑知识")
TEMPLATES = ("T001", "T002", "T003", "T004")


class CognitiveReviewApp(tk.Tk):
    """认知结果审核界面。"""

    def __init__(self, db_path: str | Path | None = None,
                 sample_file: str | Path | None = None):
        super().__init__()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self.store = CognitiveStore(self.db_path)
        self.store.ensure_schema()
        self.brain = Brain(self.db_path)

        self.queue = self._load_queue(sample_file)
        self.current_index = 0
        self.current_asset: dict | None = None
        self.current_result: dict = {}

        self.title("TreeCut AI 认知体系 - 人工确认中心")
        self.geometry("1600x900")
        self.configure(bg="#f0f0f0")

        self._build_layout()
        if self.queue:
            self._load_asset(0)
        else:
            self._show_empty()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ------------------------------------------------------------------
    # 队列
    # ------------------------------------------------------------------

    def _load_queue(self, sample_file) -> list[dict]:
        if sample_file is None:
            sample_file = self.db_path.parent / "sample_100.json"
        if Path(sample_file).exists():
            with open(sample_file, encoding="utf-8") as f:
                return json.load(f)
        # 回退：从 content_classification 未审核素材取
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT asset_id, content_type FROM content_classification "
            "WHERE reviewed=0 ORDER BY RANDOM() LIMIT 100").fetchall()
        conn.close()
        return [{"asset_id": r[0], "category": "未分类", "relative_path": "",
                 "content_type": r[1]} for r in rows]

    # ------------------------------------------------------------------
    # UI 布局
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="◀ 上一个", command=lambda: self._nav(-1)).pack(side="left")
        ttk.Button(toolbar, text="下一个 ▶", command=lambda: self._nav(1)).pack(side="left", padx=6)
        self.progress_label = ttk.Label(toolbar, text="0 / 0")
        self.progress_label.pack(side="left", padx=16)
        ttk.Button(toolbar, text="重新分析当前素材", command=self._reanalyze).pack(side="left", padx=6)
        ttk.Button(toolbar, text="💾 保存确认", command=self._save).pack(side="right")

        panes = ttk.PanedWindow(main, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes, padding=4)
        panes.add(left, weight=2)
        self._build_left(left)

        center = ttk.Frame(panes, padding=4)
        panes.add(center, weight=4)
        self._build_center(center)

        right = ttk.Frame(panes, padding=4)
        panes.add(right, weight=2)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        info = ttk.LabelFrame(parent, text="素材信息", padding=6)
        info.pack(fill="x")
        self.asset_label = ttk.Label(info, text="", wraplength=380)
        self.asset_label.pack(fill="x")

        video = ttk.LabelFrame(parent, text="视频预览", padding=4)
        video.pack(fill="both", expand=True)
        self.video_canvas = tk.Canvas(video, bg="black", height=260, highlightthickness=0)
        self.video_canvas.pack(fill="both", expand=True)
        btns = ttk.Frame(video)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="播放视频", command=self._play_video).pack(side="left")
        ttk.Button(btns, text="截取首帧", command=self._grab_frame).pack(side="left", padx=6)

        kf = ttk.LabelFrame(parent, text="关键帧", padding=4)
        kf.pack(fill="both", expand=True)
        self.kf_canvas = tk.Canvas(kf, bg="#e8e8e8", height=200, highlightthickness=0)
        self.kf_canvas.pack(fill="both", expand=True)

    def _build_center(self, parent: ttk.Frame) -> None:
        # AI 理解
        seg = ttk.LabelFrame(parent, text="① AI 理解", padding=6)
        seg.pack(fill="x", pady=(0, 6))
        self.understand_text = tk.Text(seg, height=3, wrap="word")
        self.understand_text.pack(fill="x")

        # 行业特征
        ind = ttk.LabelFrame(parent, text="② 行业特征", padding=6)
        ind.pack(fill="x", pady=(0, 6))
        self.industry_text = tk.Text(ind, height=6, wrap="word")
        self.industry_text.pack(fill="x")

        # 内容类型 + 账号 + 模板
        dec = ttk.LabelFrame(parent, text="③ 判断层（内容/账号/模板/商业价值）", padding=6)
        dec.pack(fill="x", pady=(0, 6))
        self.decision_text = tk.Text(dec, height=10, wrap="word")
        self.decision_text.pack(fill="x")

        # 模板槽位
        tpl = ttk.LabelFrame(parent, text="④ 模板槽位建议", padding=6)
        tpl.pack(fill="both", expand=True)
        self.slot_text = tk.Text(tpl, height=8, wrap="word")
        self.slot_text.pack(fill="both", expand=True)

    def _build_right(self, parent: ttk.Frame) -> None:
        # 内容类型修正
        ct = ttk.LabelFrame(parent, text="内容类型（人工确认/修正）", padding=6)
        ct.pack(fill="x")
        self.content_type_var = tk.StringVar()
        for i, ctype in enumerate(CONTENT_TYPES):
            ttk.Radiobutton(ct, text=ctype, value=ctype,
                            variable=self.content_type_var).grid(row=i // 3, column=i % 3, sticky="w", padx=2)

        # 账号适配确认
        acc = ttk.LabelFrame(parent, text="账号适配确认", padding=6)
        acc.pack(fill="x", pady=(8, 0))
        self.fit_var = tk.StringVar(value="确认")
        ttk.Radiobutton(acc, text="✅ 确认适配", value="确认", variable=self.fit_var).pack(side="left")
        ttk.Radiobutton(acc, text="⚠️ 需调整", value="需调整", variable=self.fit_var).pack(side="left")
        ttk.Radiobutton(acc, text="❌ 不适用", value="不适用", variable=self.fit_var).pack(side="left")

        # 模板选择
        tm = ttk.LabelFrame(parent, text="推荐模板（可改）", padding=6)
        tm.pack(fill="x", pady=(8, 0))
        self.template_var = tk.StringVar()
        for i, tid in enumerate(TEMPLATES):
            ttk.Radiobutton(tm, text=tid, value=tid,
                            variable=self.template_var).pack(side="left", padx=3)

        # 商业价值微调
        bz = ttk.LabelFrame(parent, text="商业价值评分（人工微调）", padding=6)
        bz.pack(fill="x", pady=(8, 0))
        self.business_var = tk.IntVar(value=70)
        ttk.Scale(bz, from_=0, to=100, variable=self.business_var,
                  command=lambda v: self.business_label.config(text=f"{int(float(v))} 分")).pack(fill="x")
        self.business_label = ttk.Label(bz, text="70 分")
        self.business_label.pack()

        # 备注
        cm = ttk.LabelFrame(parent, text="备注（供反馈学习）", padding=6)
        cm.pack(fill="both", expand=True, pady=(8, 0))
        self.comment_text = tk.Text(cm, height=6, wrap="word")
        self.comment_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _resolve_video_path(self, asset_id: str) -> str:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute("""
            SELECT s.path, m.relative_path FROM assets a
            JOIN media_files m ON m.id=a.media_id
            JOIN sources s ON s.id=m.source_id WHERE a.asset_id=?
        """, (asset_id,)).fetchone()
        conn.close()
        return os.path.join(row[0], row[1]) if row else ""

    def _load_asset(self, index: int) -> None:
        if not self.queue or index >= len(self.queue):
            return
        self.current_index = index
        item = self.queue[index]
        self.current_asset = item
        self.asset_id = item["asset_id"]
        self._video_path = self._resolve_video_path(self.asset_id)
        # 运行完整认知链
        try:
            self.current_result = self.brain.analyze(self.asset_id)
        except Exception as e:
            self.current_result = {"asset_id": self.asset_id, "error": str(e)}
        self._render()
        self.progress_label.config(text=f"{index + 1} / {len(self.queue)}")

    def _render(self) -> None:
        item = self.current_asset
        r = self.current_result
        self.asset_label.config(
            text=f"素材: {item['asset_id'][:16]}\n"
                 f"分类: {item.get('category', '未分类')}\n"
                 f"路径: {item.get('relative_path', '')[:80] or self._video_path[:80]}")

        # ① AI 理解
        self.understand_text.delete("1.0", "end")
        self.understand_text.insert("1.0", r.get("ai_understanding", "（分析失败）"))

        # ② 行业特征
        self.industry_text.delete("1.0", "end")
        ind = r.get("industry", {})
        self.industry_text.insert("1.0",
            f"产品: {', '.join(ind.get('products', [])) or '无'}\n"
            f"材料: {', '.join(ind.get('materials', [])) or '无'}\n"
            f"功能: {', '.join(ind.get('functions', [])) or '无'}\n"
            f"场景: {', '.join(s['semantic'] for s in ind.get('scenes', [])) or '无'}")

        # ③ 判断层
        self.decision_text.delete("1.0", "end")
        fit = r.get("account_fit", {})
        tpl = r.get("template", {})
        self.decision_text.insert("1.0",
            f"内容类型: {r.get('content_type', '无')} (conf {r.get('content_confidence', 0)})\n"
            f"账号适配: {fit.get('account_name', '')} {fit.get('fit_score', 0)}分 — {', '.join(fit.get('reasons', [])[:3])}\n"
            f"推荐模板: {tpl.get('template_id', '无')} {tpl.get('template_name', '')} "
            f"(match {tpl.get('match_score', 0)})\n"
            f"商业价值: {r.get('business_value', 0)}分 — {', '.join(r.get('business_reasons', [])[:4])}")

        # ④ 槽位
        self.slot_text.delete("1.0", "end")
        slots = tpl.get("slots", [])
        if slots:
            for s in slots:
                self.slot_text.insert("end",
                    f"[{s.get('time', '')}] {s.get('role', '')}: {s.get('advice', '')}\n")
        else:
            self.slot_text.insert("1.0", "（无模板槽位）")

        # 右栏默认值
        self.content_type_var.set(r.get("content_type", "") or "客户案例")
        self.fit_var.set("确认")
        self.template_var.set(tpl.get("template_id", "T001") or "T001")
        self.business_var.set(int(r.get("business_value", 70) or 70))
        self.business_label.config(text=f"{int(r.get('business_value', 70))} 分")
        self.comment_text.delete("1.0", "end")

        self._render_keyframes()
        self._render_video_placeholder()

    def _render_keyframes(self) -> None:
        self.kf_canvas.delete("all")
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT image_path FROM keyframes WHERE asset_id=? LIMIT 6", (self.asset_id,)).fetchall()
        conn.close()
        if not rows:
            self.kf_canvas.create_text(100, 30, text="无关键帧", fill="gray")
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.kf_canvas.create_text(100, 30, text="PIL 不可用", fill="red")
            return
        x = y = 4
        self._kf_images = []
        for (p,) in rows:
            if not p or not os.path.exists(p):
                continue
            try:
                img = Image.open(p)
                img.thumbnail((110, 110))
                photo = ImageTk.PhotoImage(img)
                self._kf_images.append(photo)
                self.kf_canvas.create_image(x, y, image=photo, anchor="nw")
                x += 118
                if x > 360:
                    x = 4
                    y += 118
            except Exception:
                continue

    def _render_video_placeholder(self) -> None:
        self.video_canvas.delete("all")
        self.video_canvas.create_text(100, 30, text="点击「播放视频」或「截取首帧」",
                                      fill="white")

    def _grab_frame(self) -> None:
        try:
            import cv2
            cap = cv2.VideoCapture(self._video_path)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                messagebox.showinfo("提示", "无法读取视频帧")
                return
            from PIL import Image, ImageTk
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            scale = min(1.0, 480 / w, 240 / h)
            if scale < 1:
                frame_rgb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
            self._video_img = ImageTk.PhotoImage(Image.fromarray(frame_rgb))
            self.video_canvas.delete("all")
            self.video_canvas.create_image(0, 0, image=self._video_img, anchor="nw")
        except Exception as e:
            messagebox.showerror("截图失败", str(e))

    def _play_video(self) -> None:
        if self._video_path and os.path.exists(self._video_path):
            os.startfile(self._video_path)
        else:
            messagebox.showinfo("提示", "视频文件不可访问")

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """保存人工确认：更新 content_classification + 记录 learning_rules。"""
        asset_id = self.asset_id
        ai_type = self.current_result.get("content_type", "")
        human_type = self.content_type_var.get()
        business = int(self.business_var.get())
        comment = self.comment_text.get("1.0", "end").strip()

        # 更新 content_classification（reviewed=1 + 人工类型）
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute(
            "UPDATE content_classification SET content_type=?, reviewed=1, "
            "created_time=? WHERE asset_id=?",
            (human_type, time.time(), asset_id))
        conn.commit()
        conn.close()

        # 记录学习规则（AI vs 人工差异）
        if human_type != ai_type:
            self.store.add_learning_rule(
                source="brain-ui",
                ai_output=ai_type,
                human_output=human_type,
                error_type="content_type_mismatch",
                rule=f"内容类型 AI={ai_type} → 人工={human_type}",
            )
        # 商业价值差异也记录
        ai_biz = int(self.current_result.get("business_value", 0) or 0)
        if abs(ai_biz - business) >= 10:
            self.store.add_learning_rule(
                source="brain-ui",
                ai_output=f"business={ai_biz}",
                human_output=f"business={business}",
                error_type="business_adjust",
                rule=comment or "商业价值人工调整",
            )

        self._nav(1)
        messagebox.showinfo("已保存", f"素材 {asset_id[:12]} 认知确认已保存")

    def _nav(self, delta: int) -> None:
        nxt = self.current_index + delta
        if 0 <= nxt < len(self.queue):
            self._load_asset(nxt)

    def _reanalyze(self) -> None:
        if self.current_asset:
            self.current_result = self.brain.analyze(self.asset_id)
            self._render()
            messagebox.showinfo("完成", "认知链已重新运行")

    def _show_empty(self) -> None:
        self.asset_label.config(text="认知队列为空。请先生成 sample_100.json 或先运行 --brain-batch")


def main() -> int:
    app = CognitiveReviewApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
