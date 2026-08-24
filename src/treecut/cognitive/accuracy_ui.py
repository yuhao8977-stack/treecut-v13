"""TreeCut AI 业务理解能力验证 — 人工审核 UI（tkinter 三栏）。

左栏：测试素材信息（路径/时长/分辨率 + A 段事实）
中栏：AI ABCD 四段式分析全文
右栏：人工逐项审核（场景判定/产品判定/内容类型/模板/商业评分/总评）

审核保存到 accuracy_review，并把 accuracy_test.status 置为 reviewed。
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

# 内容类型扩展列表（AI 判定标准）
CONTENT_TYPES = (
    "客户案例", "产品介绍", "产品展示", "工厂实力", "装修方案", "避坑知识",
    "材质介绍", "功能展示", "品牌宣传", "其他",
)
TEMPLATES = ("T001", "T002", "T003", "T004", "无推荐")
OVERALLS = ("优秀", "可用", "需要优化", "不可用")
VERDICTS = ("correct", "partial", "wrong")

# 人工内容确认选项（V1.2：人工给出具体判定，非对错）
HUMAN_SCENES = (
    "客户家", "工厂", "展厅", "安装现场", "生产", "厨房空间", "客厅空间",
    "餐厅", "户外", "其他",
)
HUMAN_PRODUCTS = (
    "岛台", "伸缩岛台", "岩板岛台", "实木岛台", "中古风岛台", "半岛台",
    "餐边柜", "橱柜", "餐桌", "吧台", "茶桌", "电视柜", "无产品", "其他",
)
HUMAN_MATERIALS = (
    "岩板", "实木", "奢石", "大理石", "水晶", "肤感", "烤漆", "木纹",
    "不锈钢", "玻璃", "无明确材质", "其他",
)
HUMAN_FUNCTIONS = (
    "收纳", "抽屉", "伸缩", "隐藏电器", "插座", "轨道插座", "水吧",
    "升降", "灯带", "无明确功能", "其他",
)


class AccuracyReviewApp(tk.Tk):
    """AI 业务理解准确率人工审核界面。"""

    def __init__(self, db_path: str | Path | None = None):
        super().__init__()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        # 确保 accuracy 表结构就绪（含新列迁移），否则保存会报 no such column
        try:
            from treecut.cognitive.accuracy import AccuracyEngine
            AccuracyEngine(self.db_path)
        except Exception as e:
            print(f"  [accuracy schema init] {e}")
        self.queue: list[dict] = []
        self.current_index = 0
        self.current: dict | None = None
        self.templates: dict[str, dict] = self._load_templates()

        self.title("TreeCut AI 业务理解能力验证 - 人工审核")
        self.geometry("1680x940")
        self.configure(bg="#f0f0f0")

        self._build_layout()
        self._reload_queue(force_reviewed=False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_templates(self) -> dict[str, dict]:
        """加载模板定义（T001-T004），供审核时查看。"""
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT template_id, template_name, content_type, structure, cta "
            "FROM content_templates").fetchall()
        conn.close()
        out = {}
        for tid, name, ctype, structure, cta in rows:
            try:
                struct = json.loads(structure or "[]")
                roles = " → ".join(f"{s.get('t','')}{s.get('role','')}" for s in struct)
            except Exception:
                roles = ""
            out[tid] = {"name": name, "content_type": ctype,
                        "structure": roles, "cta": cta}
        return out

    def _all_templates_desc(self) -> str:
        """全部模板清单（审核前必读）。"""
        lines = []
        for tid in ("T001", "T002", "T003", "T004"):
            t = self.templates.get(tid)
            if t:
                lines.append(f"· {tid} {t['name']}（{t['content_type']}）: {t['structure']} | CTA: {t['cta']}")
        return "\n".join(lines) if lines else "（模板库为空）"

    def template_desc(self, tid: str) -> str:
        """返回模板的可读描述（无模板/未知模板时给提示）。"""
        if not tid or tid in ("", "无推荐"):
            return "无推荐模板 — 此类素材当前无匹配模板，可人工指定或跳过"
        t = self.templates.get(tid)
        if not t:
            return f"{tid}（未知模板，可在模板表查看）"
        return (f"{tid} {t['name']}（适用: {t['content_type']}）\n"
                f"结构: {t['structure']}\nCTA: {t['cta']}")

    # ------------------------------------------------------------------
    # 队列
    # ------------------------------------------------------------------

    def _reload_queue(self, force_reviewed: bool = False) -> None:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        if force_reviewed:
            rows = conn.execute(
                "SELECT id, asset_id, expected_type, ai_analysis, status "
                "FROM accuracy_test WHERE status='reviewed' "
                "ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT id, asset_id, expected_type, ai_analysis, status "
                "FROM accuracy_test WHERE status='analyzed' "
                "ORDER BY id").fetchall()
        conn.close()
        self.queue = [
            {"test_id": r[0], "asset_id": r[1], "expected_type": r[2],
             "ai_analysis": json.loads(r[3] or "{}"), "status": r[4]}
            for r in rows
        ]
        self.queue_label.config(text=f"待审核 {len(self.queue)} 条")
        if self.queue:
            self.current_index = 0
            self._load_current()
        else:
            self._show_empty()

    def _load_current(self) -> None:
        self.current = self.queue[self.current_index]
        self.pos_label.config(
            text=f"{self.current_index + 1} / {len(self.queue)}  "
                 f"测试分类: {self.current['expected_type']}")
        self._render()

    def _show_empty(self) -> None:
        self.current = None
        self.pos_label.config(text="无待审核素材（请先 --accuracy-run 生成 AI 分析）")
        self.ai_text.delete("1.0", tk.END)
        self.ai_text.insert(tk.END, "当前队列为空。")
        for name, obj in vars(self).items():
            if isinstance(obj, (tk.StringVar, tk.IntVar, tk.DoubleVar, tk.BooleanVar)):
                try:
                    obj.set("" if isinstance(obj, tk.StringVar) else 0)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill=tk.X, padx=8, pady=6)
        self.pos_label = tk.Label(top, text="", bg="#f0f0f0", font=("Microsoft YaHei", 11, "bold"))
        self.pos_label.pack(side=tk.LEFT)
        self.queue_label = tk.Label(top, text="", bg="#f0f0f0", font=("Microsoft YaHei", 10))
        self.queue_label.pack(side=tk.LEFT, padx=16)
        ttk.Button(top, text="上一题", command=lambda: self._step(-1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="下一题", command=lambda: self._step(1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="跳过", command=lambda: self._step(1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="刷新队列", command=lambda: self._reload_queue(False)).pack(side=tk.RIGHT, padx=4)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # --- 左栏：素材信息 ---
        left = ttk.Frame(paned, width=380)
        paned.add(left, weight=0)
        self.info_text = tk.Text(left, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(left, text="▶ 播放视频",
                   command=self._play_video).pack(fill=tk.X, padx=6, pady=4)

        # --- 中栏：AI ABCD 分析 ---
        mid = ttk.Frame(paned)
        paned.add(mid, weight=1)
        tk.Label(mid, text="AI ABCD 四段式分析（只读）",
                 bg="#f0f0f0", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W)
        self.ai_text = tk.Text(mid, wrap=tk.WORD, font=("Microsoft YaHei", 9))
        self.ai_text.pack(fill=tk.BOTH, expand=True)

        # --- 右栏：人工审核（加宽） ---
        right = ttk.Frame(paned, width=560)
        paned.add(right, weight=0)
        self._build_review_form(right)

    def _build_review_form(self, parent) -> None:
        tk.Label(parent, text="人工审核（AI 判定 ↑ / 人工填写 ↓）",
                 bg="#f0f0f0", font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, padx=4)

        # 滚动容器（垂直滚动即可，2 列布局无横向溢出）
        canvas = tk.Canvas(parent, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        form = ttk.Frame(canvas)
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor=tk.NW)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def section(text, r):
            tk.Label(form, text=text, bg="#e8e8f8", anchor=tk.W,
                     font=("Microsoft YaHei", 9, "bold")).grid(
                row=r, column=0, columnspan=2, sticky=tk.W + tk.E, pady=(8, 2), padx=2)
            return r + 1

        def airow(label, var, r):
            """AI 只读行（整行绿底，2 列：标签 + 值）。"""
            tk.Label(form, text="AI " + label, bg="#d8f0d8", anchor=tk.W,
                     width=16, font=("Microsoft YaHei", 8, "bold")).grid(
                row=r, column=0, sticky=tk.W, pady=1, padx=2)
            e = tk.Entry(form, textvariable=var, state="readonly",
                         readonlybackground="#eef6ee", width=40, font=("Microsoft YaHei", 8))
            e.grid(row=r, column=1, sticky=tk.W, padx=4, pady=1)
            return r + 1

        def hurow(label, var, r, options=None, spin=False, spin_to=100, editable=True):
            """人工填写行（缩进，白底；下拉可选可手输）。"""
            tk.Label(form, text="✍ " + label, bg="#f0f0f0", anchor=tk.W,
                     width=16, font=("Microsoft YaHei", 8)).grid(
                row=r, column=0, sticky=tk.W, pady=2, padx=2)
            if spin:
                ttk.Spinbox(form, from_=0, to=spin_to, textvariable=var, width=8).grid(
                    row=r, column=1, sticky=tk.W, padx=4)
            elif options:
                cb = ttk.Combobox(form, textvariable=var, values=options,
                                  width=36, state="normal" if editable else "readonly")
                cb.grid(row=r, column=1, sticky=tk.W, padx=4)
                # 修复：点击输入框/箭头即弹出下拉列表（ttk 在 canvas 内默认不弹）
                def _open_dropdown(event):
                    try:
                        event.widget.event_generate("<Down>")
                        return "break"
                    except Exception:
                        return None
                cb.bind("<Button-1>", _open_dropdown)
            else:
                ttk.Entry(form, textvariable=var, width=40).grid(
                    row=r, column=1, sticky=tk.W, padx=4)
            return r + 1

        # ---------------- 变量 ----------------
        self.ai_scene_var = tk.StringVar()     # AI 场景判定（只读）
        self.ai_product_var = tk.StringVar()   # AI 产品识别（只读）
        self.ai_material_var = tk.StringVar()  # AI 材质识别（只读）
        self.ai_func_var = tk.StringVar()      # AI 功能识别（只读）
        # 人工内容确认（具体值，非对错）
        self.human_scene_var = tk.StringVar()
        self.human_product_var = tk.StringVar()
        self.human_material_var = tk.StringVar()
        self.human_function_var = tk.StringVar()
        self.scene_var = tk.StringVar()
        self.scene_score_var = tk.IntVar(value=0)
        self.product_var = tk.StringVar()
        self.ai_ct_var = tk.StringVar()
        self.human_ct_var = tk.StringVar()
        self.ai_tpl_var = tk.StringVar()
        self.human_tpl_var = tk.StringVar()
        self.tpl_verdict_var = tk.StringVar()
        self.tpl_reason_var = tk.StringVar()
        self.ai_biz_var = tk.IntVar(value=0)
        self.human_biz_var = tk.IntVar(value=0)
        # AI 5 维评分（只读显示）
        self.ai_truth_var = tk.StringVar()
        self.ai_prod_var = tk.StringVar()
        self.ai_user_var = tk.StringVar()
        self.ai_comm_var = tk.StringVar()
        self.ai_deal_var = tk.StringVar()
        self.ai_truth_rs_var = tk.StringVar()
        self.ai_prod_rs_var = tk.StringVar()
        self.ai_user_rs_var = tk.StringVar()
        self.ai_comm_rs_var = tk.StringVar()
        self.ai_deal_rs_var = tk.StringVar()
        # 人工 5 维评分 + 原因
        self.human_truth_var = tk.IntVar(value=0)
        self.human_prod_var = tk.IntVar(value=0)
        self.human_user_var = tk.IntVar(value=0)
        self.human_comm_var = tk.IntVar(value=0)
        self.human_deal_var = tk.IntVar(value=0)
        self.truth_reason_var = tk.StringVar()
        self.prod_reason_var = tk.StringVar()
        self.user_reason_var = tk.StringVar()
        self.comm_reason_var = tk.StringVar()
        self.deal_reason_var = tk.StringVar()
        self.overall_var = tk.StringVar()
        self.comment_var = tk.StringVar()
        self.operator_var = tk.StringVar()

        # ---------------- 布局 ----------------
        r = section("— 一、场景与产品判定（AI 判定 ↑ / 人工确认内容 ↓）—", 0)
        r = airow("AI 场景", self.ai_scene_var, r)
        r = hurow("人工场景(选择或输入)", self.human_scene_var, r, HUMAN_SCENES)
        r = airow("AI 产品", self.ai_product_var, r)
        r = hurow("人工产品(选择或输入)", self.human_product_var, r, HUMAN_PRODUCTS)
        r = airow("AI 材质", self.ai_material_var, r)
        r = hurow("人工材质(选择或输入)", self.human_material_var, r, HUMAN_MATERIALS)
        r = airow("AI 功能", self.ai_func_var, r)
        r = hurow("人工功能(选择或输入)", self.human_function_var, r, HUMAN_FUNCTIONS)
        r = airow("AI 内容类型", self.ai_ct_var, r)
        r = hurow("人工内容类型", self.human_ct_var, r, CONTENT_TYPES)

        r = section("— 二、模板反馈（账号DNA训练）—", r)
        r = airow("推荐模板", self.ai_tpl_var, r)
        r = hurow("人工最终模板", self.human_tpl_var, r, TEMPLATES)
        r = hurow("模板判定", self.tpl_verdict_var, r, ("适合", "部分适合", "不适合"))
        r = hurow("模板原因", self.tpl_reason_var, r)
        tk.Label(form, text="📋 模板说明（审核前必读）", bg="#fffbe6",
                 font=("Microsoft YaHei", 9, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.W, pady=(6, 2), padx=2); r += 1
        self.tpl_info_text = tk.Text(form, width=54, height=8,
                                     font=("Microsoft YaHei", 8), bg="#fffbe6", relief=tk.GROOVE)
        self.tpl_info_text.grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2); r += 1
        self.tpl_info_text.insert(tk.END, self._all_templates_desc())
        self.tpl_info_text.config(state=tk.DISABLED)

        r = section("— 三、商业价值评分（AI 5维 ↑ / 人工 5维 ↓）—", r)
        r = airow("商业总分", self.ai_biz_var, r)
        r = airow("真实性/20", self.ai_truth_var, r)
        r = airow("真实性原因", self.ai_truth_rs_var, r)
        r = airow("产品价值/20", self.ai_prod_var, r)
        r = airow("产品价值原因", self.ai_prod_rs_var, r)
        r = airow("用户价值/20", self.ai_user_var, r)
        r = airow("用户价值原因", self.ai_user_rs_var, r)
        r = airow("传播价值/20", self.ai_comm_var, r)
        r = airow("传播价值原因", self.ai_comm_rs_var, r)
        r = airow("成交价值/20", self.ai_deal_var, r)
        r = airow("成交价值原因", self.ai_deal_rs_var, r)
        tk.Label(form, text="▼ 以下为人工填写（每项 0-20 + 原因）",
                 bg="#f0f0f0", font=("Microsoft YaHei", 8, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.W, pady=(6, 2), padx=2); r += 1
        r = hurow("人工真实性/20", self.human_truth_var, r, spin=True, spin_to=20)
        r = hurow("人工真实性原因", self.truth_reason_var, r)
        r = hurow("人工产品价值/20", self.human_prod_var, r, spin=True, spin_to=20)
        r = hurow("人工产品价值原因", self.prod_reason_var, r)
        r = hurow("人工用户价值/20", self.human_user_var, r, spin=True, spin_to=20)
        r = hurow("人工用户价值原因", self.user_reason_var, r)
        r = hurow("人工传播价值/20", self.human_comm_var, r, spin=True, spin_to=20)
        r = hurow("人工传播价值原因", self.comm_reason_var, r)
        r = hurow("人工成交价值/20", self.human_deal_var, r, spin=True, spin_to=20)
        r = hurow("人工成交价值原因", self.deal_reason_var, r)

        r = section("— 四、总评 —", r)
        r = hurow("总评", self.overall_var, r, OVERALLS)
        r = hurow("备注", self.comment_var, r)
        r = hurow("操作员", self.operator_var, r)

        btn = tk.Button(parent, text="✓ 保存审核", command=self._save_review,
                        bg="#4CAF50", fg="white", font=("Microsoft YaHei", 11, "bold"))
        btn.pack(fill=tk.X, padx=8, pady=6)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self.current:
            return
        test = self.current
        analysis = test["ai_analysis"] or {}
        a = analysis.get("A", {})
        b = analysis.get("B", {})
        c = analysis.get("C", {})
        d = analysis.get("D", {})
        understand = analysis.get("ai_understanding", "")

        # 左栏
        info = []
        info.append(f"asset_id: {test['asset_id']}")
        info.append(f"测试分类: {test['expected_type']}")
        info.append(f"状态: {test['status']}")
        info.append(f"路径: {a.get('path', '')}")
        info.append(f"时长: {a.get('duration', 0)}s   分辨率: {a.get('resolution', '')}")
        info.append("")
        info.append("【A. 基础事实】")
        info.append(f"  关键帧: {a.get('keyframes', 0)}")
        info.append(f"  ASR: {a.get('asr', '')[:200]}")
        info.append(f"  OCR: {a.get('ocr', '')[:120]}")
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, "\n".join(info))

        # 中栏
        out = []
        out.append("【A. 基础检测事实】")
        out.append(json.dumps(a, ensure_ascii=False, indent=1))
        out.append("\n【B. AI 业务理解】")
        out.append(json.dumps(b, ensure_ascii=False, indent=1))
        out.append("\n【C. 小红书运营匹配】")
        out.append(json.dumps(c, ensure_ascii=False, indent=1))
        out.append("\n【D. 商业价值评分】")
        out.append(json.dumps(d, ensure_ascii=False, indent=1))
        out.append("\n【AI 整体理解】")
        out.append(str(understand))
        self.ai_text.delete("1.0", tk.END)
        self.ai_text.insert(tk.END, "\n".join(out))

        # 右栏预填 AI 值（人工值清空）
        ai_scene = b.get("scene_level1", "")
        if b.get("scene_level2"):
            ai_scene += f" / {b['scene_level2']}"
        self.ai_scene_var.set(ai_scene or "未识别")
        ai_products = "、".join(b.get("product", [])[:3]) or "未识别"
        ai_materials = "、".join(b.get("material", [])[:3]) or "未识别"
        ai_funcs = "、".join(b.get("function", [])[:3]) or "未识别"
        self.ai_product_var.set(ai_products)
        self.ai_material_var.set(ai_materials)
        self.ai_func_var.set(ai_funcs)
        self.ai_ct_var.set(b.get("content_type", ""))
        self.ai_tpl_var.set(c.get("recommend_template", "") or "无推荐")
        self.ai_biz_var.set(round(float(d.get("total", 0) or 0)))
        # AI 5 维评分 + 原因（只读）
        ai_scores = d.get("scores", {}) or {}
        ai_dims = {"真实性": "ai_truth", "产品价值": "ai_prod",
                   "用户价值": "ai_user", "内容传播": "ai_comm",
                   "成交价值": "ai_deal"}
        for dim, attr in ai_dims.items():
            getattr(self, f"{attr}_var").set(str(ai_scores.get(dim, 0)))
        ai_dr = d.get("dim_reasons", {}) or {}
        for dim, attr in (("真实性", "ai_truth_rs"), ("产品价值", "ai_prod_rs"),
                          ("用户价值", "ai_user_rs"), ("内容传播", "ai_comm_rs"),
                          ("成交价值", "ai_deal_rs")):
            getattr(self, f"{attr}_var").set(ai_dr.get(dim, ""))
        # 人工值清空（V1.2：具体内容确认）
        self.human_scene_var.set("")
        self.human_product_var.set("")
        self.human_material_var.set("")
        self.human_function_var.set("")
        self.scene_score_var.set(0)
        self.human_ct_var.set("")
        self.human_tpl_var.set("无推荐")
        self.tpl_verdict_var.set("")
        self.tpl_reason_var.set("")
        self.human_truth_var.set(0)
        self.human_prod_var.set(0)
        self.human_user_var.set(0)
        self.human_comm_var.set(0)
        self.human_deal_var.set(0)
        self.truth_reason_var.set("")
        self.prod_reason_var.set("")
        self.user_reason_var.set("")
        self.comm_reason_var.set("")
        self.deal_reason_var.set("")
        self.overall_var.set("")
        self.comment_var.set("")
        self.operator_var.set(os.environ.get("USERNAME", ""))

        # 模板说明：顶部标出当前 AI 推荐模板
        ai_tpl = c.get("recommend_template", "") or "无推荐"
        head = f"▶ 本视频 AI 推荐: {ai_tpl}\n"
        head += self.template_desc(ai_tpl) + "\n\n"
        self.tpl_info_text.config(state=tk.NORMAL)
        self.tpl_info_text.delete("1.0", tk.END)
        self.tpl_info_text.insert(tk.END, head)
        self.tpl_info_text.insert(tk.END, "【全部模板】\n" + self._all_templates_desc())
        self.tpl_info_text.config(state=tk.DISABLED)

    def _play_video(self) -> None:
        if not self.current:
            return
        path = (self.current.get("ai_analysis") or {}).get("A", {}).get("path", "")
        if path and os.path.exists(path):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("提示", f"视频文件不存在: {path}")

    # ------------------------------------------------------------------
    # 保存 / 导航
    # ------------------------------------------------------------------

    def _save_review(self) -> None:
        if not self.current:
            return
        if not self.human_ct_var.get() or not self.human_scene_var.get():
            messagebox.showwarning("提示", "请至少填写人工场景和人工内容类型")
            return
        # 人工 5 维总分（自动汇总）
        human_biz = (self.human_truth_var.get() + self.human_prod_var.get()
                     + self.human_user_var.get() + self.human_comm_var.get()
                     + self.human_deal_var.get())
        # AI 各维度判定（从只读变量提取，供学习规则对比）
        ai_scene = self.ai_scene_var.get()
        ai_product = self.ai_product_var.get()
        ai_material = self.ai_material_var.get()
        ai_function = self.ai_func_var.get()
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute(
            "INSERT OR REPLACE INTO accuracy_review("
            "test_id,asset_id,scene_verdict,scene_score,product_verdict,"
            "ai_content_type,human_content_type,ai_template,human_template,"
            "ai_business,human_business,overall,comment,operator,created_time,"
            "template_verdict,template_reason,"
            "truth_reason,product_reason,user_reason,comm_reason,deal_reason,"
            "human_scene,human_product,human_material,human_function)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.current["test_id"], self.current["asset_id"],
             "", self.scene_score_var.get(), "",
             self.ai_ct_var.get(), self.human_ct_var.get(),
             self.ai_tpl_var.get(), self.human_tpl_var.get(),
             self.ai_biz_var.get(), human_biz,
             self.overall_var.get(), self.comment_var.get(),
             self.operator_var.get(), time.time(),
             self.tpl_verdict_var.get(), self.tpl_reason_var.get(),
             self.truth_reason_var.get(), self.prod_reason_var.get(),
             self.user_reason_var.get(), self.comm_reason_var.get(),
             self.deal_reason_var.get(),
             self.human_scene_var.get(), self.human_product_var.get(),
             self.human_material_var.get(), self.human_function_var.get()))
        conn.execute(
            "UPDATE accuracy_test SET status='reviewed' WHERE id=?",
            (self.current["test_id"],))
        conn.commit()
        conn.close()
        # 差异 → learning_rules（供 Phase 5 学习）
        if self.human_ct_var.get() and self.ai_ct_var.get() \
                and self.human_ct_var.get() != self.ai_ct_var.get():
            self._write_learning_rule()
        # 场景/材质/产品/功能差异也写入学习规则
        self._write_content_learning_rules(ai_scene, ai_product, ai_material, ai_function)
        self._step(1)

    def _write_content_learning_rules(self, ai_scene, ai_product,
                                      ai_material, ai_function) -> None:
        """人工确认内容 vs AI 判定的差异 → learning_rules。"""
        try:
            from treecut.cognitive.store import CognitiveStore
            store = CognitiveStore(self.db_path)
            store.ensure_schema()
            diffs = [
                ("scene", ai_scene, self.human_scene_var.get()),
                ("product", ai_product, self.human_product_var.get()),
                ("material", ai_material, self.human_material_var.get()),
                ("function", ai_function, self.human_function_var.get()),
            ]
            for error_type, ai_out, hu_out in diffs:
                if hu_out and ai_out and hu_out != ai_out and "未识别" not in hu_out:
                    store.add_learning_rule(
                        source="accuracy_review",
                        ai_output=ai_out,
                        human_output=hu_out,
                        error_type=error_type,
                        rule=f"人工内容确认: AI={ai_out} 人工={hu_out}")
        except Exception as e:
            print(f"  [内容学习规则写入失败] {e}")

    def _write_learning_rule(self) -> None:
        try:
            from treecut.cognitive.store import CognitiveStore
            store = CognitiveStore(self.db_path)
            store.ensure_schema()
            store.add_learning_rule(
                source="accuracy_review",
                ai_output=self.ai_ct_var.get(),
                human_output=self.human_ct_var.get(),
                error_type="content_type",
                rule=f"人工审核修正(测试集): AI={self.ai_ct_var.get()} "
                     f"人工={self.human_ct_var.get()}")
        except Exception as e:
            print(f"  [learning_rule 写入失败] {e}")

    def _step(self, delta: int) -> None:
        if not self.queue:
            return
        n = len(self.queue)
        self.current_index = (self.current_index + delta) % n
        self._load_current()


if __name__ == "__main__":
    app = AccuracyReviewApp()
    app.mainloop()
