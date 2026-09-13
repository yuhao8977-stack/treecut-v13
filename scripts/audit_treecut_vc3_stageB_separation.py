# -*- coding: utf-8 -*-
"""TREECUT VC3 Stage B — vocal separation (HTDemucs primary, MDX-extra_q
comparison), contamination detection and candidate selection. Selection is NOT
'least music only': vocals must also retain brightness (centroid), HF energy and
be free of clipping/metallic artefacts. Anonymous repo JSON only."""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
EXP = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\experiments\VC3_OSS_R1")
MASTERS = EXP / "01_extracted_audio"
SEP = EXP / "02_separated_vocals"
CLEAN = EXP / "03_clean_candidates"
DEMUCS_PY = Path(r"E:\TreeCutRuntime\voice_clone_envs\demucs\venv\Scripts\python.exe")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
MODELS = ["htdemucs", "mdx_extra"]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def metrics(wav):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    dur = len(data) / sr
    fr = int(sr * 0.02)
    n = max(1, len(data) // fr)
    rms = np.sqrt(np.mean(data[:n * fr].reshape(n, fr) ** 2, axis=1))
    silence = float(np.mean(rms < 10 ** (-45 / 20)))
    seg = data[: min(len(data), sr * 30)]
    spec = np.abs(np.fft.rfft(seg)) ** 2 + 1e-12
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    low = float(np.sum(spec[freqs < 200]) / np.sum(spec))
    hf = float(np.sum(spec[freqs > 4000]) / np.sum(spec))
    speech = float(np.sum(spec[(freqs >= 300) & (freqs <= 3400)]) / np.sum(spec))
    centroid = float(np.sum(freqs * spec) / np.sum(spec))
    flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))
    return {"duration_s": round(dur, 3), "silence_ratio": round(silence, 4),
            "low_band_ratio": round(low, 5), "hf_ratio": round(hf, 5),
            "speech_band_ratio": round(speech, 5),
            "centroid_hz": round(centroid, 1),
            "spectral_flatness": round(flat, 6),
            "clipping_ratio": round(float(np.mean(np.abs(data) >= 0.999)), 7),
            "peak": round(float(np.max(np.abs(data))), 5)}


def separate(master, model):
    outdir = SEP / model
    outdir.mkdir(parents=True, exist_ok=True)
    canonical = SEP / model / master.stem / "vocals.wav"
    if canonical.exists():
        return canonical
    # demucs writes out/{model}/{track}/vocals.wav; reuse anything already made
    existing = sorted(outdir.rglob("vocals.wav"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if existing:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        if existing[0] != canonical:
            canonical.write_bytes(existing[0].read_bytes())
        return canonical
    cmd = [str(DEMUCS_PY), "-m", "demucs.separate", "-n", model,
           "--two-stems=vocals", "-o", str(outdir), str(master)]
    r = subprocess.run(cmd, capture_output=True, timeout=5400)
    found = sorted(outdir.rglob("vocals.wav"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if r.returncode != 0 or not found:
        log = (EXP / "11_logs" / f"demucs_{model}_{master.stem}.log")
        log.write_bytes(r.stdout[-4000:] + b"\n" + r.stderr[-4000:])
        return None
    canonical.parent.mkdir(parents=True, exist_ok=True)
    if found[0] != canonical:
        canonical.write_bytes(found[0].read_bytes())
    return canonical


def main():
    SEP.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    (EXP / "11_logs").mkdir(parents=True, exist_ok=True)
    masters = sorted(MASTERS.glob("*.master48k24.wav"))
    rows = []
    for m in masters:
        mm = metrics(m)
        cands = []
        for model in MODELS:
            t0 = time.time()
            v = separate(m, model)
            if v is None:
                cands.append({"model": model, "status": "FAILED"})
                continue
            mv = metrics(v)
            mv.update({"model": model, "path": str(v), "sha256": sha256_file(v),
                       "seconds": round(time.time() - t0, 1),
                       "centroid_ratio_vs_master":
                           round(mv["centroid_hz"] / max(mm["centroid_hz"], 1e-6), 4),
                       "hf_ratio_vs_master":
                           round(mv["hf_ratio"] / max(mm["hf_ratio"], 1e-9), 4)})
            cands.append(mv)
        # selection: contamination must pass AND voice must stay intact
        def ok(c):
            return (c.get("status") != "FAILED"
                    and c["low_band_ratio"] <= 0.25
                    and c["clipping_ratio"] <= 1e-5
                    and c["speech_band_ratio"] >= 0.45)
        good = [c for c in cands if ok(c)]
        if good:
            best = min(good, key=lambda c: c["low_band_ratio"])
            reason = "selected_lowest_music_residual_among_intact_vocals"
        else:
            # prefer the candidate that keeps the voice intact, then least music
            intact = [c for c in cands if c.get("status") != "FAILED"
                      and c["speech_band_ratio"] >= 0.45]
            if intact:
                best = min(intact, key=lambda c: c["low_band_ratio"])
                reason = "MUSIC_RESIDUAL_FAIL_but_voice_intact_best_effort"
            else:
                best = None
                reason = "ALL_CANDIDATES_FAIL_CONTAMINATION_OR_VOICE_INTEGRITY"
        chosen = None
        if best is not None:
            chosen = CLEAN / (m.stem.replace(".master48k24", "") + ".vocal.wav")
            subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel",
                            "error", "-i", best["path"], "-acodec", "pcm_s24le",
                            "-ar", "48000", "-ac", "1", str(chosen)], check=True,
                           timeout=1800)
            chosen_meta = {"path": str(chosen), "sha256": sha256_file(chosen),
                           "model": best["model"], **metrics(chosen)}
        else:
            chosen_meta = None
        rows.append({"file": m.name, "master": {**mm, "sha256": sha256_file(m)},
                     "candidates": cands, "selection_reason": reason,
                     "chosen": chosen_meta})
        print("sep", m.name, "cands", len([c for c in cands if c.get('status') != 'FAILED']),
              "reason", reason)
        (EXP / "VC3_LIVE_STATUS.json").write_text(json.dumps(
            {"current_phase": "B_separation", "current_file": m.name,
             "completed_count": len(rows), "total_count": len(masters),
             "last_artifact_time": datetime.now().isoformat(timespec="seconds")},
            ensure_ascii=False, indent=1), encoding="utf-8")
    audit = {"experiment": "TREECUT_VC3_SEPARATION_AUDIT",
             "models": MODELS, "file_count": len(rows),
             "chosen_count": sum(1 for r in rows if r["chosen"]),
             "music_residual_fail_count": sum(
                 1 for r in rows if r["selection_reason"].startswith("MUSIC_RESIDUAL")),
             "rows": rows,
             "policy": "audio-only; no pitch/formant modification; selection "
                       "requires contamination pass AND voice integrity "
                       "(centroid/HF retention, no clipping)"}
    (OUT / "TREECUT_VC3_SEPARATION_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print("chosen", audit["chosen_count"], "of", len(rows),
          "fail", audit["music_residual_fail_count"])


if __name__ == "__main__":
    main()
