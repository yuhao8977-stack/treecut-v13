"""GPU acceptance checks for NVIDIA target machines (Qwen3-VL + NVENC)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from treecut.bootstrap import bootstrap


def _nvenc_supported(ffmpeg: Path) -> bool:
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, check=False, timeout=60,
    )
    return b"h264_nvenc" in result.stdout + result.stderr


def _nvenc_render_ok(ffmpeg: Path, output: Path) -> tuple[bool, str]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1:r=30",
        "-c:v", "h264_nvenc", "-preset", "p4", "-pix_fmt", "yuv420p", str(output),
    ]
    result = subprocess.run(command, capture_output=True, check=False, timeout=120)
    ok = result.returncode == 0 and output.is_file() and output.stat().st_size > 1000
    detail = result.stderr.decode("utf-8", errors="replace").strip() or "ok"
    return ok, detail


def _qwen_caption_ok(models: Path, sample_frame: Path | None) -> tuple[bool, str]:
    if sample_frame is None or not sample_frame.is_file():
        return False, "no sample frame available; analysis frames are generated on first scan"
    try:
        from treecut.models.vision_qwen import QwenVision
        vision = QwenVision(models / "Qwen3-VL-4B-Instruct-FP8")
        captions = vision.caption_many([sample_frame])
        return bool(captions and captions[0].strip()), "ok"
    except Exception as error:
        return False, f"{type(error).__name__}: {error}"


def run_acceptance() -> dict:
    context = bootstrap()
    paths = context.paths
    capabilities = context.capabilities
    report: dict = {
        "passed": False,
        "cuda": capabilities.cuda_available,
        "vram_gb": capabilities.cuda_vram_gb,
        "qwen_ready": capabilities.qwen_vl_ready,
        "nvenc": False,
        "nvenc_render": False,
        "qwen_caption": False,
        "details": {},
    }
    if not capabilities.cuda_available:
        report["details"]["reason"] = "no_cuda"
        report["details"]["note"] = "skipped; no CUDA on this machine"
        report["passed"] = False
        return report

    ffmpeg = paths.install_root / "tools" / "win32" / "ffmpeg.exe"
    report["nvenc"] = _nvenc_supported(ffmpeg)
    report["details"]["nvenc_supported"] = report["nvenc"]

    temp_dir = paths.temp / "gpu_acceptance"
    temp_dir.mkdir(parents=True, exist_ok=True)
    test_output = temp_dir / "nvenc_probe.mp4"
    report["nvenc_render"], report["details"]["nvenc_render_error"] = _nvenc_render_ok(
        ffmpeg, test_output,
    )

    frames = sorted((paths.cache / "analysis_frames").rglob("frame_*.jpg")) if (
        paths.cache / "analysis_frames"
    ).is_dir() else []
    sample = frames[0] if frames else None
    report["qwen_caption"], report["details"]["qwen_caption_error"] = _qwen_caption_ok(
        paths.models, sample,
    )

    report["passed"] = report["nvenc_render"] and report["qwen_caption"]
    output = paths.logs / "gpu_acceptance.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_acceptance()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") or report.get("details", {}).get("reason") == "no_cuda" else 1


if __name__ == "__main__":
    raise SystemExit(main())
