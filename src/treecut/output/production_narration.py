"""Production Narration Adapter — real narration text → validated WAV → non-empty SRT.

V0.8.4：把真实 TTS/SRT 接入 produce() 的 Narration/Subtitle 阶段。
后端选择：sherpa-onnx（若引擎+模型可用）→ Windows SAPI（离线 zh-CN）→ 失败即报错。
禁止静音占位冒充成功；mock 仅限显式 MOCK 模式。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.output.narration import build_srt, wav_duration

FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"


@dataclass
class NarrationArtifacts:
    wav: Path | None = None
    srt: Path | None = None
    audio_duration: float = 0.0
    text_chars: int = 0
    chars_per_second: float = 0.0
    subtitle_count: int = 0
    text_coverage: float = 0.0
    backend: str = ""
    voice: str = ""
    text_hash: str = ""
    audio_sha256: str = ""
    generated_at: str = ""
    status: str = "PENDING"
    error: str = ""

    def to_dict(self) -> dict:
        return {k: (str(v) if k in ("wav", "srt") else v) for k, v in self.__dict__.items()}


def _backend_sherpa_available(model_root: Path) -> bool:
    try:
        from treecut.models.tts_local import discover_tts_files  # noqa: F401
        discover_tts_files(model_root)
        import importlib.util
        return importlib.util.find_spec("sherpa_onnx") is not None
    except Exception:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_audio(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, timeout=60)
    data = json.loads(out.stdout.decode("utf-8", errors="replace"))
    fmt = data.get("format", {})
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {"duration": float(fmt.get("duration") or 0),
            "codec": (stream or {}).get("codec_name"),
            "sample_rate": (stream or {}).get("sample_rate"),
            "channels": (stream or {}).get("channels")}


def _norm(s: str) -> str:
    import re
    return re.sub(r"[\s，。、；：!?！？,.…·\"'“”‘’—\-]", "", s or "")


def _text_coverage(text: str, srt_text: str) -> float:
    t = _norm(text)
    if not t:
        return 0.0
    s = _norm(srt_text)
    # 逐字覆盖（允许 SRT 分段拼接的微小差异）
    hit = sum(1 for ch in t if ch in s)
    return round(hit / len(t), 4)


class ProductionNarrationAdapter:
    """narration text → real TTS wav → non-empty SRT（+版本元数据）。"""

    def __init__(self, model_root: Path | None = None, voice: str = "Microsoft Huihui Desktop"):
        self.model_root = model_root
        self.voice = voice

    def synthesize_wav(self, text: str, wav_path: Path) -> tuple[str, str]:
        """返回 (backend, voice)。优先 sherpa-onnx；否则 Windows SAPI。"""
        if self.model_root and _backend_sherpa_available(self.model_root):
            try:
                from treecut.models.tts_local import synthesize as sherpa_synth
                sherpa_synth(text, wav_path, self.model_root)
                return "sherpa-onnx-vits", "local-vits"
            except Exception:
                pass  # 降级 SAPI
        from treecut.models.tts_sapi import synthesize as sapi_synth
        sapi_synth(text, wav_path)
        return "windows-sapi", self.voice

    def generate(self, text: str, out_dir: Path, mock: bool = False) -> NarrationArtifacts:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        art = NarrationArtifacts(text_chars=len(text or ""),
                                 text_hash=hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16],
                                 generated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        if not (text or "").strip():
            art.status = "SUBTITLE_GENERATION_FAILED"
            art.error = "narration text empty"
            return art
        wav = out_dir / "narration.wav"
        srt = out_dir / "narration.srt"
        if mock:
            # 显式 MOCK：仅测试用，不冒充 production
            import subprocess as _sp
            _sp.run(["powershell", "-NoProfile", "-Command",
                     "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                     f"$s.SelectVoice('{self.voice}'); $s.SetOutputToWaveFile('{wav}'); $s.Speak('测试'); $s.Dispose()"],
                    capture_output=True, timeout=120)
            art.status = "MOCK"
            return art
        # 真实 TTS
        try:
            backend, voice = self.synthesize_wav(text, wav)
        except Exception as e:
            art.status = "TTS_GENERATION_FAILED"
            art.error = str(e)[:300]
            return art
        # WAV 校验
        probe = _probe_audio(wav)
        if not probe.get("duration") or probe["duration"] <= 0.5 or not probe.get("codec"):
            art.status = "TTS_GENERATION_FAILED"
            art.error = f"wav invalid: {probe}"
            return art
        art.audio_duration = round(probe["duration"], 3)
        art.chars_per_second = round(len(text) / probe["duration"], 2)
        art.backend = backend
        art.voice = voice
        art.audio_sha256 = _sha256_file(wav)[:16]
        # 时长异常：100+ 汉字却 <5s → 可疑
        if len(text) >= 100 and probe["duration"] < 5:
            art.status = "TTS_DURATION_ANOMALY"
            art.error = f"{len(text)} chars but {probe['duration']}s"
            return art
        # SRT
        try:
            srt_text = build_srt(text, probe["duration"], wav)
        except Exception as e:
            art.status = "SUBTITLE_GENERATION_FAILED"
            art.error = str(e)[:300]
            return art
        if not srt_text.strip():
            art.status = "SUBTITLE_GENERATION_FAILED"
            art.error = "empty srt"
            return art
        srt.write_text(srt_text, encoding="utf-8")
        art.srt = srt
        art.wav = wav
        art.subtitle_count = srt_text.count("\n\n") + (1 if srt_text.strip().endswith("\n") else 0)
        art.text_coverage = _text_coverage(text, srt_text)
        art.status = "NARRATION_READY"
        if art.text_coverage < 0.95:
            art.status = "SUBTITLE_TEXT_COVERAGE_LOW"
        return art


def validate_srt(srt_text: str, audio_duration: float) -> dict:
    """SRT 结构校验：index/start<end/monotonic/no-negative/last<=duration。"""
    import re
    ok = {"blocks": 0, "errors": []}
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    prev_end = -1.0
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            ok["errors"].append("block <3 lines")
            continue
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            ok["errors"].append(f"bad time line: {lines[1]}")
            continue
        def t(a, b, c, d):
            return int(a) * 3600 + int(b) * 60 + int(c) + int(d) / 1000
        start = t(*[int(x) for x in m.groups()[:4]])
        end = t(*[int(x) for x in m.groups()[4:]])
        ok["blocks"] += 1
        if start < 0 or end < 0:
            ok["errors"].append("negative time")
        if start >= end:
            ok["errors"].append("start>=end")
        if start < prev_end - 0.001:
            ok["errors"].append("non-monotonic")
        prev_end = end
        if end > audio_duration + 1.0:
            ok["errors"].append(f"end {end:.2f} > audio {audio_duration:.2f}")
    return ok
