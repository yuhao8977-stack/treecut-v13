"""Beginner-friendly native Windows desktop interface."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

from treecut.application import CreativeRequest, ProductionService, open_job_journal
from treecut.bootstrap import bootstrap
from treecut.library import Catalog
from treecut.learning import FeedbackStore
from treecut.config.settings import save_settings
from treecut.platform.paths import RuntimePaths
from treecut.platform.single_instance import SingleInstanceLock


class TreeCutDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        from treecut.platform.dpi import apply_tk_scaling
        scale = apply_tk_scaling(self)
        self.title("树剪 v13")
        self.geometry(f"{int(920 * scale)}x{int(720 * scale)}")
        self.minsize(int(800 * scale), int(620 * scale))
        self.context = bootstrap()
        self.catalog = Catalog(self.context.paths.databases / "materials.db")
        self.feedback = FeedbackStore(self.context.paths.databases / "feedback.db")
        self.job_journal = open_job_journal(self.context.paths.databases)
        self.session_id = uuid.uuid4().hex
        self.interrupted_count = self.job_journal.mark_interrupted(self.session_id)
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self._analysis_cancel = threading.Event()
        self._agent_guard_scheduled = False
        from treecut.scheduler import ScheduleStore, ScheduleThread
        self.schedule_store = ScheduleStore(
            self.context.paths.data_root / "config" / "schedule.json",
        )
        self._schedule_thread = ScheduleThread(self.schedule_store, on_due=self._on_scheduled)
        self._schedule_thread.start()
        threading.Thread(target=self._housekeeping_loop, daemon=True).start()
        self._remote_stop = threading.Event()
        self._maybe_start_remote_agent()
        self._build()
        self.after(150, self._drain_messages)
        self.after(300, self._maybe_show_welcome)
        self._policy_blocked = False
        self.after(5000, self._apply_remote_policy)
        self._ensure_remote_autostart()
        self._ensure_desktop_shortcut()

    def _ensure_desktop_shortcut(self) -> None:
        """Portable copies have no installer, so create the desktop shortcut here."""
        try:
            from treecut.platform.shortcuts import create_desktop_shortcut
            create_desktop_shortcut(self.context.paths.install_root)
        except Exception:
            pass

    def _ensure_remote_autostart(self) -> None:
        """Link software startup with the remote assistant; self-register boot entries."""
        try:
            from treecut.remote.autostart import ensure_autostart
            from treecut.remote.config import load_config
            from treecut.remote.roles import is_master
            managed = is_master(self.context.paths) or load_config(
                self.context.paths.data_root / "config" / "remote.json").valid()
            if not managed:
                return
            if is_master(self.context.paths):
                ensure_autostart("hub", self.context.paths.install_root)
            else:
                # 独立后台代理：桌面程序关掉后主机仍能远程启动/控制。
                ensure_autostart("agent", self.context.paths.install_root)
            ensure_autostart("desktop", self.context.paths.install_root)
        except Exception:
            pass

    def _build(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="树剪 v13", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        plan = self.context.model_plan
        ttk.Label(root, text=f"当前模式：{plan.profile} ｜ 画面：{plan.vision} ｜ 语音：{plan.speech} ｜ 配音：{plan.tts}").pack(anchor="w", pady=(2, 14))

        source_box = ttk.LabelFrame(root, text="第一步：添加素材文件夹", padding=10)
        source_box.pack(fill="x")
        saved_sources = self.context.settings.material_sources
        initial_source = next((item for item in saved_sources if Path(item).is_dir()), "")
        self.source_var = tk.StringVar(value=initial_source)
        ttk.Entry(source_box, textvariable=self.source_var).pack(side="left", fill="x", expand=True)
        ttk.Button(source_box, text="选择文件夹", command=self._choose_source).pack(side="left", padx=6)
        self.scan_button = ttk.Button(source_box, text="扫描素材", command=self._scan)
        self.scan_button.pack(side="left")
        self.cancel_button = ttk.Button(source_box, text="停止分析", command=self._cancel_analysis, state="disabled")
        self.cancel_button.pack(side="left", padx=6)

        brief = ttk.LabelFrame(root, text="第二步：填写需求", padding=10)
        brief.pack(fill="both", expand=True, pady=10)
        ttk.Label(brief, text="产品卖点 / 希望匹配的画面").pack(anchor="w")
        self.selling = tk.Text(brief, height=4, wrap="word")
        self.selling.pack(fill="x", pady=(3, 10))
        self.selling.insert("1.0", "小户型岛台，伸缩设计，分区收纳，实用尺寸，家庭办公和聚餐")
        ttk.Label(brief, text="配音文案").pack(anchor="w")
        self.narration = tk.Text(brief, height=7, wrap="word")
        self.narration.pack(fill="both", expand=True, pady=(3, 8))
        self.narration.insert("1.0", "小户型也能拥有实用岛台。伸缩设计兼顾办公、用餐和聚会。分区收纳让常用物品随手可取。合理定制高度、宽度和台面厚度，让小空间更舒适。")
        ttk.Button(brief, text="按卖点生成配音文案", command=self._generate_narration).pack(anchor="w")

        options = ttk.Frame(brief)
        options.pack(fill="x")
        ttk.Label(options, text="目标时长（秒）").pack(side="left")
        self.duration_var = tk.DoubleVar(value=self.context.settings.default_duration)
        ttk.Spinbox(options, from_=5, to=300, width=7, textvariable=self.duration_var).pack(side="left", padx=(4, 16))
        ttk.Label(options, text="画幅").pack(side="left")
        self.preset_labels = {
            "竖屏 9:16": "vertical", "横屏 16:9": "horizontal", "方屏 1:1": "square",
            "抖音（竖屏）": "douyin", "快手（竖屏）": "kuaishou", "小红书（方屏）": "xiaohongshu",
        }
        self.preset_display = tk.StringVar(value="竖屏 9:16")
        ttk.Combobox(options, textvariable=self.preset_display, state="readonly", width=14,
                     values=tuple(self.preset_labels)).pack(side="left", padx=(4, 16))
        ttk.Label(options, text="风格").pack(side="left")
        self.style_labels = {"自然": "natural", "暖色": "warm", "鲜艳": "vivid"}
        self.style_display = tk.StringVar(value="自然")
        ttk.Combobox(options, textvariable=self.style_display, state="readonly", width=8,
                     values=tuple(self.style_labels)).pack(side="left", padx=(4, 16))
        ttk.Label(options, text="语速").pack(side="left")
        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(options, from_=0.8, to=1.5, increment=0.1,
                    textvariable=self.speed_var, width=6).pack(side="left", padx=(4, 16))
        ttk.Label(options, text="水印").pack(side="left")
        self.watermark_var = tk.StringVar(value="")
        ttk.Entry(options, textvariable=self.watermark_var, width=18).pack(side="left", padx=(4, 4))
        ttk.Button(options, text="选择水印图片", command=self._choose_watermark).pack(side="left")
        default_mp4, default_draft = self.context.settings.output_flags()
        self.mp4_var = tk.BooleanVar(value=default_mp4)
        self.draft_var = tk.BooleanVar(value=default_draft)
        ttk.Checkbutton(options, text="导出 MP4 成片", variable=self.mp4_var).pack(side="left")
        ttk.Checkbutton(options, text="导出剪映草稿", variable=self.draft_var).pack(side="left", padx=12)

        action = ttk.Frame(root)
        action.pack(fill="x")
        self.generate_button = ttk.Button(action, text="开始自动制作", command=self._generate)
        self.generate_button.pack(side="left")
        ttk.Button(action, text="素材库管理", command=self._show_library).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="任务记录 / 重试", command=self._show_jobs).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="设置", command=self._open_settings).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="备份/清理", command=self._open_maintenance).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="检查更新", command=self._check_updates).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="批量生产", command=self._batch_production).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="定时生产", command=self._open_schedule).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="数据看板", command=self._open_dashboard).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="使用说明", command=self._open_help).pack(side="left", padx=(8, 0))
        ttk.Button(action, text="运行日志", command=self._open_log).pack(side="left", padx=(8, 0))
        action2 = ttk.Frame(root)
        action2.pack(fill="x", pady=(8, 0))
        from treecut.remote.roles import is_master
        if is_master(self.context.paths):
            ttk.Button(action2, text="远程管理（主程序：监控与下发）",
                       command=self._open_remote_management).pack(side="left")
        self.progress = ttk.Progressbar(action2, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=12)
        initial_status = (f"发现 {self.interrupted_count} 个上次被中断的任务，可点击“任务记录 / 重试”"
                          if self.interrupted_count
                          else "首次使用：先选素材文件夹 → 扫描素材 → 填卖点 → 开始自动制作")
        self.status_var = tk.StringVar(value=initial_status)
        ttk.Label(root, textvariable=self.status_var, wraplength=850).pack(anchor="w", pady=(8, 0))

    def _choose_source(self):
        selected = filedialog.askdirectory(title="选择素材文件夹")
        if selected:
            self.source_var.set(selected)

    def _choose_watermark(self):
        selected = filedialog.askopenfilename(
            title="选择水印图片（PNG 建议透明背景）",
            filetypes=[("图片", "*.png *.jpg *.jpeg"), ("所有文件", "*.*")],
        )
        if selected:
            self.watermark_var.set(selected)

    def _background(self, task):
        self.scan_button.config(state="disabled")
        self.generate_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.progress.start(12)
        threading.Thread(target=task, daemon=True).start()

    def _cancel_analysis(self):
        self._analysis_cancel.set()
        self.status_var.set("正在停止分析…")

    def _scan(self):
        source = self.source_var.get().strip()
        def task():
            try:
                if not source:
                    raise ValueError("请先选择一个素材文件夹")
                result = self.catalog.scan(source)
                if source not in self.context.settings.material_sources:
                    self.context.settings.material_sources.append(source)
                    save_settings(self.context.settings, self.context.paths)
                pending = len(self.catalog.pending_jobs(limit=10000))
                analysis_text = ""
                if pending:
                    self.messages.put(("progress", f"扫描完成，发现 {pending} 个素材需要真实分析…"))
                    job_stats = self.catalog.job_stats()
                    interrupted = job_stats.get("running", 0) + job_stats.get("retry", 0)
                    if interrupted:
                        self.messages.put(("progress", (
                            f"发现 {interrupted} 个上次中断的分析任务，本次将继续处理。", None,
                        )))
                    from treecut.analysis.pool import AnalysisPool
                    from treecut.analysis.parallel import suggest_workers
                    workers = suggest_workers(
                        self.context.settings.analysis_workers,
                        self.context.capabilities.ram_gb,
                    )
                    total_succeeded = total_retried = total_failed = 0
                    batch = workers * 3
                    pool = AnalysisPool(self.catalog.db_path, workers=workers)
                    try:
                        while not self._analysis_cancel.is_set():
                            remaining = len(self.catalog.pending_jobs(limit=1))
                            if remaining == 0:
                                break
                            run = pool.run_batch(
                                min(batch, remaining),
                                progress=lambda text, percent=None: self.messages.put(
                                    ("progress", (text, percent)),
                                ),
                            )
                            total_succeeded += run.succeeded
                            total_retried += run.retried
                            total_failed += run.failed
                            if run.claimed == 0:
                                break
                    finally:
                        pool.close()
                    if self._analysis_cancel.is_set():
                        analysis_text = (f"；已停止，分析成功 {total_succeeded}，待重试 {total_retried}，"
                                         f"失败 {total_failed}（下次扫描会继续）")
                    else:
                        analysis_text = (f"；分析成功 {total_succeeded}，待重试 {total_retried}，"
                                         f"失败 {total_failed}")
                limit_text = "；达到扫描上限，本次未执行丢失素材对账" if result.stopped_early else ""
                error_text = ""
                if result.error_details:
                    examples = "；".join(
                        f"{Path(item['path']).name}: {item['type']} {item['message']}"
                        for item in result.error_details[:3]
                    )
                    more = f"（另有 {result.errors - 3} 个）" if result.errors > 3 else ""
                    error_text = f"；错误示例：{examples}{more}"
                self.messages.put(("done", f"扫描完成：共 {result.total} 个，新增 {result.added}，变化 {result.changed}，错误 {result.errors}{error_text}{limit_text}{analysis_text}"))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
        self._background(task)

    def _generate(self):
        if not self._require_materials():
            return
        request = CreativeRequest(**self._current_request_dict())
        self._start_request(request)

    def _current_request_dict(self) -> dict:
        return asdict(CreativeRequest(
            self.selling.get("1.0", "end").strip(), self.narration.get("1.0", "end").strip(),
            self.duration_var.get(), 4, self.mp4_var.get(), self.draft_var.get(), False,
            output_preset=self.preset_labels[self.preset_display.get()],
            style=self.style_labels[self.style_display.get()],
            narration_speed=float(self.speed_var.get()),
            watermark_path=self.watermark_var.get().strip(),
        ))

    def _materials_ready(self) -> bool:
        return self.catalog.job_stats().get("success", 0) > 0

    def _require_materials(self) -> bool:
        if self._materials_ready():
            return True
        messagebox.showwarning(
            "还没有可用素材",
            "素材库还没有分析成功的素材。\n请先选择素材文件夹并点击“扫描素材”，"
            "等分析完成后再开始制作。",
        )
        return False

    def _maybe_show_welcome(self) -> None:
        from treecut.ui.welcome_dialog import WelcomeDialog, is_first_run, mark_welcomed
        if is_first_run(self.context.paths.data_root):
            mark_welcomed(self.context.paths.data_root)
            WelcomeDialog(self, self.context.paths.data_root,
                          self.context.paths.install_root / "docs")

    def _open_help(self) -> None:
        docs = self.context.paths.install_root / "docs"
        if docs.is_dir():
            import os
            os.startfile(str(docs))
        else:
            messagebox.showinfo("使用说明", "软件目录下没有 docs 文件夹。")

    def _open_log(self) -> None:
        from treecut.ui.log_dialog import LogDialog
        LogDialog(self, self.context.paths.logs / "treecut.log")

    def _open_remote_management(self) -> None:
        from treecut.ui.remote_manager_dialog import RemoteManagerDialog
        try:
            RemoteManagerDialog(self, self.context.paths)
        except Exception as error:
            messagebox.showerror("远程管理不可用", str(error), parent=self)

    def _maybe_start_remote_agent(self) -> None:
        def start() -> None:
            try:
                from treecut.remote.agent import RemoteAgent
                from treecut.remote.agent import (
                    launch_standalone_agent, standalone_agent_running,
                )
                from treecut.remote.config import load_config
                config_path = self.context.paths.data_root / "config" / "remote.json"
                config = load_config(config_path)
                if not config.valid() or not config.enabled:
                    return
                if getattr(config, "standalone", False):
                    if not standalone_agent_running(self.context.paths.install_root):
                        launch_standalone_agent(self.context.paths.install_root)
                    return
                log_path = self.context.paths.logs / "remote.log"

                def logger(message: str) -> None:
                    try:
                        with open(log_path, "a", encoding="utf-8") as stream:
                            stream.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}\n")
                    except OSError:
                        pass

                RemoteAgent(self.context.paths, config, logger=logger).run(stop=self._remote_stop)
            except Exception as error:
                self.context.logger.warning("远程助手启动失败: %s", error)

        threading.Thread(target=start, daemon=True).start()
        self._schedule_agent_guard()

    def _schedule_agent_guard(self) -> None:
        """每 60 秒确认独立后台代理存活；死了就自动拉起（仅 standalone 模式）。"""
        if self._agent_guard_scheduled:
            return
        self._agent_guard_scheduled = True
        self.after(60_000, self._agent_guard)

    def _agent_guard(self) -> None:
        try:
            from treecut.remote.agent import (
                launch_standalone_agent, standalone_agent_running,
            )
            from treecut.remote.config import load_config
            config = load_config(
                self.context.paths.data_root / "config" / "remote.json",
            )
            if (config.valid() and config.enabled
                    and getattr(config, "standalone", False)
                    and not standalone_agent_running(self.context.paths.install_root)):
                launch_standalone_agent(self.context.paths.install_root)
        except Exception:
            pass
        self.after(60_000, self._agent_guard)

    def _housekeeping_loop(self) -> None:
        from treecut.database import verify_integrity
        from treecut.maintenance import auto_backup
        while True:
            try:
                auto_backup(self.context.paths)
            except Exception as error:
                self.context.logger.warning("自动备份失败: %s", error)
            bad = [
                name for name in ("materials.db", "jobs.db", "desktop_jobs.db", "feedback.db")
                if verify_integrity(self.context.paths.databases / name) != "ok"
            ]
            if bad:
                self.context.logger.warning("数据库自检异常: %s", "、".join(bad))
                self.messages.put(("progress", f"数据库自检发现异常：{'、'.join(bad)}，建议尽快恢复备份。"))
            time.sleep(6 * 3600)

    def _generate_narration(self) -> None:
        try:
            from treecut.copywriter import build_narration
            text = build_narration(
                self.selling.get("1.0", "end").strip(), float(self.duration_var.get()),
            )
            self.narration.delete("1.0", "end")
            self.narration.insert("1.0", text)
        except Exception as error:
            messagebox.showerror("生成失败", str(error))

    def _open_settings(self) -> None:
        from treecut.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self, self.context.settings, self.context.paths)
        self.wait_window(dialog)
        self.duration_var.set(self.context.settings.default_duration)

    def _open_maintenance(self) -> None:
        from treecut.ui.maintenance_dialog import MaintenanceDialog
        MaintenanceDialog(self, self.context.paths)

    def _start_request(self, request: CreativeRequest, plan_override=None,
                       notify_result: bool = True):
        job_id = uuid.uuid4().hex
        threading.Thread(
            target=self._produce_one,
            args=(request, job_id, plan_override, notify_result),
            daemon=True,
        ).start()

    def _produce_one(self, request: CreativeRequest, job_id: str,
                     plan_override=None, notify_result: bool = True,
                     progress_prefix: str = "") -> None:
        job = {"id": job_id, "session_id": self.session_id, "state": "queued",
               "message": "已排队", "created_at": time.time(),
               "result": None, "error": None, "request": asdict(request)}
        self.job_journal.save(job, asdict(request))

        def progress(text: str, percent: float | None = None):
            text = progress_prefix + text if progress_prefix else text
            job.update(state="running", message=text)
            self.job_journal.save(job)
            self.messages.put(("progress", (text, percent)))

        def task():
            try:
                result = ProductionService(self.context).create(
                    request, progress, plan_override=plan_override)
                job.update(state="success", message="全部输出完成", result=result.to_dict())
                self.job_journal.save(job)
                if notify_result:
                    self.messages.put(("result", (result, job_id)))
            except Exception as exc:
                self.context.logger.exception("Desktop production job %s failed", job_id)
                error = f"{type(exc).__name__}: {exc}"
                job.update(state="failed", message="制作失败", error=error)
                self.job_journal.save(job)
                self.messages.put(("production_error", error))

    def _on_scheduled(self, request_dict: dict) -> None:
        try:
            request = CreativeRequest(**request_dict)
        except Exception as error:
            self.context.logger.warning("定时任务请求无效: %s", error)
            return
        self._start_request(request)

    def _batch_production(self) -> None:
        from treecut.batch import load_batch_file
        path = filedialog.askopenfilename(
            title="选择批量任务文件（每行：卖点|配音|时长）",
            filetypes=[("文本", "*.txt *.tsv"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            rows = load_batch_file(path)
        except Exception as error:
            messagebox.showerror("批量文件无效", str(error))
            return
        if not messagebox.askyesno("批量生产", f"将按顺序制作 {len(rows)} 个任务。是否开始？"):
            return
        if not self._require_materials():
            return
        self.scan_button.config(state="disabled")
        self.generate_button.config(state="disabled")
        self.progress.start(12)
        threading.Thread(target=self._batch_task, args=(rows,), daemon=True).start()

    def _batch_task(self, rows) -> None:
        try:
            for index, row in enumerate(rows, 1):
                self.messages.put(("progress", (
                    f"批量制作 {index}/{len(rows)}：{row.selling_points[:24]}", None,
                )))
                request = CreativeRequest(
                    row.selling_points, row.narration, row.target_duration, 4,
                    self.mp4_var.get(), self.draft_var.get(), False,
                    output_preset=self.preset_labels[self.preset_display.get()],
                    style=self.style_labels[self.style_display.get()],
                    watermark_path=self.watermark_var.get().strip(),
                )
                self._produce_one(
                    request, uuid.uuid4().hex, notify_result=False,
                    progress_prefix=f"批量 {index}/{len(rows)}：",
                )
        finally:
            self.messages.put(("done", f"批量制作完成：共 {len(rows)} 个任务"))

    def _open_schedule(self) -> None:
        from treecut.ui.schedule_dialog import ScheduleDialog
        ScheduleDialog(self, self.schedule_store, request_factory=self._current_request_dict)

    def _open_dashboard(self) -> None:
        from treecut.ui.dashboard_dialog import DashboardDialog
        DashboardDialog(self, self.context)

    def _drain_messages(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "progress":
                    text, percent = value if isinstance(value, tuple) else (value, None)
                    self.status_var.set(str(text))
                    if percent is not None:
                        if str(self.progress.cget("mode")) != "determinate":
                            self.progress.config(mode="determinate", maximum=100)
                        self.progress["value"] = percent
                elif kind == "done":
                    self._finish(); self.status_var.set(str(value)); messagebox.showinfo("树剪", str(value))
                elif kind == "error":
                    self._finish(); self.status_var.set(str(value)); messagebox.showerror("树剪出现问题", str(value))
                elif kind == "production_error":
                    self._finish(); self.status_var.set(str(value))
                    messagebox.showerror("制作失败", f"{value}\n\n任务已保存，可在“任务记录 / 重试”中重试。")
                elif kind == "result":
                    result, _job_id = value
                    self._finish(); self.status_var.set(f"制作完成：{result.project_dir}")
                    self._show_result(result)
        except queue.Empty:
            pass
        self.after(150, self._drain_messages)

    def _finish(self):
        self.progress.stop()
        self.progress.config(mode="indeterminate", value=0)
        self.scan_button.config(state="normal")
        self.generate_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self._analysis_cancel.clear()

    def _show_result(self, result):
        from treecut.ui.result_dialog import ResultDialog
        ResultDialog(
            self, result,
            feedback=self.feedback,
            get_query=lambda: self.selling.get("1.0", "end").strip(),
            on_edit_timeline=self._edit_timeline,
            auto_preview=self.context.settings.auto_preview,
        )

    def _show_jobs(self):
        window = tk.Toplevel(self)
        window.title("任务记录与重试")
        window.geometry("880x430")
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="任务记录", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="选中任务可预览成片（仅限已导出 MP4 的任务）；失败或被中断的任务可以重试。",
                  wraplength=840).pack(anchor="w", pady=(2, 8))
        tree = ttk.Treeview(frame, columns=("state", "message", "created", "id"), show="headings")
        for name, title, width in (("state", "状态", 80), ("message", "说明", 330),
                                   ("created", "时间", 150), ("id", "任务编号", 270)):
            tree.heading(name, text=title); tree.column(name, width=width, stretch=name == "message")
        tree.pack(fill="both", expand=True)
        records = self.job_journal.recent(100)
        for job in records:
            created = datetime.fromtimestamp(job["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            tree.insert("", "end", iid=job["id"], values=(job["state"], job["message"], created, job["id"]))

        def retry_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("请选择任务", "请先点击一条任务记录。", parent=window)
                return
            job = self.job_journal.get(selected[0])
            if not job or job["state"] != "failed":
                messagebox.showwarning("不能重试", "只有失败或被中断的任务可以重试。", parent=window)
                return
            try:
                request = CreativeRequest(**job["request"])
            except Exception as error:
                messagebox.showerror("原请求损坏", str(error), parent=window)
                return
            window.destroy()
            self._start_request(request)

        def preview_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("请选择任务", "请先点击一条任务记录。", parent=window)
                return
            job = self.job_journal.get(selected[0])
            result = (job or {}).get("result") or {}
            video = result.get("final_mp4") or result.get("preview_mp4")
            if not video or not Path(video).is_file():
                messagebox.showinfo(
                    "没有成片", "该任务没有可预览的成片（未导出 MP4，或文件已被移动/清理）。",
                    parent=window,
                )
                return
            from treecut.ui.player import VideoPlayerWindow
            VideoPlayerWindow(window, video)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="预览选中成片", command=preview_selected).pack(side="left")
        ttk.Button(buttons, text="重试选中的失败任务", command=retry_selected).pack(side="left", padx=(8, 0))

    def _edit_timeline(self, result) -> None:
        try:
            import json as json_module
            from pathlib import Path as PathType
            from treecut.workflow.planning import EditPlan, EditSegment
            report = json_module.loads(PathType(result.report_json).read_text(encoding="utf-8"))
            segments = tuple(
                EditSegment(
                    int(item["order"]), int(item["media_id"]), item["path"],
                    item["category"], float(item["source_start"]),
                    float(item["source_end"]), float(item["timeline_start"]),
                    float(item["timeline_end"]), float(item["match_score"]),
                    tuple(item["matched_terms"]), item.get("content_fingerprint") or "",
                )
                for item in report["plan"]["segments"]
            )
            plan = EditPlan(float(report["plan"]["requested_duration"]),
                            float(report["plan"]["planned_duration"]),
                            bool(report["plan"]["complete"]),
                            tuple(report["plan"]["warnings"]), segments)
        except Exception as error:
            messagebox.showerror("无法读取剪辑计划", str(error))
            return
        from treecut.ui.timeline_dialog import TimelineDialog
        TimelineDialog(self, plan, on_apply=self._rerender_with_plan)

    def _rerender_with_plan(self, plan) -> None:
        request = CreativeRequest(
            self.selling.get("1.0", "end").strip(), self.narration.get("1.0", "end").strip(),
            self.duration_var.get(), 4, self.mp4_var.get(), self.draft_var.get(), False,
            output_preset=self.preset_labels[self.preset_display.get()],
            style=self.style_labels[self.style_display.get()],
            watermark_path=self.watermark_var.get().strip(),
        )
        self._start_request(request, plan_override=plan)

    def _check_updates(self) -> None:
        from treecut.ui.update_check_dialog import UpdateCheckDialog
        UpdateCheckDialog(self, self.context.paths)

    def _apply_remote_policy(self) -> None:
        """Enforce remote-control policy (disable / blacklist / force update)."""
        policy = {}
        try:
            policy = json.loads(
                (self.context.paths.data_root / "config" / "remote_policy.json")
                .read_text(encoding="utf-8")
            )
        except Exception:
            pass
        blocked: list[str] = []
        if policy.get("blacklisted"):
            blocked.append("该电脑已被管理端拉黑")
        elif policy.get("disabled"):
            blocked.append("该电脑已被管理端禁用")
        if policy.get("min_version_ok") is False:
            blocked.append("软件版本低于管理端要求，正在等待自动更新")
        if policy.get("force_update_pending"):
            blocked.append("检测到强制更新，正在安装（安装完成后请重启软件）")
        if policy.get("update_state") == "uninstall_scheduled":
            blocked.append("卸载已安排，本窗口即将关闭")
            self.after(500, self.destroy)
        remote_job = policy.get("remote_job_state")
        if remote_job == "running":
            message = policy.get("remote_job_message") or "远程制作中"
            percent = policy.get("remote_job_percent")
            suffix = f"（{percent:.0f}%）" if isinstance(percent, (int, float)) else ""
            blocked.append(f"远程制作中：{message}{suffix}")
        elif remote_job == "success":
            self.status_var.set("远程制作完成，可在「任务记录 / 重试」查看成片")
        elif remote_job == "failed":
            self.status_var.set(f"远程制作失败：{policy.get('remote_job_message') or '请查看任务记录'}")
        if blocked:
            self.generate_button.config(state="disabled")
            self.status_var.set("；".join(blocked))
        elif getattr(self, "_policy_blocked", False):
            self.generate_button.config(state="normal")
        self._policy_blocked = bool(blocked)
        self.after(5000, self._apply_remote_policy)

    def _show_library(self):
        from treecut.ui.library_dialog import LibraryDialog
        LibraryDialog(
            self,
            catalog=self.catalog,
            paths=self.context.paths,
            run_background=self._background,
            on_message=lambda kind, value: self.messages.put((kind, value)),
        )


def main():
    from treecut.platform.dpi import enable_dpi_awareness
    enable_dpi_awareness()
    paths = RuntimePaths.discover()
    paths.apply_environment()
    from treecut.platform.crash import install_crash_handler
    install_crash_handler(paths.logs)
    with SingleInstanceLock(paths.data_root / "locks" / "desktop.lock"):
        TreeCutDesktop().mainloop()


if __name__ == "__main__":
    main()
