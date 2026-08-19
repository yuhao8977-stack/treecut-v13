"""Beginner-facing portable installation checks."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import importlib
import json
from pathlib import Path
import sys
import tempfile

from treecut.bootstrap import bootstrap


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    passed: bool
    detail: str
    critical: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def run_checks(deep: bool = False) -> dict:
    context = bootstrap()
    paths = context.paths
    checks: list[DiagnosticCheck] = []

    def add(name: str, passed: bool, detail: object, critical: bool = True):
        checks.append(DiagnosticCheck(name, bool(passed), str(detail), critical))

    add("安装盘不是 C 盘", paths.install_root.drive.upper() != "C:", paths.install_root)
    add("Python 位于软件目录", Path(sys.executable).resolve().is_relative_to(paths.install_root), sys.executable)
    add("Python 基础路径独立", Path(sys.base_prefix).resolve() == paths.install_root / "runtime", sys.base_prefix)
    for label, path in {
        "FFmpeg": paths.install_root / "tools/win32/ffmpeg.exe",
        "FFprobe": paths.install_root / "tools/win32/ffprobe.exe",
        "Florence": paths.models / "Florence-2-base/model.safetensors",
        "Whisper": paths.models / "Whisper-small/model.bin",
        "Chinese-CLIP": paths.models / "Chinese-CLIP-ViT-B-16/pytorch_model.bin",
        "BGE-M3": paths.models / "BGE-M3/pytorch_model.bin",
        "离线配音": paths.models / "LocalTTS/vits-melo-tts-zh_en/model.onnx",
    }.items():
        add(f"{label} 文件", path.is_file(), path)
    for label, path in vars(paths).items():
        if label == "install_root":
            continue
        add(f"{label} 与安装盘一致", Path(path).drive.upper() == paths.install_root.drive.upper(), path)
    try:
        with tempfile.NamedTemporaryFile(dir=paths.temp, prefix="treecut_write_", delete=True) as stream:
            stream.write(b"TreeCut")
        add("运行目录可写", True, paths.temp)
    except Exception as error:
        add("运行目录可写", False, error)
    if deep:
        for module in ("torch", "transformers", "cv2", "sherpa_onnx", "fastapi", "faster_whisper"):
            try:
                imported = importlib.import_module(module)
                add(f"导入 {module}", True, getattr(imported, "__version__", "ok"))
            except Exception as error:
                add(f"导入 {module}", False, f"{type(error).__name__}: {error}")
    passed = all(check.passed for check in checks if check.critical)
    return {"passed": passed, "profile": context.model_plan.to_dict(),
            "checks": [check.to_dict() for check in checks]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true")
    args = parser.parse_args()
    report = run_checks(args.deep)
    output = bootstrap().paths.logs / "installation_diagnostic.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已保存：{output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
