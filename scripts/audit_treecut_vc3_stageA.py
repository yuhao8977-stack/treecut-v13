# -*- coding: utf-8 -*-
"""TREECUT VC3 Stage0/A — preflight, decision freeze, raw source manifest,
48k/24-bit mono master extraction (read-only originals) + first-pass audio
forensics (music residual proxy, silence, F0, LUFS/TP). Anonymous repo JSON."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
SRC_DIR = Path(r"C:\Users\admin\Desktop\录音训练文件")
EXP = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\experiments\VC3_OSS_R1")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
FFPROBE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffprobe.exe")
NAMES = ["ffe0fe05aea1281802ad10e04db84bea.mp4",
         "1f9c445a28736942cfd84d19ffc87293.mp4",
         "3bad5e51a7e03bf91db9ea8192cf1044.mp4",
         "4f8a6f3b4160ef49d5cf0135570b762d.mp4",
         "7c9133e56ad2b7b8dc2c9f08b0813f7f.mp4",
         "36d855036cae95e20b557bd2132a6e1c.mp4",
         "67351bcb8b7d6de001cbc2d4235a559d.mp4",
         "b1e2da63aa73b6364dc599f6d2d4517a.mp4",
         "fbb22200af6d3441fe2ebc0be82a9b57.mp4"]
SUBDIRS = ["00_raw_manifest", "01_extracted_audio", "02_separated_vocals",
           "03_clean_candidates", "04_segments", "05_transcripts", "06_dataset",
           "07_zero_shot", "08_finetune", "09_evaluation", "10_blind_review",
           "11_logs"]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a):
    p = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr


def probe(p):
    r = subprocess.run([str(FFPROBE), "-v", "quiet", "-print_format", "json",
                        "-show_format", "-show_streams", str(p)],
                       capture_output=True, timeout=120)
    d = json.loads(r.stdout.decode("utf-8", errors="replace"))
    a = next((s for s in d["streams"] if s.get("codec_type") == "audio"), {})
    v = next((s for s in d["streams"] if s.get("codec_type") == "video"), {})
    return {"container": d["format"].get("format_name"),
            "video_duration": float(v.get("duration") or
                                    d["format"].get("duration") or 0),
            "audio_duration": float(a.get("duration") or
                                    d["format"].get("duration") or 0),
            "audio_codec": a.get("codec_name"),
            "sample_rate": a.get("sample_rate"),
            "channels": a.get("channels"),
            "bitrate": a.get("bit_rate") or d["format"].get("bit_rate"),
            "creation_metadata": d["format"].get("tags", {})}


def loudness(wav):
    r = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(wav), "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, timeout=600)
    e = r.stderr.decode("utf-8", errors="replace")
    try:
        b = e[e.index("{"): e.rindex("}") + 1]
        d = json.loads(b)
        return {"lufs": float(d["input_i"]), "tp": float(d["input_tp"])}
    except Exception:
        return {"lufs": None, "tp": None}


def forensics(wav):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / sr
    fr = int(sr * 0.02)
    n = len(data) // fr
    frames = data[:n * fr].reshape(n, fr)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    thr = 10 ** (-45 / 20)
    silence = float(np.mean(rms < thr))
    # low-band (music/bass) energy proxy: FFT energy < 200Hz share
    spec = np.abs(np.fft.rfft(data[: min(len(data), sr * 30)]))
    freqs = np.fft.rfftfreq(min(len(data), sr * 30), 1 / sr)
    low = float(np.sum(spec[freqs < 200] ** 2) /
                (np.sum(spec ** 2) + 1e-9))
    # spectral flatness (music/noise proxy)
    psd = spec ** 2 + 1e-12
    flat = float(np.exp(np.mean(np.log(psd))) / np.mean(psd))
    f0s = []
    step = int(sr * 0.03)
    for st in range(0, len(data) - step, step):
        blk = data[st:st + step]
        if float(np.sqrt(np.mean(blk ** 2))) < 0.01:
            continue
        ac = np.correlate(blk - blk.mean(), blk - blk.mean(), "full")[len(blk) - 1:]
        lag = np.argmax(ac[80:int(sr / 60)]) + 80 if len(ac) > 80 else 0
        if lag > 0:
            f = sr / lag
            if 60 <= f <= 400:
                f0s.append(f)
    return {"duration_s": round(dur, 3), "silence_ratio": round(silence, 4),
            "low_band_energy_ratio": round(low, 4),
            "spectral_flatness": round(flat, 5),
            "f0_median_hz": round(float(np.median(f0s)), 1) if f0s else None,
            "f0_iqr_hz": round(float(np.subtract(*np.percentile(f0s, [75, 25]))), 1)
            if len(f0s) > 4 else None,
            "clipping_ratio": round(float(np.mean(np.abs(data) >= 0.999)), 7),
            "peak": round(float(np.max(np.abs(data))), 5)}


def main():
    t0 = time.time()
    for d in SUBDIRS:
        (EXP / d).mkdir(parents=True, exist_ok=True)
    code, head, _ = git("rev-parse", "HEAD")
    _, origin, _ = git("rev-parse", "origin/main")
    _, branch, _ = git("branch", "--show-current")
    _, status, _ = git("status", "--porcelain=v1")
    pre = {"start_time": datetime.now().isoformat(timespec="seconds"),
           "branch": branch, "head": head, "origin_main": origin,
           "head_eq_origin": head == origin,
           "worktree_clean_before_this_task":
               status == "" or all(l.startswith("??") for l in status.splitlines()
                                   if l.strip()),
           "status_lines": status.splitlines()[:20]}
    try:
        import torch
        pre["torch"] = torch.__version__
        pre["cuda"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            pre["gpu"] = torch.cuda.get_device_name(0)
            pre["gpu_mem_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 1)
    except Exception as exc:  # noqa: BLE001
        pre["torch_error"] = str(exc)
    pre["ffmpeg"] = str(FFMPEG)
    pre["disk_free_gb"] = {str(d): round(shutil.disk_usage(d).free / 2 ** 30, 1)
                           for d in ("E:\\", "C:\\")}
    pre["E_TreeCutRuntime_writable"] = _writable(Path(r"E:\TreeCutRuntime"))

    freeze = {
        "experiment": "TREECUT_VC3_DECISION_FREEZE",
        "VOICE_OWNER_AUTHORIZED": "YES", "SAME_FEMALE_OWNER_CONFIRMED": "YES",
        "SAME_AS_VOICE_001_TARGET": "YES", "NEW_VIDEO_COUNT": 9,
        "NEW_RAW_DURATION_EXPECTED": 539.5, "AUDIO_ONLY_POLICY": "YES",
        "VIDEO_VISUAL_CONTENT_ALLOWED_FOR_MODEL": "NO",
        "BACKGROUND_MUSIC_ALLOWED_FOR_MODEL": "NO",
        "SOUND_EFFECT_ALLOWED_FOR_MODEL": "NO",
        "OLD_MALE_DRIFT_OUTPUT_ALLOWED_AS_REFERENCE": "NO",
        "ZERO_SHOT_FIRST": "YES", "FINE_TUNE_CONDITIONAL_ONLY": "YES",
        "PRODUCTION_INTEGRATION_ALLOWED": "NO", "TREECUT_TTS_REPLACED": "NO",
        "B2_C0_N1_GEOM_CAM": "NOT_STARTED",
        "SAME_SPEAKER_DIFFERENT_POST_PROCESSING_DOMAINS": "YES",
        "USER_PREFERENCE_IS_SAMPLE_LEVEL_ONLY": "YES", "VC2_ACCEPTED": "NO",
        "VC2_PARTIAL_DIRECTIONAL_SIGNAL": "YES",
        "R2_MALE_MAGNETIC_DRIFT_NEGATIVE_REFERENCE": "YES",
        "preflight": pre,
    }
    (OUT / "TREECUT_VC3_DECISION_FREEZE.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")

    found, missing = [], []
    for n in NAMES:
        p = SRC_DIR / n
        (found if p.is_file() else missing).append(n)
    if missing:
        (OUT / "TREECUT_VC3_SOURCE_MANIFEST.json").write_text(json.dumps(
            {"experiment": "TREECUT_VC3_SOURCE_MANIFEST",
             "missing": missing, "found": found,
             "STOP_REASON": "missing_source_files"}, ensure_ascii=False,
            indent=1), encoding="utf-8")
        print("MISSING", missing)
        return

    entries = []
    total = 0.0
    for n in NAMES:
        src = SRC_DIR / n
        info = {"file": n, "absolute_path": str(src),
                "file_size": src.stat().st_size,
                "sha256": sha256_file(src), **probe(src)}
        total += info["audio_duration"]
        entries.append(info)
        print("manifest", n, round(info["audio_duration"], 2), "s")
    manifest = {"experiment": "TREECUT_VC3_SOURCE_MANIFEST",
                "source_dir": str(SRC_DIR), "file_count": len(entries),
                "raw_total_audio_duration_s": round(total, 3),
                "expected_duration_s": 539.5,
                "hash_match_expected": None,
                "files": entries}
    (OUT / "TREECUT_VC3_SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # extract masters 48k/24bit mono (no normalization/speed/pitch)
    masters = []
    for e in entries:
        src = Path(e["absolute_path"])
        out = EXP / "01_extracted_audio" / (Path(e["file"]).stem + ".master48k24.wav")
        if not out.exists():
            subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel",
                            "error", "-i", str(src), "-vn", "-acodec",
                            "pcm_s24le", "-ar", "48000", "-ac", "1",
                            str(out)], check=True, timeout=1800)
        f = forensics(out)
        f.update(loudness(out))
        masters.append({"file": e["file"], "master": str(out),
                        "sha256": sha256_file(out),
                        "source_sha256": e["sha256"], **f})
        print("master", e["file"], f["duration_s"], "silence",
              f["silence_ratio"], "lowband", f["low_band_energy_ratio"],
              "f0", f["f0_median_hz"])
    audit = {"experiment": "TREECUT_VC3_DATASET_AUDIT",
             "phase": "A_masters_only",
             "master_count": len(masters),
             "master_total_duration_s": round(sum(m["duration_s"] for m in masters), 3),
             "masters": masters,
             "note": "separation/segmentation/speaker gates not yet run"}
    (OUT / "TREECUT_VC3_DATASET_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    live = {"current_phase": "A_masters_done", "completed_count": len(masters),
            "total_count": len(NAMES), "elapsed_s": round(time.time() - t0, 1),
            "last_artifact_time": datetime.now().isoformat(timespec="seconds")}
    (EXP / "VC3_LIVE_STATUS.json").write_text(
        json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOTAL", round(total, 2), "s ; masters", len(masters))


def _writable(p: Path) -> bool:
    try:
        t = p / ".vc3_wtest"
        t.write_text("x", encoding="utf-8")
        t.unlink()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
