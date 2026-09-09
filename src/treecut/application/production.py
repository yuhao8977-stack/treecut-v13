"""The only formal orchestration path used by desktop, CLI, and future API."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import traceback

from treecut.bootstrap import AppContext, bootstrap
from treecut.learning import FeedbackStore
from treecut.output import (
    build_jianying_draft, burn_subtitles, create_narrated_video,
    render_video_plan,
)
from treecut.output.mix import build_mix, last_voice_time, remux_video_audio
from treecut.quality.publish_gates import (
    LAST_SUBTITLE_INCOMPLETE, check_audible_end, check_script_completeness,
)
from treecut.output.cover import make_cover
from treecut.output.filters import resolve_style
from treecut.quality import (
    combine_reports, inspect_burned_subtitles, inspect_final_video,
    inspect_edit_plan, inspect_jianying_draft, inspect_playback_quality,
)
from treecut.workflow import build_edit_plan, load_candidates, match_materials
from treecut.models.semantic_matching import semantic_scores
from treecut.output.presets import resolve_preset
from treecut.platform.memory import available_ram_gb
from treecut.platform.progress import ProgressCallback, no_progress
from treecut.extensions import run_hooks


@dataclass(frozen=True)
class CreativeRequest:
    selling_points: str
    narration: str
    target_duration: float = 30
    clip_seconds: float = 4
    output_mp4: bool = True
    output_jianying: bool = True
    include_test_materials: bool = False
    bgm_path: str = ""
    output_preset: str = "vertical"
    narration_speed: float = 1.0
    style: str = "natural"
    watermark_path: str = ""
    # B1 narration duration contract
    duration_strategy: str = "strict_reject"
    intentional_outro: bool = False

    def validate(self) -> None:
        if not self.selling_points.strip():
            raise ValueError("请填写产品卖点或画面需求")
        if not self.narration.strip():
            raise ValueError("请填写配音文案")
        if not 5 <= self.target_duration <= 300:
            raise ValueError("目标时长必须在 5–300 秒之间")
        if not 1 <= self.clip_seconds <= 15:
            raise ValueError("单镜头时长必须在 1–15 秒之间")
        if not 0.5 <= self.narration_speed <= 2.0:
            raise ValueError("配音语速必须在 0.5–2.0 之间")
        from treecut.quality.duration_contract import STRATEGIES
        if self.duration_strategy not in STRATEGIES:
            raise ValueError(f"未知时长策略: {self.duration_strategy}（可选 {STRATEGIES}）")
        if not (self.output_mp4 or self.output_jianying):
            raise ValueError("至少选择 MP4 或剪映草稿一种输出")
        resolve_preset(self.output_preset)
        resolve_style(self.style)
        validate_test_material_access(self.include_test_materials)


def validate_test_material_access(include_test_materials: bool,
                                  development_mode: bool | None = None) -> None:
    """Keep test sources out of formal jobs unless development mode is explicit."""
    if development_mode is None:
        development_mode = os.environ.get("TREECUT_DEVELOPMENT_MODE") == "1"
    if include_test_materials and not development_mode:
        raise PermissionError("正式模式禁止使用测试素材；只有显式开发模式可以开启")


def select_render_profile(request: CreativeRequest) -> str:
    """An MP4 request must start from the real final-resolution picture master."""
    return "final" if request.output_mp4 else "preview"


@dataclass(frozen=True)
class ProductionResult:
    project_dir: str
    planned_duration: float
    match_count: int
    segment_count: int
    preview_mp4: str | None
    final_mp4: str | None
    jianying_draft: str | None
    report_json: str
    cover: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


QUALITY_ADVICE = {
    "video_exists": "检查输出盘是否在线、空间是否充足，并重新渲染。",
    "video_bytes": "成片过小，检查 FFmpeg 日志和源视频是否可解码。",
    "video_probe": "FFprobe 无法读取成片，建议重新渲染并检查磁盘写入。",
    "video_duration": "画面或配音时长不一致，重新生成镜头计划。",
    "video_dimensions": "最终成片画幅不是预设尺寸（竖屏 1080×1920 / 方屏 1080×1080 / 横屏 1920×1080），请检查渲染预设。",
    "video_audio": "成片没有音轨，检查本地配音和音频封装。",
    "playback_decode": "成片存在解码错误，检查源素材并重新渲染。",
    "burned_subtitle_pixels": "字幕没有可靠烧录到画面，请检查字体和字幕文件。",
    "draft_source_files": "剪映草稿引用的素材已离线，请重新连接硬盘后重试。",
    "draft_segment_bounds": "剪映片段越界，重新生成时间线。",
    "NARRATION_TOO_SHORT": "旁白过短：请扩写配音文案或缩短目标时长；禁止静默补空镜（B1 时长契约）。",
    "NARRATION_TOO_LONG": "旁白过长：请精简配音文案或增加目标时长（B1 时长契约）。",
    "VOICE_COVERAGE_LOW": "旁白覆盖率过低（需≥95%）：文案与目标时长不匹配（B1 时长契约）。",
    "VOICE_TAIL_TOO_LONG": "结尾无旁白超过 0.8 秒且未声明片尾（B1 时长契约）。",
    "BGM_ONLY_AUDIO": "检测不到旁白音轨，背景音乐不得计为旁白（B1 时长契约）。",
    "DURATION_CONTRACT_NOT_RUN": "时长契约未执行，禁止放行（B1）。",
    "SCRIPT_TRUNCATED": "脚本被中途截断（非完整句子结尾）：请按完整句子/Beat 增删，禁止字符切片（B1R1）。",
    "SCRIPT_NO_TERMINAL_PUNCTUATION": "脚本无结束标点：必须以完整句子与结束标点结尾（B1R1）。",
    "AUDIO_GAIN_PUMPING": "音频短时响度跳变或人声音量不稳定：仅允许 BGM 淡入淡出/ducking，人声增益恒定（B1R1）。",
    "AUDIO_TRUE_PEAK_EXCEEDED": "混音真峰值超限：需 true-peak limiter 兜底（B1R1）。",
    "AUDIBLE_END_TOO_CLOSE": "最后发声距画面结束不足 0.25s 或超过 0.8s（B1R1）。",
    "LAST_SUBTITLE_INCOMPLETE": "最后一条字幕未以完整句子结束（B1R1）。",
}


def _write_project_status(project: Path, state: str, *, error: str = "",
                          details: str = "", advice: list[str] | None = None) -> Path:
    payload = {
        "state": state, "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": error, "details": details, "advice": advice or [],
    }
    path = project / "STATUS.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path


class ProductionService:
    def __init__(self, context: AppContext | None = None):
        self.context = context or bootstrap()

    def create(self, request: CreativeRequest,
               progress: ProgressCallback = no_progress,
               plan_override=None) -> ProductionResult:
        request.validate()
        if available_ram_gb() < 4.0:
            raise RuntimeError(
                f"可用内存不足（{available_ram_gb():.1f} GB < 4 GB），"
                "请关闭其他程序后重试。"
            )
        free_bytes = shutil.disk_usage(self.context.paths.output).free
        if free_bytes < 2 * 1024 * 1024 * 1024:
            raise RuntimeError(
                f"输出盘剩余空间不足（{free_bytes / 2**30:.2f} GB），制作前至少需要 2 GB。"
                "请清理 runtime_data\\output 或更换素材盘后重试。"
            )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        project = self.context.paths.output / "projects" / timestamp
        project.mkdir(parents=True, exist_ok=False)
        _write_project_status(project, "running")
        try:
            result = self._create(request, progress, project, plan_override)
            _write_project_status(project, "success")
            run_hooks("post_production", result.to_dict())
            return result
        except Exception as error:
            text = str(error)
            codes = [code for code in QUALITY_ADVICE if code in text]
            advice = [QUALITY_ADVICE[code] for code in codes]
            if not advice:
                advice = ["查看本项目 STATUS.json 的 details 和 runtime_data\\logs 后重试。"]
            _write_project_status(
                project, "failed", error=f"{type(error).__name__}: {error}",
                details=traceback.format_exc(), advice=advice,
            )
            raise

    def _create(self, request: CreativeRequest, progress, project: Path,
                plan_override=None) -> ProductionResult:
        from treecut.output.narration import _apply_narration_speed, synthesize, wav_duration
        from treecut.quality.duration_contract import check_duration_contract, resolve_plan_duration
        paths = self.context.paths
        ffmpeg = paths.install_root / "tools" / "win32" / "ffmpeg.exe"
        ffprobe = paths.install_root / "tools" / "win32" / "ffprobe.exe"
        # ---- B1R1: script must be COMPLETE before any TTS (no char-slicing) ----
        script_gate = check_script_completeness(request.narration)
        if not script_gate.passed:
            raise RuntimeError(
                f"脚本完整性失败 [{script_gate.code}]: {script_gate.reason}")
        # ---- B1: REAL narration first, single synthesis; duration is the only
        # authority. Never silently pad empty footage; never fake with BGM. ----
        work = project / "work"
        work.mkdir(parents=True, exist_ok=True)
        narration_wav = work / "narration.wav"
        progress("正在合成真实旁白并测量时长…", 5)
        synthesize(request.narration, narration_wav, paths.models / "LocalTTS")
        if abs(request.narration_speed - 1.0) > 1e-6:
            stretched = work / "narration_speed.wav"
            _apply_narration_speed(narration_wav, stretched, request.narration_speed, ffmpeg)
            stretched.replace(narration_wav)
        narration_duration = wav_duration(narration_wav)
        if plan_override is not None:
            plan_duration = float(getattr(plan_override, "planned_duration", 0.0)
                                  or request.target_duration)
        else:
            plan_duration = resolve_plan_duration(
                request.duration_strategy, request.target_duration, narration_duration)
        contract = check_duration_contract(
            strategy=request.duration_strategy,
            target_duration=request.target_duration,
            narration_duration=narration_duration,
            video_duration=plan_duration,
            intentional_outro=request.intentional_outro)
        if not contract.passed:
            raise RuntimeError(f"时长契约失败 [{contract.code}]: {contract.reason}")
        progress("旁白时长契约通过", 8)
        if plan_override is not None:
            progress("使用用户调整后的剪辑计划…", 10)
            plan = plan_override
            matches = []
            bge_scores = clip_scores = {}
            semantic_errors = []
        else:
            progress("正在匹配相关素材…", 10)
            candidates = load_candidates(
                paths.databases / "materials.db", request.include_test_materials,
            )
            feedback = FeedbackStore(paths.databases / "feedback.db").adjustments(
                request.selling_points,
            )
            progress("正在用本地中文语义模型复核素材相关性…", 20)
            bge_scores, clip_scores, semantic_errors = semantic_scores(
                request.selling_points, candidates, paths.models,
                use_bge=self.context.capabilities.bge_m3_ready,
                use_clip=self.context.capabilities.chinese_clip_ready,
                ffmpeg=ffmpeg, ffprobe=ffprobe,
            )
            matches = match_materials(
                request.selling_points, candidates, limit=40,
                feedback_adjustments=feedback,
                bge_scores=bge_scores, clip_scores=clip_scores,
                domain_terms=self.context.domain_vocabulary,
            )
            plan = build_edit_plan(matches, plan_duration, request.clip_seconds)
            if not plan.complete:
                raise RuntimeError("；".join(plan.warnings))
        plan_quality = inspect_edit_plan(plan)
        if not plan_quality.passed:
            failed = [item.code for item in plan_quality.checks if item.critical and not item.passed]
            raise RuntimeError("剪辑计划质量检查失败：" + "、".join(failed))
        bgm = Path(request.bgm_path) if request.bgm_path else paths.install_root / "assets" / "bgm" / "mixkit_ambient_31f31ead.mp3"
        render_profile = select_render_profile(request)
        preset = resolve_preset(request.output_preset)
        preview = project / ("01_高清画面底片.mp4" if render_profile == "final" else "01_画面预览.mp4")
        progress("正在渲染高清画面底片…" if render_profile == "final" else "正在渲染画面预览…", 35)
        watermark = Path(request.watermark_path) if request.watermark_path else None
        render_video_plan(
            plan, preview, ffmpeg, ffprobe, render_profile, preset=preset,
            style=request.style, watermark_path=watermark,
        )
        narrated = project / "02_配音字幕预览.mp4"
        progress("正在生成离线配音和字幕…", 55)
        create_narrated_video(
            preview, request.narration, narrated, work, paths.models / "LocalTTS",
            ffmpeg, ffprobe, speed=request.narration_speed,
            prebuilt_audio=narration_wav,
        )
        mixed = project / "03_配音音乐预览.mp4"
        progress("正在按三轨契约混音（voice 恒定 / 仅 BGM 淡入淡出与 ducking / limiter）…", 70)
        from treecut.media import probe_media
        mix_artifacts = build_mix(
            work / "narration.wav", bgm, work, ffmpeg,
            probe_media(Path(narrated), ffprobe).duration,
        )
        mix_ev = mix_artifacts["evidence"]
        if not mix_ev["pump_ok"]:
            raise RuntimeError(
                f"音频混音失败 [AUDIO_GAIN_PUMPING]: 相邻窗口响度跳变 "
                f"{mix_ev['max_adjacent_window_delta_db']}dB ≥ 8dB")
        if not mix_ev["peak_ok"]:
            raise RuntimeError(
                f"音频混音失败 [AUDIO_TRUE_PEAK_EXCEEDED]: "
                f"峰值 {mix_ev['final'].get('max_volume_db')}dB 超过限幅余量")
        remux_video_audio(
            Path(narrated), mix_artifacts["final_mix"], Path(mixed), ffmpeg,
            probe_media(Path(narrated), ffprobe).duration,
        )

        final_mp4 = None
        if request.output_mp4:
            progress("正在烧录中文字幕…", 80)
            final = project / "TreeCut_成片.mp4"
            burn_subtitles(mixed, work / "narration.srt", paths.install_root / "assets" / "fonts",
                           final, ffmpeg, ffprobe)
            final_mp4 = str(final)
        cover = None
        if final_mp4:
            cover = str(make_cover(
                Path(final_mp4), request.narration.strip(),
                paths.install_root / "assets" / "fonts", ffmpeg, project,
            ))

        draft_path = None
        if request.output_jianying:
            progress("正在生成剪映草稿…", 88)
            draft = project / "TreeCut_剪映草稿"
            build_jianying_draft(plan, draft, work / "narration.wav", bgm,
                                 work / "narration.srt", ffmpeg,
                                 width=preset.width, height=preset.height, fps=preset.fps)
            draft_path = str(draft)

        progress("正在回读并检查最终输出…", 95)
        quality_reports = [plan_quality]
        final_video_duration = None
        if final_mp4:
            quality_reports.append(inspect_final_video(
                Path(final_mp4), ffprobe, plan.planned_duration,
                expected_width=preset.width, expected_height=preset.height,
            ))
            quality_reports.append(inspect_playback_quality(Path(final_mp4), ffmpeg, plan.planned_duration))
            quality_reports.append(inspect_burned_subtitles(
                mixed, Path(final_mp4), work / "narration.srt",
            ))
            from treecut.media import probe_media
            final_video_duration = float(probe_media(Path(final_mp4), ffprobe).duration)
        if draft_path:
            quality_reports.append(inspect_jianying_draft(Path(draft_path), plan.planned_duration))
        # B1: re-verify the duration contract against the REAL final video length
        contract_final = check_duration_contract(
            strategy=request.duration_strategy,
            target_duration=request.target_duration,
            narration_duration=narration_duration,
            video_duration=final_video_duration or plan_duration,
            intentional_outro=request.intentional_outro)
        if not contract_final.passed:
            raise RuntimeError(
                f"最终成片时长契约失败 [{contract_final.code}]: {contract_final.reason}")
        # B1R1: audible-end alignment (REAL last voice, not container length)
        last_voice = last_voice_time(work / "narration.wav")
        end_gate = check_audible_end(
            last_voice, final_video_duration or plan_duration, narration_duration,
            request.intentional_outro)
        if not end_gate.passed:
            raise RuntimeError(
                f"结尾对齐失败 [{end_gate.code}]: {end_gate.reason}")
        # B1R1: last subtitle must be a COMPLETE sentence aligned with narration end
        srt_lines = (work / "narration.srt").read_text(
            encoding="utf-8-sig").strip().splitlines()
        last_cue_text = srt_lines[-1] if srt_lines else ""
        if last_cue_text and last_cue_text[-1] not in "。！？!?":
            raise RuntimeError(
                f"字幕完整性失败 [{LAST_SUBTITLE_INCOMPLETE}]: 最后一条字幕未以完整句子结束")
        quality = combine_reports(*quality_reports)
        script_sha = hashlib.sha256(request.narration.encode("utf-8")).hexdigest()
        technical_pass = bool(quality.passed)
        duration_pass = bool(contract_final.passed)
        script_pass = bool(script_gate.passed)
        audio_pass = bool(mix_ev["pump_ok"] and mix_ev["peak_ok"]
                          and mix_ev.get("voice_gain_constant", True))
        audible_pass = bool(end_gate.passed)

        report_path = project / "production_report.json"
        report = {
            "request": asdict(request), "matches": [item.to_dict() for item in matches],
            "plan": plan.to_dict(), "preview_mp4": str(preview),
            "render_profile": render_profile,
            "final_mp4": final_mp4, "jianying_draft": draft_path, "cover": cover,
            "quality": quality.to_dict(),
            "semantic_models": {"bge_scored": len(bge_scores),
                                "clip_scored": len(clip_scores),
                                "errors": semantic_errors},
            "duration_contract": contract_final.fields
            | {"code": contract_final.code, "strategy": request.duration_strategy},
            "script": {"text": request.narration, "sha256": script_sha,
                       "char_count": len(request.narration),
                       "last_sentence": script_gate.fields.get("last_sentence"),
                       "last_char": script_gate.fields.get("last_char")},
            "audio_mix": mix_ev,
            "audible_end": end_gate.fields,
            "statuses": {
                "TECHNICAL_RENDER_PASS": technical_pass,
                "DURATION_CONTRACT_PASS": duration_pass,
                "SCRIPT_COMPLETENESS_PASS": script_pass,
                "AUDIO_MIX_PASS": audio_pass,
                "AUDIBLE_END_ALIGNMENT_PASS": audible_pass,
                "B1_ACCEPTANCE_PASS": bool(technical_pass and duration_pass
                                           and script_pass and audio_pass
                                           and audible_pass),
                # B2+ scope only; later phases must turn these on
                "SUBTITLE_HYGIENE_PASS": False,
                "SEMANTIC_MATCH_PASS": False,
                "VISUAL_GRAMMAR_PASS": False,
                "CONTENT_QUALITY_PASS": False,
                "HUMAN_ACCEPTANCE_PASS": False,
                "PUBLISH_READY": False,
                "note": "B1R1 scope: script completeness + three-track audio mix + "
                        "audible-end alignment. Subtitle hygiene (B2 occlusion "
                        "plates: bottom-subtitle cover then redraw; top/mid multi-"
                        "text reject) / semantic match / visual grammar / human "
                        "acceptance are NOT yet passed."},
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not quality.passed:
            failed = [item.code for item in quality.checks if item.critical and not item.passed]
            raise RuntimeError("最终输出质量检查失败：" + "、".join(failed))
        progress("全部输出完成", 100)
        return ProductionResult(str(project), plan.planned_duration, len(matches), len(plan.segments),
                                str(preview), final_mp4, draft_path, str(report_path), cover)
