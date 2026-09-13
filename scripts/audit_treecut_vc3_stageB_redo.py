# -*- coding: utf-8 -*-
"""TREECUT VC3 Stage B-REDO — deterministic separation mapping (NO rglob).

Path is CONSTRUCTED from (model, source unique id, stem), never searched:
    native    = 02_separated_vocals/{model}/{model}/{stem}/vocals.wav
    canonical = 02_separated_vocals/{model}/{stem}/vocals.wav
Requires the strict 9 sources x 2 separation models = 18 one-to-one rows, checks
duration/samples against the source working PCM, re-reads each file's SHA from
disk for the metrics, and applies explicit contamination thresholds. Records
MUSIC_RESIDUAL_FAIL threshold/method. High-pollution sources that fail both
models are flagged for an additional BS-RoFormer/UVR-class attempt (no
force-picking among failures). Writes a CORRECTED audit; the INVALID one stays.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
EXP = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\experiments\VC3_OSS_R1")
MASTERS = EXP / "01_extracted_audio"
SEP = EXP / "02_separated_vocals"
DEMUCS_PY = Path(r"E:\TreeCutRuntime\voice_clone_envs\demucs\venv\Scripts\python.exe")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
MODELS = ["htdemucs", "mdx_extra"]
# user-flagged higher-pollution sources (search priority only, never hardcoded
# final results)
HIGH_POLLUTION = {"1f9c445a28736942cfd84d19ffc87293",
                  "3bad5e51a7e03bf91db9ea8192cf1044",
                  "4f8a6f3b4160ef49d5cf0135570b762d",
                  "67351bcb8b7d6de001cbc2d4235a559d"}
THRESHOLDS = {"music_residual_low_band_ratio_max": 0.25,
              "clipping_ratio_max": 1e-5,
              "speech_band_ratio_min": 0.45,
              "duration_tolerance_s": 0.25}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def wav_info(p):
    import soundfile as sf
    info = sf.info(str(p))
    return {"samplerate": info.samplerate, "channels": info.channels,
            "frames": info.frames, "duration_s": round(info.duration, 3)}


def metrics(p):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    seg = data[: min(len(data), sr * 30)]
    spec = np.abs(np.fft.rfft(seg)) ** 2 + 1e-12
    freqs = np.fft.rfftfreq(len(seg), 1 / sr)
    total = float(np.sum(spec))
    low = float(np.sum(spec[freqs < 200]) / total)
    speech = float(np.sum(spec[(freqs >= 300) & (freqs <= 3400)]) / total)
    hf = float(np.sum(spec[freqs > 4000]) / total)
    centroid = float(np.sum(freqs * spec) / total)
    flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))
    return {"low_band_ratio": round(low, 5),
            "speech_band_ratio": round(speech, 5),
            "hf_ratio": round(hf, 5), "centroid_hz": round(centroid, 1),
            "spectral_flatness": round(flat, 6),
            "clipping_ratio": round(float(np.mean(np.abs(data) >= 0.999)), 7),
            "peak": round(float(np.max(np.abs(data))), 5)}


def native_path(model, master_stem):
    """Deterministic demucs output: outdir/{track}/vocals.wav where outdir was
    SEP/model and track name = input master file stem (id + .master48k24)."""
    return SEP / model / master_stem / "vocals.wav"


def ensure_native(model, stem, master_stem):
    """Return the deterministic native path, running demucs only if absent."""
    nat = native_path(model, master_stem)
    if nat.is_file():
        return nat, "reused"
    master = MASTERS / f"{stem}.master48k24.wav"
    subprocess.run([str(DEMUCS_PY), "-m", "demucs.separate", "-n", model,
                    "--two-stems=vocals", "-o", str(SEP / model), str(master)],
                   capture_output=True, timeout=5400)
    return (nat, "ran") if nat.is_file() else (None, "failed")


def main():
    masters = {p.name.replace(".master48k24.wav", ""): p
               for p in sorted(MASTERS.glob("*.master48k24.wav"))}
    master_stems = {sid: f"{sid}.master48k24" for sid in masters}
    rows = []
    per_source = {}
    for stem, master in masters.items():
        mi = wav_info(master)
        per_source[stem] = {"master": {"path": str(master),
                                       "sha256": sha256_file(master), **mi},
                            "candidates": []}
        for model in MODELS:
            nat, how = ensure_native(model, stem, master_stems[stem])
            if nat is None:
                rows.append({"model": model, "source_id": stem,
                             "status": "NATIVE_OUTPUT_MISSING"})
                per_source[stem]["candidates"].append(
                    {"model": model, "status": "NATIVE_OUTPUT_MISSING"})
                continue
            # deterministic 48k canonical (demucs models output 44.1k)
            canon = SEP / model / (master_stems[stem] + ".vocals48k.wav")
            nat_sha = sha256_file(nat)
            if (not canon.exists()) or canon.with_suffix(".srcsha").read_text(
                    encoding="utf-8").strip() != nat_sha:
                subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel",
                                "error", "-i", str(nat), "-acodec",
                                "pcm_s24le", "-ar", "48000", "-ac", "1",
                                str(canon)], check=True, timeout=1800)
                canon.with_suffix(".srcsha").write_text(nat_sha, encoding="utf-8")
            sha = sha256_file(canon)
            wi = wav_info(canon)
            m = metrics(canon)
            row = {"model": model, "source_id": stem, "status": "OK",
                   "native_path": str(nat), "canonical_path": str(canon),
                   "native_sha256": sha256_file(nat),
                   "sha256": sha, "how": how, **wi, **m}
            row["duration_consistent"] = abs(wi["duration_s"] - mi["duration_s"]) \
                <= THRESHOLDS["duration_tolerance_s"]
            row["samplerate_consistent"] = wi["samplerate"] == mi["samplerate"]
            row["channels_consistent"] = wi["channels"] == 1
            row["MUSIC_RESIDUAL_FAIL"] = \
                row["low_band_ratio"] > THRESHOLDS["music_residual_low_band_ratio_max"]
            row["CLIPPING_FAIL"] = \
                row["clipping_ratio"] > THRESHOLDS["clipping_ratio_max"]
            row["VOICE_INTEGRITY_FAIL"] = \
                row["speech_band_ratio"] < THRESHOLDS["speech_band_ratio_min"]
            row["PASS"] = not (row["MUSIC_RESIDUAL_FAIL"] or row["CLIPPING_FAIL"]
                               or row["VOICE_INTEGRITY_FAIL"]
                               or not row["duration_consistent"]
                               or not row["samplerate_consistent"])
            rows.append(row)
            per_source[stem]["candidates"].append(row)
            print("row", model, stem[:12], "pass", row["PASS"],
                  "lowband", row["low_band_ratio"], "speech",
                  row["speech_band_ratio"], "how", how)

    # strict 18-row one-to-one check
    ok_rows = [r for r in rows if r.get("status") == "OK"]
    keys = [(r["model"], r["source_id"]) for r in ok_rows]
    mapping_ok = (len(rows) == 18 and len(ok_rows) == 18
                  and len(set(keys)) == 18)
    sha_unique_per_model = all(
        len({r["sha256"] for r in ok_rows if r["model"] == mdl}) == len(masters)
        for mdl in MODELS)

    # selection per source (never force-pick among failures)
    for stem, s in per_source.items():
        cands = [c for c in s["candidates"] if c.get("status") == "OK"]
        passing = [c for c in cands if c["PASS"]]
        if passing:
            best = min(passing, key=lambda c: c["low_band_ratio"])
            s["selected"] = best["model"]
            s["selected_sha256"] = best["sha256"]
            s["selection_status"] = "SELECTED_PASSING_CANDIDATE"
        else:
            s["selected"] = None
            s["selection_status"] = ("SOURCE_REQUIRES_ADDITIONAL_MODEL_"
                                     "(BS_RoFormer_or_UVR)"
                                     if stem in HIGH_POLLUTION
                                     else "NO_PASSING_CANDIDATE")
    need_extra = [k for k, v in per_source.items()
                  if v["selection_status"].startswith("SOURCE_REQUIRES")]

    audit = {"experiment": "TREECUT_VC3_SEPARATION_AUDIT_R1",
             "supersedes": "TREECUT_VC3_SEPARATION_AUDIT.json "
                           "(INVALID_SELECTION_PATH_RESOLUTION_BUG, kept for "
                           "history)",
             "method": "deterministic path construction "
                       "(model, source_id, stem) - rglob forbidden",
             "separation_models": MODELS,
             "terminology_note": "HTDemucs and MDX-extra are two separation "
                                 "MODELS/ARCHITECTURES; they are not presented as "
                                 "two fully independent tool families",
             "expected_rows": 18, "rows_ok": len(ok_rows),
             "mapping_one_to_one_ok": mapping_ok,
             "sha_unique_per_model": sha_unique_per_model,
             "thresholds": THRESHOLDS,
             "music_residual_definition":
                 "MUSIC_RESIDUAL_FAIL_IN_TRAIN=0 means every TRAIN segment must "
                 "be below the documented low_band_ratio threshold and pass the "
                 "detector; it does NOT require zero music energy anywhere in "
                 "the spectrum",
             "sources_requiring_additional_model": need_extra,
             "per_source": per_source, "rows": rows,
             "generated_at": datetime.now().isoformat(timespec="seconds")}
    (OUT / "TREECUT_VC3_SEPARATION_AUDIT_R1.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    (EXP / "VC3_LIVE_STATUS.json").write_text(json.dumps(
        {"current_phase": "B_redo_done", "rows_ok": len(ok_rows),
         "mapping_ok": mapping_ok, "need_additional_model": need_extra,
         "last_artifact_time": datetime.now().isoformat(timespec="seconds")},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("rows_ok", len(ok_rows), "mapping_ok", mapping_ok,
          "sha_unique", sha_unique_per_model, "need_extra", need_extra)


if __name__ == "__main__":
    main()
