# -*- coding: utf-8 -*-
"""TREECUT VC2 Stage0/1 — machine preflight + decision freeze + dataset audit
(A1 identity, A3 per-segment quality gate, speaker machine proxy). Anonymous
repo JSON only (no transcripts)."""
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
PROFILE = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001")
SEG = PROFILE / "segments"
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
SRC_SHA = "4f453ddfa046fe9b7d9f373d1f7a80c8fe9e16703dd95054bda0fb0cb58992e5"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a):
    p = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def main():
    t0 = time.time()
    start = datetime.now().isoformat(timespec="seconds")
    _, head, _ = git("rev-parse", "HEAD")
    _, origin, _ = git("rev-parse", "origin/main")
    _, branch, _ = git("branch", "--show-current")
    rc, status, _ = git("status", "--porcelain=v1")
    preflight = {"start_time": start, "branch": branch.strip(),
                 "head": head.strip(), "origin_main": origin.strip(),
                 "head_eq_origin": head.strip() == origin.strip(),
                 "worktree_clean": status.strip() == ""}
    try:
        import torch
        preflight["torch"] = torch.__version__
        preflight["cuda"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            preflight["gpu"] = torch.cuda.get_device_name(0)
            preflight["gpu_mem_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 1)
    except Exception as exc:  # noqa: BLE001
        preflight["torch_error"] = str(exc)
    preflight["disk_free_gb"] = {str(d): round(shutil.disk_usage(d).free / 2 ** 30, 1)
                                 for d in ("E:\\", "C:\\")}
    import sys as _s
    preflight["python"] = _s.version.split()[0]
    preflight["python_exe"] = _s.executable

    freeze = {
        "experiment": "TREECUT_VC2_DECISION_FREEZE",
        "ARCHITECT_REVIEW_DATE": "2026-09-09",
        "PREFERRED_ANONYMOUS_LABEL": "A", "LABEL_A_BACKEND": "GPT_SOVITS",
        "LABEL_B_BACKEND": "MELO", "GPT_SOVITS_CLOSER_THAN_MELO": "YES",
        "ZERO_SHOT_DIRECTION_VALID": "YES",
        "ZERO_SHOT_PASS": "PARTIAL_NOT_ACCEPTED",
        "VOICE_SIMILARITY_ASSESSMENT":
            "SOMEWHAT_SIMILAR_BUT_SUBSTANTIAL_GAP_REMAINS",
        "FINE_TUNE_NEEDED": "YES",
        "FINE_TUNE_ALLOWED": "YES_INTERNAL_EXPERIMENT_ONLY",
        "PRODUCTION_INTEGRATION_ALLOWED": "NO",
        "TREECUT_TTS_REPLACED": "NO", "VOICE_OWNER_AUTHORIZED": "YES",
        "known_issues": {
            "pause_ratio_ref": 0.11, "pause_ratio_vc1_gpt": [0.29, 0.37],
            "gpt_slower_than_melo": True,
            "old_T5_renamed": "LONG_STRESS_TEST_NOT_25S",
            "transcripts_unverified": True,
            "single_speaker_human_confirmed": "NO",
            "weight_license": "INTERNAL_TEST_ONLY_PENDING_COMMERCIAL_CONFIRM",
            "infer_config_in_audit_temp": "migrate to permanent experiment dir"},
    }
    (OUT / "TREECUT_VC2_DECISION_FREEZE.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")

    # dataset audit from VC0 unique segments (read-only)
    local = json.loads((PROFILE / "vc0_local_manifest.json")
                       .read_text(encoding="utf-8"))
    uniq = [s for s in local["segments"]]
    import numpy as np
    import soundfile as sf
    rows = []
    for s in sorted(uniq, key=lambda x: x["start_s"]):
        sid = s["segment_id"]
        wav = SEG / f"{sid}.wav"
        data, sr = sf.read(str(wav), dtype="float32")
        dur = len(data) / sr
        peak = float(np.max(np.abs(data)))
        clip = float(np.mean(np.abs(data) >= 0.999))
        dc = float(np.mean(data))
        # silence ratio (energy frames < -45 dBFS)
        fr = int(sr * 0.02)
        n = len(data) // fr
        rms = np.sqrt(np.mean(data[:n * fr].reshape(n, fr) ** 2, axis=1))
        silent = float(np.mean(rms < 10 ** (-45 / 20)))
        # leading/trailing silence
        active = np.where(rms >= 10 ** (-45 / 20))[0]
        lead = float(active[0] * 0.02) if len(active) else dur
        trail = float((n - 1 - active[-1]) * 0.02) if len(active) else dur
        # F0 median proxy via autocorrelation on voiced frames
        f0s = []
        step = int(sr * 0.03)
        for st in range(0, len(data) - step, step):
            blk = data[st:st + step]
            if float(np.sqrt(np.mean(blk ** 2))) < 0.01:
                continue
            ac = np.correlate(blk - blk.mean(), blk - blk.mean(), "full")[len(blk) - 1:]
            if len(ac) < 2:
                continue
            lag = np.argmax(ac[80:int(sr / 60)]) + 80 if len(ac) > 80 else 0
            if lag > 0:
                f0 = sr / lag
                if 70 <= f0 <= 400:
                    f0s.append(f0)
        f0 = float(np.median(f0s)) if f0s else None
        f0iqr = float(np.subtract(*np.percentile(f0s, [75, 25]))) if len(f0s) > 4 else None
        proc = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(wav),
                               "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:"
                               "print_format=json", "-f", "null", "-"],
                              capture_output=True, timeout=300)
        err = proc.stderr.decode("utf-8", errors="replace")
        try:
            block = err[err.index("{"): err.rindex("}") + 1]
            d = json.loads(block)
            lufs = float(d.get("input_i", 0)); tp = float(d.get("input_tp", 0))
        except Exception:
            lufs = tp = None
        rows.append({"segment_id": sid, "start_s": s["start_s"],
                     "end_s": s["end_s"], "duration_s": round(dur, 3),
                     "sha256": sha256_file(wav),
                     "duplicate_of": s.get("duplicate_of"),
                     "peak": round(peak, 5),
                     "clipping_ratio": round(clip, 7),
                     "dc_offset": round(dc, 6),
                     "silence_ratio": round(silent, 4),
                     "lead_silence_s": round(lead, 3),
                     "trail_silence_s": round(trail, 3),
                     "f0_median_hz": round(f0, 1) if f0 else None,
                     "f0_iqr_hz": round(f0iqr, 1) if f0iqr else None,
                     "lufs": lufs, "true_peak_dbtp": tp,
                     "quality_flags": [f for f, on in
                                       [("clip", clip > 1e-4),
                                        ("dc", abs(dc) > 0.005)]
                                       if on]})
    total = round(sum(r["duration_s"] for r in rows), 3)
    dup_pairs = sorted({tuple(sorted((r["segment_id"],
                                      r["duplicate_of"]))) for r in rows
                        if r["duplicate_of"]})
    audit = {"experiment": "TREECUT_VC2_DATASET_AUDIT",
             "source_mp4_sha256": SRC_SHA,
             "original_wav_sha256": sha256_file(PROFILE / "source_original_audio.wav"),
             "unique_segment_count": len(rows),
             "unique_duration_s": total,
             "duplicate_pairs": len(dup_pairs),
             "dup_pair_ids": sorted(list(dup_pairs)),
             "segments": rows,
             "quality_flags_summary": {f: sum(1 for r in rows for f in
                                              r["quality_flags"])
                                       for f in ("clip", "dc")},
             "machine_speaker": {"method": "proxy features only (F0/centroid/"
                                           "silence) - no reliable speaker "
                                           "embedding available without new "
                                           "downloads",
                                 "verdict": "MACHINE_INCONCLUSIVE"}}
    (OUT / "TREECUT_VC2_DATASET_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"preflight": {k: preflight[k] for k in
                                    ("head", "head_eq_origin",
                                     "worktree_clean", "gpu", "gpu_mem_gb")},
                      "unique": len(rows), "duration": total,
                      "dup_pairs": len(dup_pairs),
                      "speaker": audit["machine_speaker"]["verdict"]},
                     ensure_ascii=False))
    print("elapsed_s", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
