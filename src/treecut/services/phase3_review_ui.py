# -*- coding: utf-8 -*-
"""TreeCut Phase 3 — 人工审核 UI（Schema V2.1，中文界面）。

两个独立审核任务（审核期间系统冻结，只允许保存人工结果）：
  1. THIRD_ADJUDICATION_V1：34 条第三次独立裁决 → human_annotation_v3（Human V3）
  2. TARGETED_REVIEW_BATCH_V1：60 条新 Segment 主动学习审核 → targeted_human_review_v1

设计约束（架构监工冻结）：
  - 隐藏 AI / Human V1 / Human V2 答案，只显示 Segment 视频与元数据
  - 字段 = ANNOTATION_DICTIONARY_V2_1（中文显示、英文入库）
  - 中文词汇与 Phase 2.5 业务词连贯（工厂展示区/客户住宅/茶桌/插电/拉出/缩回…）
  - human_confidence / review_status 无默认必选；空提交禁止；看不清 → 未知+低+需复核
  - 保存不覆盖 V1/V2；完成后只提示进度，不自动改 canonical / 不学习
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.services.schema_v2 import (
    ACTION_GROUP, ATOMIC_ACTION, MULTI_OPTIONS, PRODUCT_FAMILY,
    PRODUCT_VARIANT_BY_FAMILY, SCENE_FAMILY, SCENE_SUBTYPE_BY_FAMILY,
    SHOT_SCALE, PEOPLE_PRESENCE, DICTIONARY_VERSION_V2_1, cn, en,
)

FFMPEG = r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe"


class PlaybackController:
    """统一播放控制器（B2/B3）。

    - UI 禁止直接 os.startfile/subprocess.Popen，统一经此控制器
    - Single Flight + Debounce：同一 (path, mode) 在 DEBOUNCE_MS 内重复请求只接受第一次
    - 不杀用户其他播放器进程
    """

    DEBOUNCE_MS = 600

    def __init__(self, on_launch):
        self._last = {}
        self._busy_until = 0.0
        self._on_launch = on_launch  # 回调：记录 launch（测试/日志用）

    def _allowed(self, key) -> bool:
        import time as _t
        now = _t.time() * 1000
        if key in self._last and (now - self._last[key]) < self.DEBOUNCE_MS:
            return False
        self._last[key] = now
        return True

    def play_full(self, path: str) -> bool:
        if not path or not self._allowed(("full", path)):
            return False
        self._on_launch("full", path)
        os.startfile(path)  # type: ignore[attr-defined]
        return True

    def play_context(self, path: str, start_ms: int, end_ms: int) -> bool:
        key = ("ctx", path, start_ms, end_ms)
        if not path or not self._allowed(key):
            return False
        self._on_launch("context", path)
        out = os.path.join(tempfile.gettempdir(),
                           f"treecut_preview_{abs(hash(key)) % 10**10}.mp4")
        cmd = [FFMPEG, "-y", "-ss", str(max(0, start_ms - 3000) / 1000.0),
               "-i", path, "-t", str((end_ms + 3000 - max(0, start_ms - 3000)) / 1000.0),
               "-c:v", "libx264", "-preset", "ultrafast", "-an", out]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

# 字段中文名（UI 标签）
FIELD_CN = {"scene_family": "场景类别", "scene_subtype": "场景子类",
            "product_family": "产品类别", "product_variant": "产品型号",
            "material": "材质", "component": "组件", "function": "功能",
            "action_group": "动作类别", "action_sequence": "动作序列",
            "shot_scale": "景别", "shot_role": "镜头角色",
            "people_presence": "人物", "product_visibility": "产品可见性",
            "quality": "质量分"}

# 分组标题
GROUPS = [
    ("scene", "① 场景"),
    ("product", "② 产品"),
    ("parts", "③ 材质 / 组件 / 功能（可多选）"),
    ("action", "④ 动作（按发生顺序）"),
    ("shot", "⑤ 镜头"),
    ("other", "⑥ 其他"),
    ("review", "⑦ 审核（必填）"),
]


def validate_v21(values: dict, human_confidence: str, review_status: str,
                 comment: str = "") -> tuple[bool, str, str]:
    """V2.1 提交校验。返回 (是否通过, 提示, 调整后 status)。"""
    conf = (human_confidence or "").strip().upper()
    status = (review_status or "").strip().upper()
    if conf not in ("HIGH", "MEDIUM", "LOW"):
        return False, "人工置信度未选择：本题目需单独选择（高/中/低）", status
    if status not in ("REVIEWED", "NEEDS_SECOND_REVIEW", "GOLD", "EXCLUDED"):
        return False, "审核状态未选择：本题目需单独选择（已审核/需复核/金标准/排除）", status
    filled = 0
    for k in ("scene_family", "scene_subtype", "product_family", "product_variant",
              "shot_scale", "people_presence", "product_visibility"):
        if (values.get(k) or "").strip() not in ("", "UNKNOWN"):
            filled += 1
    for k in ("material", "component", "function", "shot_role", "action_sequence"):
        if values.get(k):
            filled += 1
    if values.get("action_group"):
        filled += 1
    if filled == 0:
        note = (comment or "").upper()
        if status == "EXCLUDED" and ("UNPLAYABLE" in note or "无法播放" in comment):
            return True, "EXCLUDED（视频无法播放）", status
        if status in ("REVIEWED", "GOLD"):
            return False, "关键字段全空，禁止保存为已审核/金标准；已自动改为需复核", "NEEDS_SECOND_REVIEW"
        return True, "关键字段全空，仅允许需复核/排除", status
    return True, "", status


class _V21Form(tk.Frame):
    """Schema V2.1 审核表单（滚动布局 + 分组 + 大号多选框）。

    conf_var/status_var：由父窗口顶部固定区传入（共享 StringVar），
    置信度/状态永远在顶部可见，避免"滚到底部看不见漏选"。
    """

    def __init__(self, master, on_save, conf_var=None, status_var=None):
        super().__init__(master)
        self.on_save = on_save
        self.vars = {}
        self.combos = {}
        self.conf_var = conf_var
        self.status_var = status_var
        self.seq_list: tk.Listbox | None = None
        self.seq = []  # 有序动作（英文）
        self._build()

    # ---------------- 构建 ----------------
    def _combo(self, parent, row, label, options_en, bind=None):
        tk.Label(parent, text=FIELD_CN.get(label, label), bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=row, column=0, sticky=tk.W, pady=3)
        var = tk.StringVar()
        cb = ttk.Combobox(parent, textvariable=var,
                          values=[cn(label, o) for o in options_en], width=30,
                          state="readonly", font=("Microsoft YaHei", 10))
        cb.grid(row=row, column=1, sticky=tk.W, padx=6)
        if bind:
            cb.bind("<<ComboboxSelected>>", bind)
        self.vars[label] = var
        self.combos[label] = cb
        return cb

    def _multiselect(self, parent, row, label, options_en):
        tk.Label(parent, text=f"{FIELD_CN.get(label, label)}（可多选）",
                 bg="#f0f0f0", anchor=tk.W, font=("Microsoft YaHei", 10)).grid(
            row=row, column=0, sticky=tk.NW, pady=3)
        wrap = ttk.Frame(parent)
        wrap.grid(row=row, column=1, sticky=tk.W, padx=6)
        # MULTIPLE: 点击即选中/再点取消，无需 Ctrl —— 符合"点一下选一个"习惯
        lb = tk.Listbox(wrap, selectmode=tk.MULTIPLE, height=5, width=32,
                        exportselection=False, font=("Microsoft YaHei", 10))
        for o in options_en:
            lb.insert(tk.END, cn(label, o))
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.vars[label] = lb
        return lb

    def _group(self, parent, row, title):
        tk.Label(parent, text=title, bg="#e8f0fe", anchor=tk.W,
                 font=("Microsoft YaHei", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=(8, 2))

    def _build(self):
        canvas = tk.Canvas(self, highlightthickness=0, bg="#f0f0f0")
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(inner_id, width=e.width - 8))
        # 鼠标滚轮：仅右侧表单区域生效（Enter 绑定 / Leave 解绑，避免全局劫持）
        self._wheel_bound = False

        def _bind_wheel(_e=None):
            if self._wheel_bound:
                return
            canvas.bind_all("<MouseWheel>",
                            lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
            canvas.bind_all("<Button-4>",
                            lambda _e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>",
                            lambda _e: canvas.yview_scroll(1, "units"))
            self._wheel_bound = True

        def _unbind_wheel(_e=None):
            if not self._wheel_bound:
                return
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
            self._wheel_bound = False

        self.bind("<Enter>", _bind_wheel, add="+")
        self.bind("<Leave>", _unbind_wheel, add="+")
        canvas.bind("<Enter>", _bind_wheel, add="+")
        canvas.bind("<Leave>", _unbind_wheel, add="+")
        inner.bind("<Enter>", _bind_wheel, add="+")
        inner.bind("<Leave>", _unbind_wheel, add="+")
        self.bind("<Destroy>", lambda _e: _unbind_wheel(), add="+")
        self._wheel_bind = (_bind_wheel, _unbind_wheel)

        form = ttk.Frame(inner)
        form.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        r = 0
        self._group(form, r, GROUPS[0][1]); r += 1
        self._combo(form, r, "scene_family", list(SCENE_FAMILY),
                    bind=self._on_scene); r += 1
        self._combo(form, r, "scene_subtype", []); r += 1
        self._group(form, r, GROUPS[1][1]); r += 1
        self._combo(form, r, "product_family", list(PRODUCT_FAMILY),
                    bind=self._on_product); r += 1
        self._combo(form, r, "product_variant", []); r += 1
        self._group(form, r, GROUPS[2][1]); r += 1
        for f in ("material", "component", "function"):
            self._multiselect(form, r, f, MULTI_OPTIONS[f]); r += 1
        self._group(form, r, GROUPS[3][1]); r += 1
        self._combo(form, r, "action_group", list(ACTION_GROUP)); r += 1
        # 动作序列（有序）
        tk.Label(form, text="动作序列（按发生顺序）", bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=0, sticky=tk.NW, pady=3)
        seq_wrap = ttk.Frame(form)
        seq_wrap.grid(row=r, column=1, sticky=tk.W, padx=6)
        self.cand_seq = tk.Listbox(seq_wrap, selectmode=tk.SINGLE, height=5, width=20,
                                   exportselection=False, font=("Microsoft YaHei", 10))
        for a in ATOMIC_ACTION:
            self.cand_seq.insert(tk.END, cn("atomic_action", a))
        csb = ttk.Scrollbar(seq_wrap, orient="vertical", command=self.cand_seq.yview)
        self.cand_seq.configure(yscrollcommand=csb.set)
        self.cand_seq.grid(row=0, column=0, rowspan=5)
        csb.grid(row=0, column=1, rowspan=5, sticky=tk.NS)
        btns = ttk.Frame(seq_wrap)
        btns.grid(row=0, column=2, rowspan=5, padx=6)
        ttk.Button(btns, text="添加 →", command=self._seq_add, width=9).pack(pady=2)
        ttk.Button(btns, text="↑ 上移", command=lambda: self._seq_move(-1), width=9).pack(pady=2)
        ttk.Button(btns, text="↓ 下移", command=lambda: self._seq_move(1), width=9).pack(pady=2)
        ttk.Button(btns, text="移除", command=self._seq_remove, width=9).pack(pady=2)
        self.seq_list = tk.Listbox(seq_wrap, height=5, width=22,
                                   exportselection=False, font=("Microsoft YaHei", 10))
        self.seq_list.grid(row=0, column=3, rowspan=5)
        r += 1
        self._group(form, r, GROUPS[4][1]); r += 1
        self._combo(form, r, "shot_scale", list(SHOT_SCALE)); r += 1
        self._multiselect(form, r, "shot_role", MULTI_OPTIONS["shot_role"]); r += 1
        self._group(form, r, GROUPS[5][1]); r += 1
        self._combo(form, r, "people_presence", list(PEOPLE_PRESENCE)); r += 1
        self._combo(form, r, "product_visibility",
                    ["VISIBLE", "PARTIAL", "HIDDEN", "UNKNOWN"]); r += 1
        tk.Label(form, text="质量分（0-100）", bg="#f0f0f0", font=("Microsoft YaHei", 10)).grid(
            row=r, column=0, sticky=tk.W, pady=3)
        self.vars["quality"] = tk.StringVar()
        tk.Entry(form, textvariable=self.vars["quality"], width=32,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=1, sticky=tk.W, padx=6)
        r += 1
        self._group(form, r, GROUPS[6][1]); r += 1
        # 置信度/状态在顶部固定区（conf_var/status_var 由父窗口共享），表单内提示即可
        tk.Label(form, text="* 人工置信度", bg="#f0f0f0", fg="#b00000",
                 font=("Microsoft YaHei", 10, "bold")).grid(row=r, column=0, sticky=tk.W, pady=3)
        tk.Label(form, text="（在顶部工具栏选择）", bg="#f0f0f0", fg="#b00000",
                 font=("Microsoft YaHei", 10)).grid(row=r, column=1, sticky=tk.W, padx=6)
        r += 1
        tk.Label(form, text="* 审核状态", bg="#f0f0f0", fg="#b00000",
                 font=("Microsoft YaHei", 10, "bold")).grid(row=r, column=0, sticky=tk.W, pady=3)
        tk.Label(form, text="（在顶部工具栏选择）", bg="#f0f0f0", fg="#b00000",
                 font=("Microsoft YaHei", 10)).grid(row=r, column=1, sticky=tk.W, padx=6)
        r += 1
        tk.Label(form, text="备注", bg="#f0f0f0", font=("Microsoft YaHei", 10)).grid(
            row=r, column=0, sticky=tk.NW, pady=3)
        cmt_wrap = ttk.Frame(form)
        cmt_wrap.grid(row=r, column=1, sticky=tk.W, padx=6)
        self.vars["comment"] = tk.StringVar()
        tk.Entry(cmt_wrap, textvariable=self.vars["comment"], width=42,
                 font=("Microsoft YaHei", 10)).grid(row=0, column=0, columnspan=6, sticky=tk.W)
        quick = [("［成片］", "此视频为已剪辑成片，若需使用需按需裁剪"),
                 ("［素材片段］", "此视频为原始素材片段"),
                 ("［录屏］", "此视频为录屏内容"),
                 ("［价格/尺寸］", "视频主要讲价格或尺寸等业务参数"),
                 ("［纯画面无讲解］", "画面只有产品展示，无讲解"),
                 ("［颜色/配色］", "视频讲产品颜色/配色（颜色为业务属性，V2.1 无字段，备注记录）"),
                 ("［工艺/组装］", "视频展示组装/工艺过程（可配镜头角色-工艺展示）"),
                 ("［卡断/质量差］", "视频有卡断或质量差，需按需裁剪或标记低质量")]
        self._quick_btns = []
        for i, (tag, hint) in enumerate(quick):
            def _mk(tag=tag, hint=hint):
                def _ins():
                    cur = self.vars["comment"].get()
                    new = (cur + "；" if cur else "") + tag + hint
                    self.vars["comment"].set(new)
                return _ins
            b = ttk.Button(cmt_wrap, text=tag, command=_mk(), width=12)
            b.grid(row=1, column=i, padx=1, pady=2)
            self._quick_btns.append(b)
        # 响应式：宽度 <460 两列 / <620 三列 / 其余四列（重排已有按钮，不重建）
        cmt_wrap.bind("<Configure>", self._relayout_quick)

    def _relayout_quick(self, _e=None):
        try:
            w = self.winfo_width()
            cols = 2 if w < 460 else (3 if w < 620 else 4)
            for i, b in enumerate(self._quick_btns):
                b.grid_configure(row=1 + i // cols, column=i % cols, padx=1, pady=2)
        except Exception:
            pass

    # ---------------- 联动 ----------------
    def _on_scene(self, _e=None):
        f = self.vars["scene_family"].get()
        self.vars["scene_subtype"].set("")
        self.combos["scene_subtype"]["values"] = [
            cn("scene_subtype", o) for o in SCENE_SUBTYPE_BY_FAMILY.get(en("scene_family", f), [])]

    def _on_product(self, _e=None):
        f = self.vars["product_family"].get()
        self.vars["product_variant"].set("")
        self.combos["product_variant"]["values"] = [
            cn("product_variant", o) for o in PRODUCT_VARIANT_BY_FAMILY.get(en("product_family", f), [])]

    def _seq_add(self):
        sel = self.cand_seq.curselection()
        if sel:
            v = self.cand_seq.get(sel[0])
            self.seq.append(en("atomic_action", v))
            self._seq_refresh()

    def _seq_move(self, delta):
        sel = self.seq_list.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if 0 <= j < len(self.seq):
            self.seq[i], self.seq[j] = self.seq[j], self.seq[i]
            self._seq_refresh()
            self.seq_list.selection_set(j)

    def _seq_remove(self):
        sel = self.seq_list.curselection()
        if sel:
            del self.seq[sel[0]]
            self._seq_refresh()

    def _seq_refresh(self):
        self.seq_list.delete(0, tk.END)
        for i, a in enumerate(self.seq):
            self.seq_list.insert(tk.END, f"{i + 1}. {cn('atomic_action', a)}")

    # ---------------- 取值 / 重置 ----------------
    def _get(self, label: str) -> str:
        """双通道取值：StringVar + Combobox 显示值兜底（修复 readonly Combobox 偶发不同步）。"""
        v = ""
        if label in self.vars and hasattr(self.vars[label], "get"):
            v = self.vars[label].get() or ""
        if not v and label in self.combos:
            v = self.combos[label].get() or ""
        return v

    def collect(self) -> dict:
        def multi(label):
            lb = self.vars[label]
            return [en(label, lb.get(i)) for i in lb.curselection()]
        out = {}
        for label in ("scene_family", "scene_subtype", "product_family",
                      "product_variant", "action_group", "shot_scale",
                      "people_presence", "product_visibility", "quality", "comment"):
            if label in self.vars:
                out[label] = self._get(label)
        out["scene_family"] = en("scene_family", out.get("scene_family", ""))
        out["scene_subtype"] = en("scene_subtype", out.get("scene_subtype", ""))
        out["product_family"] = en("product_family", out.get("product_family", ""))
        out["product_variant"] = en("product_variant", out.get("product_variant", ""))
        out["action_group"] = en("action_group", out.get("action_group", ""))
        out["shot_scale"] = en("shot_scale", out.get("shot_scale", ""))
        out["people_presence"] = en("people_presence", out.get("people_presence", ""))
        out["product_visibility"] = en("product_visibility", out.get("product_visibility", ""))
        conf_raw = self.conf_var.get() if self.conf_var is not None else self._get("human_confidence")
        status_raw = self.status_var.get() if self.status_var is not None else self._get("review_status")
        out["human_confidence"] = {"高": "HIGH", "中": "MEDIUM", "低": "LOW"}.get(conf_raw, "")
        out["review_status"] = {"已审核": "REVIEWED", "需复核": "NEEDS_SECOND_REVIEW",
                                "金标准": "GOLD", "排除": "EXCLUDED"}.get(status_raw, "")
        out["material"] = multi("material")
        out["component"] = multi("component")
        out["function"] = multi("function")
        out["shot_role"] = multi("shot_role")
        out["action_sequence"] = list(self.seq)
        return out

    def reset(self):
        for label in self.vars:
            if isinstance(self.vars[label], tk.Listbox):
                self.vars[label].selection_clear(0, tk.END)
            else:
                self.vars[label].set("")
        if self.conf_var is not None:
            self.conf_var.set("")
        if self.status_var is not None:
            self.status_var.set("")
        self.seq = []
        self._seq_refresh()


class _ReviewBase(tk.Tk):
    """审核 UI 基类（进度 / 信息 / 播放 / 保存）。"""

    MANIFEST = None
    TABLE = ""
    TITLE = ""
    SOURCE_FIELD = ""
    HINT = ""

    def __init__(self, db_path):
        super().__init__()
        self._ui_built = False
        self._widget_baseline = None
        self.db_path = Path(db_path)
        from treecut.services.annotation_governance import AnnotationService
        self.svc = AnnotationService(self.db_path)
        self.items = self._load_items()
        self.done = self._done_set()
        self.queue = [it for it in self.items if it["segment_id"] not in self.done]
        self.idx = 0
        self.title(self.TITLE)
        # 窗口尺寸：默认 1280x820，最小 980x640，可缩放（不强制最大化）
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(1280, max(980, sw - 160))
        h = min(820, max(640, sh - 180))
        self.geometry(f"{w}x{h}")
        self.minsize(min(980, sw - 80), min(640, sh - 120))
        self.resizable(True, True)
        self.configure(bg="#f0f0f0")
        # root 统一 grid（toolbar/body 同一 parent）
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()
        if self.queue:
            self._load(0)
        else:
            self.pos.config(text="全部完成")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        # widget leak 守卫：首次构建完成后冻结基线
        self.after_idle(self._freeze_widget_baseline)

    def _load_items(self) -> list[dict]:
        p = Path(self.MANIFEST)
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8")).get("segments", [])

    def _done_set(self) -> set:
        """已完成集 = 本任务 manifest 成员 ∩ 表中已审 segment_id（避免共享表跨任务污染）。"""
        items = getattr(self, "items", None) or self._load_items()
        ids = {i["segment_id"] for i in items}
        if not ids:
            return set()
        with sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro",
                             uri=True) as conn:
            ph = ",".join("?" * len(ids))
            rows = conn.execute(f"SELECT segment_id FROM {self.TABLE} WHERE segment_id IN ({ph})",
                                list(ids)).fetchall()
            return {r[0] for r in rows}

    def _build(self):
        if self._ui_built:
            raise RuntimeError("Review UI must only be built once")
        self._ui_built = True
        self._build_toolbar()
        self._build_body()
        # 联动：必选完成后保存按钮才可用
        self.conf_var.trace_add("write", self._on_mandatory)
        self.status_var.trace_add("write", self._on_mandatory)
        self._on_mandatory()

    def _build_toolbar(self):
        top = tk.Frame(self, bg="#e8f0fe", padx=8, pady=6)
        top.grid(row=0, column=0, sticky="ew")
        self.pos = tk.Label(top, text="", bg="#e8f0fe",
                            font=("Microsoft YaHei", 13, "bold"))
        self.pos.pack(side=tk.LEFT)
        self.progress = tk.Label(top, text="", bg="#e8f0fe",
                                 font=("Microsoft YaHei", 11))
        self.progress.pack(side=tk.LEFT, padx=20)
        tk.Label(top, text=f"词典：{DICTIONARY_VERSION_V2_1}（中文显示/英文入库）",
                 bg="#e8f0fe", font=("Microsoft YaHei", 9), fg="#555").pack(side=tk.RIGHT)
        # 保存按钮：防呆（未选置信度/状态时禁用，选完才亮）
        self.save_btn = ttk.Button(top, text="✓ 保存并下一题", command=self._save,
                                   state="disabled")
        self.save_btn.pack(side=tk.RIGHT, padx=8)
        self.mandatory_hint = tk.Label(top, text="⚠ 请先选置信度/状态（每题目必选）",
                                       bg="#ffe0e0", fg="#b00000",
                                       font=("Microsoft YaHei", 9, "bold"))
        self.mandatory_hint.pack(side=tk.RIGHT)
        # 固定必选区：置信度/状态 永远在顶部可见（修复"滚到底部看不见漏选"）
        self.conf_var = tk.StringVar()
        self.status_var = tk.StringVar()
        tk.Label(top, text="*置信度", bg="#e8f0fe", fg="#b00000",
                 font=("Microsoft YaHei", 10, "bold")).pack(side=tk.RIGHT)
        ttk.Combobox(top, textvariable=self.conf_var, values=("高", "中", "低"),
                     width=6, state="readonly", font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=4)
        tk.Label(top, text="*状态", bg="#e8f0fe", fg="#b00000",
                 font=("Microsoft YaHei", 10, "bold")).pack(side=tk.RIGHT)
        ttk.Combobox(top, textvariable=self.status_var,
                     values=("已审核", "需复核", "金标准", "排除"),
                     width=9, state="readonly", font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=4)
        tk.Label(top, text="每题目必选：", bg="#e8f0fe", fg="#b00000",
                 font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT)
        ttk.Button(top, text="跳过", command=lambda: self._load(self.idx + 1)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top, text="上一题", command=lambda: self._load(self.idx - 1)).pack(side=tk.RIGHT, padx=4)

    def _build_body(self):
        """body（左栏+右栏滚动表单）只在此创建一次。"""
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        left = ttk.Frame(paned, width=430)
        paned.add(left, weight=0)
        # 信息卡片
        card = tk.Frame(left, bg="#ffffff", highlightbackground="#ccc",
                        highlightthickness=1)
        card.pack(fill=tk.X, padx=4, pady=2)
        self.info = tk.Text(card, wrap=tk.WORD, font=("Microsoft YaHei", 10),
                            bg="#ffffff", height=8, borderwidth=0)
        self.info.pack(fill=tk.X, padx=8, pady=6)
        self.note = tk.Label(card, text="", bg="#fffbe6", anchor=tk.W, justify=tk.LEFT,
                             font=("Microsoft YaHei", 9), wraplength=400, padx=6, pady=4)
        self.note.pack(fill=tk.X)
        # 播放按钮（经 PlaybackController：防重复 launch + 点击后短暂禁用）
        self.pb = PlaybackController(on_launch=lambda mode, path: None)
        btn = tk.Frame(left)
        btn.pack(fill=tk.X, padx=4, pady=6)
        self._btn_ctx = ttk.Button(btn, text="▶ 播放本段（前后3秒）",
                                   command=self._play_context, width=24)
        self._btn_ctx.pack(fill=tk.X, pady=2)
        self._btn_full = ttk.Button(btn, text="▶ 播放完整视频",
                                    command=self._play_full, width=24)
        self._btn_full.pack(fill=tk.X, pady=2)
        # 提示
        tk.Label(left, text=self.HINT, bg="#f0f0f0", justify=tk.LEFT,
                 font=("Microsoft YaHei", 9), wraplength=410,
                 fg="#444").pack(fill=tk.X, padx=8, pady=6)

        right = ttk.Frame(paned, width=600)
        paned.add(right, weight=1)
        self.form = _V21Form(right, self._save,
                             conf_var=self.conf_var, status_var=self.status_var)
        self.form.pack(fill=tk.BOTH, expand=True)

    def _on_mandatory(self, *_a):
        """防呆：置信度+状态都选完 → 保存按钮可用；否则禁用并提示。

        本方法只更新状态，禁止创建任何 Widget。
        """
        ok = bool((self.conf_var.get() or "").strip()) and bool((self.status_var.get() or "").strip())
        self.save_btn.config(state="normal" if ok else "disabled")
        if ok:
            self.mandatory_hint.config(text="✓ 已选择置信度和审核状态", bg="#e8f0fe")
        else:
            self.mandatory_hint.config(text="⚠ 请先选置信度/状态（每题目必选）", bg="#ffe0e0")

    def _seg_info(self, sid) -> tuple[str, int, int]:
        with sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro",
                             uri=True) as conn:
            r = conn.execute(
                "SELECT asset_id, start_ms, end_ms FROM segments WHERE segment_id=?",
                (sid,)).fetchone()
        if not r:
            return "", 0, 0
        return r[0], r[1], r[2]

    def _load(self, idx: int):
        if not self.queue:
            self.pos.config(text="全部完成")
            return
        self.idx = idx % len(self.queue)
        it = self.queue[self.idx]
        self.current = it
        sid = it["segment_id"]
        self.pos.config(text=f"{self.idx + 1} / {len(self.queue)}")
        asset, start, end = self._seg_info(sid)
        self.current_start, self.current_end = start, end
        info = [f"片段编号：{sid[:20]}…", f"素材：{asset[:20]}…",
                f"时间范围：{start} - {end} ms（共 {(end - start) // 1000} 秒）"]
        if self.SOURCE_FIELD:
            info.append(f"采样原因：{it.get(self.SOURCE_FIELD, '')}")
        if it.get("hits"):
            info.append(f"命中：{', '.join(it['hits'][:6])}")
        if it.get("conflict_fields"):
            info.append(f"冲突字段：{', '.join(d['field'] for d in it['conflict_fields'][:8])}")
        self.info.delete("1.0", tk.END)
        self.info.insert(tk.END, "\n".join(info))
        self.note.config(text="")
        self.form.reset()
        self.progress.config(text=f"已完成 {len(self.done)} / {len(self.items)}")
        # widget leak 守卫：切题不得增加 widget
        self.after_idle(self._assert_widget_stable)

    # ---------------- Widget Leak Guard ----------------
    def _count_widgets(self, w=None) -> int:
        w = w or self
        n = 1
        for c in w.winfo_children():
            n += self._count_widgets(c)
        return n

    def _freeze_widget_baseline(self):
        self.update_idletasks()
        self._widget_baseline = self._count_widgets()

    def _assert_widget_stable(self):
        if self._widget_baseline is None:
            return
        cur = self._count_widgets()
        if cur != self._widget_baseline:
            import logging
            logging.getLogger("review_ui").error(
                "UI_WIDGET_LEAK baseline=%s current=%s diff=%s",
                self._widget_baseline, cur, cur - self._widget_baseline)

    # ---------------- 播放 ----------------
    def _resolve_asset(self, asset_id: str) -> str:
        try:
            from treecut.services.identity import AssetRepository
            p = AssetRepository(self.db_path).resolve_path(asset_id)
            return p if p and os.path.exists(p) else ""
        except Exception:
            return ""

    def _play_full(self):
        if not getattr(self, "current", None):
            return
        path = self._resolve_asset(self._seg_info(self.current["segment_id"])[0])
        if not path:
            messagebox.showwarning("无法播放", "素材视频文件不可达")
            return
        launched = self.pb.play_full(path)
        if launched:
            self._debounce_btn(self._btn_full)

    def _debounce_btn(self, btn):
        """点击后按钮短暂禁用（防连点），成功 launch 后恢复。"""
        try:
            btn.config(state="disabled")
            self.after(PlaybackController.DEBOUNCE_MS + 150, lambda: btn.config(state="normal"))
        except Exception:
            pass

    def _play_context(self):
        if not getattr(self, "current", None):
            return
        asset = self._seg_info(self.current["segment_id"])[0]
        path = self._resolve_asset(asset)
        if not path:
            messagebox.showwarning("无法播放", "素材视频文件不可达")
            return
        if not self.pb.play_context(path, self.current_start, self.current_end):
            return  # debounce 内重复请求忽略
        self._debounce_btn(self._btn_ctx)
        self.note.config(text="正在提取片段…（约3-8秒）")
        self.update_idletasks()
        out = os.path.join(tempfile.gettempdir(),
                           f"treecut_preview_{self.current['segment_id'][:12]}.mp4")
        try:
            deadline = time.time() + 15
            while time.time() < deadline:
                if os.path.exists(out) and os.path.getsize(out) > 1000:
                    break
                time.sleep(0.4)
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                os.startfile(out)  # type: ignore[attr-defined]
                self.note.config(text="")
            else:
                self.note.config(text="片段提取超时，已打开完整视频")
                os.startfile(path)  # type: ignore[attr-defined]
        except Exception as e:
            messagebox.showerror("播放错误", str(e))

    # ---------------- 保存 ----------------
    def _save_log(self, values: dict, ok: bool, msg: str, status: str):
        """保存尝试日志（追加文件），用于诊断偶发校验失败。"""
        try:
            log_dir = self.db_path.parent.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            line = "\t".join([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                self.TABLE,
                self.current["segment_id"] if getattr(self, "current", None) else "",
                repr(values.get("human_confidence", "")),
                repr(values.get("review_status", "")),
                str(ok), msg.replace("\t", " "), status,
            ])
            with open(log_dir / "review_save_log.tsv", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _save(self):
        if not getattr(self, "current", None):
            return
        values = self.form.collect()
        ok, msg, status = validate_v21(
            values, values["human_confidence"], values["review_status"],
            values["comment"])
        self._save_log(values, ok, msg, status)
        if not ok:
            messagebox.showerror("无法保存", msg)
            return
        if msg:
            messagebox.showwarning("状态已调整", msg)
        self._persist(values, status)
        self.done.add(self.current["segment_id"])
        self.queue = [it for it in self.items if it["segment_id"] not in self.done]
        self.progress.config(text=f"已完成 {len(self.done)} / {len(self.items)}")
        if len(self.done) >= len(self.items):
            messagebox.showinfo("批次完成",
                                f"{self.TITLE}\n\n{len(self.done)}/{len(self.items)} 全部完成。\n"
                                "请进行 Phase 3 人工数据结算（暂不学习）。")
        if self.queue:
            self._load(0)
        else:
            self.pos.config(text="全部完成")

    def _persist(self, values: dict, status: str):
        raise NotImplementedError


class AdjudicationV1App(_ReviewBase):
    """THIRD_ADJUDICATION_V1：34 条第三次独立裁决 → human_annotation_v3。"""

    MANIFEST = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\THIRD_ADJUDICATION_V1.json"
    TABLE = "human_annotation_v3"
    TITLE = "THIRD_ADJUDICATION_V1 — 34 条第三次独立裁决"
    SOURCE_FIELD = ""
    HINT = ("审核说明：已隐藏 AI 答案、第一次答案、第二次答案，请只看视频独立判断。\n"
            "· 材质/组件/功能/镜头角色：点击即多选，再点一下取消\n"
            "· 动作按发生顺序逐个添加（如 拉出→缩回）\n"
            "· 场景/产品先选大类，再选子类\n"
            "· 看不清就选：未知 + 低 + 需复核，不要硬猜")

    def _persist(self, values: dict, status: str):
        """Stage 2 STEP 0：统一走 AnnotationService（不直接写 SQL）。"""
        self.svc.save_v3(self.current["segment_id"], values,
                         values["human_confidence"], status,
                         operator=os.environ.get("USERNAME", ""))


class TargetedReviewV1App(_ReviewBase):
    """TARGETED_REVIEW_BATCH_V1：60 条新 Segment 主动学习审核 → targeted_human_review_v1。"""

    MANIFEST = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\TARGETED_REVIEW_BATCH_V1.json"
    TABLE = "targeted_human_review_v1"
    TITLE = "TARGETED_REVIEW_BATCH_V1 — 60 条新片段人工标注"
    SOURCE_FIELD = "selection_reason"
    HINT = ("审核说明：已隐藏 AI 预测结果，请只看视频独立标注。\n"
            "这批是主动学习补覆盖的新样本，可能出现非工厂/实木/水槽/电器等少见场景，属正常。\n"
            "· 材质/组件/功能/镜头角色：点击即多选，再点一下取消\n"
            "· 动作按发生顺序添加\n"
            "· 看不清就选：未知 + 低 + 需复核")

    def _persist(self, values: dict, status: str):
        """Stage 2 STEP 0：统一走 AnnotationService（不直接写 SQL）。"""
        it = self.current
        self.svc.save_targeted_review(it["segment_id"], values,
                                      values["human_confidence"], status,
                                      selection_reason=it.get("selection_reason", ""),
                                      operator=os.environ.get("USERNAME", ""))


# ---------------------------------------------------------------------------
# Stage 2 — 业务认知评审（Human Business Review 24）
# 评审对象不是视觉标签，而是"该片段的证据支持哪些业务意义"。
# 盲审：不显示 AI claims/affinity/confidence/rule/knowledge。
# 独立 Human Truth：每个多标签字段显示完整固定 Taxonomy（非 AI 候选），
# Human 从全量独立勾选所有成立的标签 → Recall 真正可计算。
# ---------------------------------------------------------------------------

VERDICT_CN = {"SUPPORTED": "支持", "NOT_SUPPORTED": "不支持", "UNSURE": "不确定"}
AFFINITY_CN = {"STRONG": "强", "MEDIUM": "中", "WEAK": "弱",
               "NOT_SUPPORTED": "不支持", "UNKNOWN": "未知"}
_AFFINITY_TO_EN = {v: k for k, v in AFFINITY_CN.items()}


def _affinity_to_en(raw: str) -> str:
    """中文亲和度 → 英文（未知/空 → UNKNOWN，保证存库一致）。"""
    raw = (raw or "").strip()
    if not raw:
        return "UNKNOWN"
    return _AFFINITY_TO_EN.get(raw, raw.upper())

# 默认完整 Taxonomy（运行时从 manifest 读取，避免硬编码与 AI 耦合）
DEFAULT_TAXONOMY = {
    "user_needs": [], "business_values": [], "decision_factors": [],
    "search_intents": [], "shot_functions": [], "trust_signals": [],
    "content_roles": [{"id": "TRAFFIC", "cn": "流量"}, {"id": "SEARCH", "cn": "搜索"},
                      {"id": "TRUST", "cn": "信任"}, {"id": "CONVERSION", "cn": "转化"}],
    "mother_themes": [{"id": "SPACE_SOLUTION", "cn": "空间解决方案"},
                      {"id": "FAMILY_SCENE", "cn": "家庭生活场景"},
                      {"id": "DECISION_AVOID_PIT", "cn": "决策避坑"},
                      {"id": "AESTHETIC_STYLE", "cn": "审美风格"},
                      {"id": "CRAFT_TRUST", "cn": "工艺信任"}],
    "affinity_levels": ["STRONG", "MEDIUM", "WEAK", "NOT_SUPPORTED", "UNKNOWN"],
}


class _BusinessCognitionReviewForm(tk.Frame):
    """独立 Human Business Truth 表单（blind）。

    - 多标签字段（user_needs/business_values/decision_factors/search_intents/
      shot_functions/trust_signals）：完整固定 Taxonomy 多选，Human 独立勾选
      所有成立的标签（可包含 AI 未预测的 → Recall 可计算）
    - content_role_affinity（4 类）与 mother_theme_affinity（5 类）：
      每个维度独立 5 级评级（STRONG/MEDIUM/WEAK/NOT_SUPPORTED/UNKNOWN）
    - overall_unknown_or_insufficient / conflicting_evidence_observed / comment
    保存内容即 Human Truth；AI 信息零进入。
    """

    def __init__(self, master, on_save, conf_var=None, status_var=None, taxonomy=None):
        super().__init__(master)
        self.on_save = on_save
        self.conf_var = conf_var
        self.status_var = status_var
        self.tax = taxonomy or DEFAULT_TAXONOMY
        self.vars = {}
        self._build()

    # 多选 Listbox（点击即选/再点取消）
    def _multiselect(self, parent, row, label, options):
        tk.Label(parent, text=label, bg="#f0f0f0", anchor=tk.NW,
                 font=("Microsoft YaHei", 10, "bold")).grid(
            row=row, column=0, sticky=tk.NW, pady=2)
        wrap = ttk.Frame(parent)
        wrap.grid(row=row, column=1, sticky=tk.W, padx=6)
        lb = tk.Listbox(wrap, selectmode=tk.MULTIPLE, height=min(8, max(4, len(options))),
                        width=46, exportselection=False, font=("Microsoft YaHei", 9))
        for o in options:
            lb.insert(tk.END, f"{o['cn']}（{o['id']}）")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.vars[label] = lb
        return lb

    def _affinity_row(self, parent, row, label, key):
        tk.Label(parent, text=label, bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=row, column=0, sticky=tk.W, pady=2)
        var = tk.StringVar()
        cb = ttk.Combobox(parent, textvariable=var,
                          values=[AFFINITY_CN[l] for l in self.tax["affinity_levels"]],
                          width=10, state="readonly", font=("Microsoft YaHei", 10))
        cb.grid(row=row, column=1, sticky=tk.W, padx=6)
        self.vars[key] = var
        return var

    def _build(self):
        canvas = tk.Canvas(self, highlightthickness=0, bg="#f0f0f0")
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(inner_id, width=e.width - 8))
        form = ttk.Frame(inner)
        form.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        r = 0
        hint = ("请从【完整清单】独立勾选所有该片段证据支持的标签（可多选，再点取消）。\n"
                "只判断证据支持的 Business Meaning，不重标视觉事实；不确定就不勾。")
        tk.Label(form, text=hint, bg="#fff8e1", anchor=tk.W, wraplength=520,
                 font=("Microsoft YaHei", 9), foreground="#8a6d00").grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(2, 6)); r += 1

        # A. user_needs
        tk.Label(form, text="A. 用户需求 user_needs[]（多选，完整清单）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "user_needs", self.tax["user_needs"]); r += 1

        # B. business_values
        tk.Label(form, text="B. 商业价值 business_values[]（多选，完整清单）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "business_values", self.tax["business_values"]); r += 1

        # C. decision_factors
        tk.Label(form, text="C. 决策因素 decision_factors[]（多选，完整清单）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "decision_factors", self.tax["decision_factors"]); r += 1

        # D. trust_signals
        tk.Label(form, text="D. 信任信号 trust_signals[]（多选，完整清单）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "trust_signals", self.tax["trust_signals"]); r += 1

        # E. search_intents
        tk.Label(form, text="E. 搜索意图候选 search_intent_candidates[]（多选）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "search_intents", self.tax["search_intents"]); r += 1

        # F. shot_functions
        tk.Label(form, text="F. 镜头功能候选 shot_function_candidates[]（多选）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        self._multiselect(form, r, "shot_functions", self.tax["shot_functions"]); r += 1

        # G. content_role_affinity（全部 4 维独立评级）
        tk.Label(form, text="G. 内容角色亲和 content_role_affinity（4 类全部独立评级）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        for role in self.tax["content_roles"]:
            self._affinity_row(form, r, f"  {role['cn']}（{role['id']}）", f"role_{role['id']}"); r += 1

        # H. mother_theme_affinity（全部 5 维独立评级）
        tk.Label(form, text="H. 母题亲和 mother_theme_affinity（5 类全部独立评级）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        for th in self.tax["mother_themes"]:
            self._affinity_row(form, r, f"  {th['cn']}（{th['id']}）", f"theme_{th['id']}"); r += 1

        # I. overall_unknown_or_insufficient
        tk.Label(form, text="I. 整体证据不足/未知（该片段不足以做业务判断）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        tk.Label(form, text="选『是』表示：宁可 Unknown，不制造 Human 过标",
                 bg="#f0f0f0", anchor=tk.W, font=("Microsoft YaHei", 9),
                 foreground="#666").grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=2); r += 1
        tk.Label(form, text="整体不足/未知", bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=0, sticky=tk.W, pady=2)
        self.vars["overall_unknown"] = tk.StringVar()
        ttk.Combobox(form, textvariable=self.vars["overall_unknown"],
                     values=("NO", "YES"), width=10, state="readonly",
                     font=("Microsoft YaHei", 10)).grid(row=r, column=1, sticky=tk.W, padx=6); r += 1

        # J. conflicting_evidence_observed
        tk.Label(form, text="J. 证据冲突观察（视频中是否出现话语↔画面矛盾）",
                 bg="#e8f0fe", anchor=tk.W, font=("Microsoft YaHei", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.EW, pady=(6, 2)); r += 1
        tk.Label(form, text="例：讲解说'家里/客户家'但画面是工厂展台；说'实木'但画面材质存疑",
                 bg="#f0f0f0", anchor=tk.W, font=("Microsoft YaHei", 9),
                 foreground="#666").grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=2); r += 1
        tk.Label(form, text="冲突观察", bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=0, sticky=tk.W, pady=2)
        self.vars["conflict_observed"] = tk.StringVar()
        ttk.Combobox(form, textvariable=self.vars["conflict_observed"],
                     values=("NONE", "SCENE_ASR_CONFLICT", "MATERIAL_WEAK_CONFLICT", "UNSURE"),
                     width=28, state="readonly", font=("Microsoft YaHei", 10)).grid(
            row=r, column=1, sticky=tk.W, padx=6); r += 1

        # K. comment
        tk.Label(form, text="K. 备注", bg="#f0f0f0", anchor=tk.W,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=0, sticky=tk.NW, pady=3)
        self.vars["comment"] = tk.StringVar()
        tk.Entry(form, textvariable=self.vars["comment"], width=46,
                 font=("Microsoft YaHei", 10)).grid(row=r, column=1, sticky=tk.W, padx=6); r += 1

        tk.Label(form, text="* 人工置信度 / 审核状态 在顶部工具栏选择（必选）",
                 bg="#f0f0f0", fg="#b00000", font=("Microsoft YaHei", 9, "bold")).grid(
            row=r, column=0, columnspan=2, sticky=tk.W, pady=(12, 2))

    def _multi_selected(self, label):
        lb = self.vars[label]
        out = []
        for i in lb.curselection():
            txt = lb.get(i)
            # 格式：cn（ID）
            if "（" in txt and txt.endswith("）"):
                out.append(txt.split("（", 1)[1][:-1])
        return out

    def collect(self) -> dict:
        out = {
            "user_needs": self._multi_selected("user_needs"),
            "business_values": self._multi_selected("business_values"),
            "decision_factors": self._multi_selected("decision_factors"),
            "trust_signals": self._multi_selected("trust_signals"),
            "search_intents": self._multi_selected("search_intents"),
            "shot_functions": self._multi_selected("shot_functions"),
            "role_affinity": {},
            "theme_affinity": {},
            "overall_unknown": self.vars.get("overall_unknown").get() or "",
            "conflict_observed": self.vars.get("conflict_observed").get() or "",
            "comment": (self.vars.get("comment").get() if self.vars.get("comment") else ""),
        }
        for k, v in self.vars.items():
            if k.startswith("role_"):
                # Combobox 显示中文，存库转回英文（AFFINITY_CN 反查）
                out["role_affinity"][k[len("role_"):]] = _affinity_to_en(v.get())
            elif k.startswith("theme_"):
                out["theme_affinity"][k[len("theme_"):]] = _affinity_to_en(v.get())
        conf_raw = self.conf_var.get() if self.conf_var is not None else ""
        status_raw = self.status_var.get() if self.status_var is not None else ""
        out["human_confidence"] = {"高": "HIGH", "中": "MEDIUM", "低": "LOW"}.get(conf_raw, "")
        out["review_status"] = {"已审核": "REVIEWED", "需复核": "NEEDS_SECOND_REVIEW",
                                "金标准": "GOLD", "排除": "EXCLUDED"}.get(status_raw, "")
        return out

    def reset(self):
        for k, v in self.vars.items():
            if isinstance(v, tk.Listbox):
                v.selection_clear(0, tk.END)
            else:
                v.set("")
        if self.conf_var is not None:
            self.conf_var.set("")
        if self.status_var is not None:
            self.status_var.set("")


def validate_business_cognition(values: dict) -> tuple[bool, str]:
    """业务认知评审校验：置信度/状态必选；UNKNOWN 纪律：不逼用户选业务意义。

    允许整字段/全部维度 UNKNOWN（宁可 Unknown 不制造过标）。
    """
    conf = (values.get("human_confidence") or "").strip().upper()
    status = (values.get("review_status") or "").strip().upper()
    if conf not in ("HIGH", "MEDIUM", "LOW"):
        return False, "人工置信度未选择（顶部工具栏）"
    if status not in ("REVIEWED", "NEEDS_SECOND_REVIEW", "GOLD", "EXCLUDED"):
        return False, "审核状态未选择（顶部工具栏）"
    return True, ""


def main():
    import sys as _sys
    mode = _sys.argv[1] if len(_sys.argv) > 1 else "adjudication"
    db = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
    if mode == "targeted":
        app = TargetedReviewV1App(db)
    else:
        app = AdjudicationV1App(db)
    app.mainloop()


if __name__ == "__main__":
    main()
