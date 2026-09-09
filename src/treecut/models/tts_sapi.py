"""Offline Chinese speech synthesis via Windows SAPI (System.Speech).

V0.8.4 原因：tts_local 依赖 sherpa-onnx + VITS onnx 模型，本机无外网安装/下载；
Windows 自带「Microsoft Huihui Desktop (zh-CN)」离线语音 → 作为真实 TTS 后端。
接口镜像 treecut.models.tts_local.synthesize：synthesize(text, output_wav) -> Path。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

VOICE = "Microsoft Huihui Desktop"
_PS_TEMPLATE = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = [System.IO.File]::ReadAllText($args[0], [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $synth.SelectVoice('%VOICE%')
  $synth.SetOutputToWaveFile($args[1])
  $synth.Speak($text)
} finally {
  $synth.Dispose()
}
"""


def _available_voice(synth) -> bool:
    try:
        for v in synth.GetInstalledVoices():
            try:
                info = v.VoiceInfo
                if info.Name == VOICE or str(info.Culture).startswith("zh"):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def available() -> bool:
    """检测 SAPI 中文语音是否可用（只读，不合成）。"""
    try:
        import sysconfig
        # 通过 powershell 探测（避免在 python 内引用 System.Speech 需要 pythonnet）
        ps = ("$ErrorActionPreference='SilentlyContinue';"
              "Add-Type -AssemblyName System.Speech;"
              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              "[bool]($s.GetInstalledVoices() | Where-Object { try { $_.VoiceInfo.Name -eq '%VOICE%' } catch { $false } })"
              ).replace("%VOICE%", VOICE)
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, timeout=30)
        return b"True" in out.stdout
    except Exception:
        return False


def synthesize(text: str, output_wav: Path) -> Path:
    """用 Windows SAPI（Microsoft Huihui Desktop zh-CN）合成中文语音到 WAV。"""
    if not (text or "").strip():
        raise ValueError("配音文字不能为空")
    output_wav = Path(output_wav)
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(text)
        text_file = Path(tf.name)
    script = _PS_TEMPLATE.replace("%VOICE%", VOICE)
    script_file = output_wav.parent / f".tts_sapi_{output_wav.stem}.ps1"
    script_file.write_text(script, encoding="utf-8")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script_file), str(text_file), str(output_wav)],
            capture_output=True, timeout=300)
        if result.returncode != 0 or not output_wav.is_file() or output_wav.stat().st_size < 1000:
            err = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"SAPI TTS 失败: {err or '无输出文件'}")
        return output_wav
    finally:
        text_file.unlink(missing_ok=True)
        script_file.unlink(missing_ok=True)
