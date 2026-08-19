"""Statistics dashboard dialog."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from treecut.stats import collect_stats


class DashboardDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, context):
        super().__init__(master)
        self.title("数据看板")
        self.geometry("720x560")
        self.transient(master)
        self._build(collect_stats(context))

    def _build(self, stats: dict) -> None:
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        rows = []
        sources = stats["sources"]
        rows.append(("素材来源数", str(sources["sources"])))
        rows.append(("在线来源", str(sources["online_sources"])))
        for media_type, info in (sources.get("available") or {}).items():
            rows.append((f"可用素材（{media_type}）", f"{info['count']} 个"))
        for state, count in (stats["analysis"] or {}).items():
            rows.append((f"分析任务（{state}）", str(count)))
        for state, count in (stats["production_jobs"] or {}).items():
            rows.append((f"制作任务（{state}）", str(count)))
        rows.append(("产出项目数", str(stats["projects"])))
        rows.append(("反馈记录", str(stats["feedback_records"])))
        production = stats.get("production_stats") or {}
        if production:
            rows.append(("制作成功/失败", f"{production.get('success', 0)} / {production.get('failed', 0)}"))
            rows.append(("制作失败率", f"{production.get('failure_rate', 0)}%"))
            rows.append(("制作平均耗时", f"{production.get('avg_seconds', 0)} 秒"))
            rows.append(("制作最长耗时", f"{production.get('max_seconds', 0)} 秒"))
        rows.append(("模型方案", " / ".join(f"{k}={v}" for k, v in (stats["model_plan"] or {}).items())))

        tree = ttk.Treeview(frame, columns=("item", "value"), show="headings")
        tree.heading("item", text="项目")
        tree.heading("value", text="数值")
        tree.column("item", width=260)
        tree.column("value", width=380)
        for item, value in rows:
            tree.insert("", "end", values=(item, value))
        tree.pack(fill="both", expand=True)
