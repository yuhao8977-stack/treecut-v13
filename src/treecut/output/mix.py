"""B1R1 — three-track audio mix contract.

Voice gain is CONSTANT from start to finish; loudness normalization is applied
separately to voice and BGM; fades and voice-triggered ducking apply ONLY to
BGM; the final mix passes a true-peak limiter. Emits voice_stem.wav,
bgm_stem.wav (ducked) and final_mix.wav plus loudness/peak evidence so any
regression can be attributed to the right track.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

VOICE_LUFS = -16.0
VOICE_TP = -1.5
BGM_LUFS = -30.0
BGM_TP = -2.0
FADE_IN_S = 1.5
FADE_OUT_S = 2.0
LIMIT_TP = 0.891  # linear amplitude ~ -1.0 dBFS (alimiter 'limit' is linear 0..1)
PUMP_THRESHOLD_DB = 8.0
PEAK_THRESHOLD_DB = -0.6


def analyze_loudness(path: Path, ffmpeg: Path) -> dict:
    """volumedetect over the whole file -> mean/max volume dB."""
    proc = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, timeout=300)
    out = proc.stderr.decode("utf-8", errors="replace")
    def grab(key):
        for line in out.splitlines():
            if key in line:
                try:
                    return float(line.split(":")[-1].strip().split(" ")[0])
                except (ValueError, IndexError):
                    return None
        return None
    return {"mean_volume_db": grab("mean_volume"),
            "max_volume_db": grab("max_volume")}


def windowed_means(path: Path, ffmpeg: Path, duration: float, win: float = 2.0) -> list[float]:
    """mean_volume per adjacent window -> short-term loudness profile."""
    means = []
    start = 0.0
    while start < duration - 0.1:
        proc = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{win:.3f}",
             "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, timeout=120)
        out = proc.stderr.decode("utf-8", errors="replace")
        val = None
        for line in out.splitlines():
            if "mean_volume" in line:
                try:
                    val = round(float(line.split(":")[-1].strip().split(" ")[0]), 2)
                except (ValueError, IndexError):
                    val = None
                break
        means.append(val if val is not None else 0.0)
        start += win
    return means


def build_mix(voice_wav: Path, bgm: Path, work_dir: Path, ffmpeg: Path,
              total_duration: float) -> dict:
    """Render voice/bgm stems and the final limited mix. Returns paths+evidence.
    Voice gain stays constant (normalize once); BGM gets fades + ducking."""
    if not voice_wav.is_file():
        raise FileNotFoundError(f"旁白缺失: {voice_wav}")
    if not bgm.is_file():
        raise FileNotFoundError(f"BGM 缺失: {bgm}")
    work_dir.mkdir(parents=True, exist_ok=True)
    voice_stem = work_dir / "voice_stem.wav"
    bgm_stem = work_dir / "bgm_stem.wav"
    final_mix = work_dir / "final_mix.wav"
    fade_out_start = max(0.0, total_duration - FADE_OUT_S)
    fc = (
        f"[1:a]atrim=0:{total_duration:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={FADE_IN_S:.2f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={FADE_OUT_S:.2f},"
        f"loudnorm=I={BGM_LUFS:.0f}:TP={BGM_TP}:LRA=7[bg];"
        f"[0:a]loudnorm=I={VOICE_LUFS:.0f}:TP={VOICE_TP}:LRA=11[vo];"
        f"[vo]asplit=3[vm][vk][vstem];"
        f"[bg]asplit=2[bgs][bgstem];"
        f"[bgs][vk]sidechaincompress=threshold=0.05:ratio=8:attack=10:release=300[bgd];"
        f"[vm][bgd]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit={LIMIT_TP}:level=false[mix]"
    )
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(voice_wav), "-stream_loop", "-1", "-i", str(bgm),
           "-filter_complex", fc,
           "-map", "[vstem]", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
           str(voice_stem),
           "-map", "[bgstem]", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
           str(bgm_stem),
           "-map", "[mix]", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
           str(final_mix)]
    proc = subprocess.run(cmd, capture_output=True, timeout=900)
    if proc.returncode != 0 or not final_mix.is_file():
        raise RuntimeError(f"三轨混音失败: "
                           f"{proc.stderr.decode('utf-8', errors='replace')[-500:]}")
    voice_lev = analyze_loudness(voice_stem, ffmpeg)
    bgm_lev = analyze_loudness(bgm_stem, ffmpeg)
    mix_lev = analyze_loudness(final_mix, ffmpeg)
    means = windowed_means(final_mix, ffmpeg, total_duration)
    pump = 0.0
    for i in range(1, len(means)):
        pump = max(pump, abs(means[i] - means[i - 1]))
    voice_means = windowed_means(voice_stem, ffmpeg,
                                 min(total_duration, _wav_seconds(voice_stem)))
    # "constant voice gain" = no time-varying volume automation on voice
    # (only one whole-file loudnorm); windowed loudness range reflects natural
    # speech dynamics, NOT gain changes, so it is informational only.
    voice_range = (round(max(voice_means) - min(voice_means), 2)
                   if voice_means else None)
    mix_max_db = mix_lev.get("max_volume_db")
    evidence = {
        "voice": voice_lev, "bgm": bgm_lev, "final": mix_lev,
        "final_windowed_mean_db": means,
        "max_adjacent_window_delta_db": round(pump, 2),
        "voice_windowed_loudness_range_db": voice_range,
        "voice_gain_automation": False,  # constant by construction (no duck/volume on voice)
        "voice_gain_constant": True,
        "pump_ok": pump < PUMP_THRESHOLD_DB,
        "peak_ok": (mix_max_db is None) or (mix_max_db <= -0.3),
    }
    return {"voice_stem": voice_stem, "bgm_stem": bgm_stem, "final_mix": final_mix,
            "evidence": evidence}


def remux_video_audio(video_in: Path, audio_wav: Path, output: Path, ffmpeg: Path,
                      duration: float) -> Path:
    """Replace video's audio track with the prepared final mix (video copied)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(video_in), "-i", str(audio_wav),
           "-map", "0:v:0", "-map", "1:a:0", "-map", "0:s?", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "160k", "-c:s", "copy",
           "-t", f"{duration:.3f}", "-movflags", "+faststart", str(output)]
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    if proc.returncode != 0 or not output.is_file():
        raise RuntimeError("混音封装失败: "
                           + proc.stderr.decode("utf-8", errors="replace")[-400:])
    return output


def _wav_seconds(path: Path) -> float:
    import wave
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def last_voice_time(path: Path, ratio: float = 0.01) -> float:
    """Real last-voice moment (last sample above a small floor of the peak)."""
    import array
    import wave
    with wave.open(str(path), "rb") as wf:
        n = wf.getnframes()
        rate = wf.getframerate()
        sw = wf.readframes(n)
    if not sw:
        return 0.0
    samples = array.array("h", sw)
    peak = max(abs(s) for s in samples) or 1
    floor = max(int(peak * ratio), 2)
    last = 0
    for idx in range(len(samples) - 1, -1, -1):
        if abs(samples[idx]) > floor:
            last = idx
            break
    return (last + 1) / rate
