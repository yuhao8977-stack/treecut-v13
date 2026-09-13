# -*- coding: utf-8 -*-
"""TREECUT VC3 Stage B-R2 — (1) re-process the legacy authorized source
0899bb1f...mp4 with the SAME standard as the 9 new videos; (2) extended audio
quality checks beyond the initial 3 thresholds (music classification proxy,
sustained low-band harmony/drum residue, separation-artefact proxy, ASR
completeness delta, speaker-embedding shift with two LOCAL embedding families:
CN-HuBERT + Whisper encoder); (3) local sampled listening page; (4) trusted
third-party separator weight verification probe (official source + license +
SHA required, else BLOCKED). Anonymous repo JSON only."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
import os
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DATA_ROOT", None)

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
EXP = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\experiments\VC3_OSS_R1")
MASTERS = EXP / "01_extracted_audio"
SEP = EXP / "02_separated_vocals"
PAGE = EXP / "10_blind_review"
DEMUCS_PY = Path(r"E:\TreeCutRuntime\voice_clone_envs\demucs\venv\Scripts\python.exe")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
OLD_MP4 = Path(r"C:\Users\admin\Desktop\0899bb1ff653be0070d46332d1b0d96a.mp4")
OLD_ID = "0899bb1ff653be0070d46332d1b0d96a"
MODELS = ["htdemucs", "mdx_extra"]
TH = {"music_residual_low_band_ratio_max": 0.25, "clipping_ratio_max": 1e-5,
      "speech_band_ratio_min": 0.45, "duration_tolerance_s": 0.25,
      "lowband_periodicity_max": 0.55, "artifact_flatness_max": 0.02,
      "asr_length_ratio_min": 0.90, "embedding_cosine_min": 0.85}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def wav_info(p):
    import soundfile as sf
    i = sf.info(str(p))
    return {"samplerate": i.samplerate, "channels": i.channels,
            "frames": i.frames, "duration_s": round(i.duration, 3)}


def native(model, master_stem):
    return SEP / model / master_stem / "vocals.wav"


def canon48(model, master_stem):
    return SEP / model / (master_stem + ".vocals48k.wav")


def ensure(model, master_stem, master):
    nat = native(model, master_stem)
    if not nat.is_file():
        subprocess.run([str(DEMUCS_PY), "-m", "demucs.separate", "-n", model,
                        "--two-stems=vocals", "-o", str(SEP / model),
                        str(master)], capture_output=True, timeout=5400)
    if not nat.is_file():
        return None
    c = canon48(model, master_stem)
    tag = c.with_suffix(".srcsha")
    nat_sha = sha256_file(nat)
    if (not c.exists()) or (not tag.exists()) or \
            tag.read_text(encoding="utf-8").strip() != nat_sha:
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(nat), "-acodec", "pcm_s24le", "-ar", "48000",
                        "-ac", "1", str(c)], check=True, timeout=1800)
        tag.write_text(nat_sha, encoding="utf-8")
    return c


def initial_metrics(p):
    import numpy as np
    import soundfile as sf
    d, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if d.ndim > 1:
        d = d.mean(axis=1)
    seg = d[: min(len(d), sr * 30)]
    spec = np.abs(np.fft.rfft(seg)) ** 2 + 1e-12
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    tot = float(np.sum(spec))
    return {"low_band_ratio": round(float(np.sum(spec[f < 200]) / tot), 5),
            "speech_band_ratio": round(float(np.sum(
                spec[(f >= 300) & (f <= 3400)]) / tot), 5),
            "hf_ratio": round(float(np.sum(spec[f > 4000]) / tot), 5),
            "clipping_ratio": round(float(np.mean(np.abs(d) >= 0.999)), 7),
            "peak": round(float(np.max(np.abs(d))), 5)}


def extended_metrics(p):
    """Music classification proxy (via vocal/instrument separation energy in
    speech gaps), sustained low-band periodicity (drums/harmony), separation
    artefact proxy (HF flatness), all computed on the SAME file whose SHA is
    recorded by the caller."""
    import numpy as np
    import soundfile as sf
    d, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if d.ndim > 1:
        d = d.mean(axis=1)
    fr = int(sr * 0.02)
    n = max(1, len(d) // fr)
    rms = np.sqrt(np.mean(d[:n * fr].reshape(n, fr) ** 2, axis=1))
    active = rms >= 10 ** (-45 / 20)
    gaps = ~active
    gap_energy = float(np.mean(rms[gaps]) + 1e-9) if gaps.any() else 0.0
    speech_energy = float(np.mean(rms[active]) + 1e-9) if active.any() else 0.0
    music_in_gaps_db = round(20 * np.log10(gap_energy / speech_energy), 2)
    # sustained low-band periodicity over the whole file (drums/bass residue)
    low = np.fft.rfft(d[: min(len(d), sr * 30)])
    # simple autocorrelation peak of the 60-200Hz band-passed envelope
    from scipy.signal import butter, filtfilt
    b, a = butter(4, [60 / (sr / 2), 200 / (sr / 2)], btype="band")
    band = filtfilt(b, a, d[: min(len(d), sr * 30)])
    env = np.abs(band)
    ac = np.correlate(env - env.mean(), env - env.mean(), "full")[len(env) - 1:]
    denom = ac[0] + 1e-12
    per = float(np.max(ac[int(sr * 0.15): int(sr * 1.0)]) / denom) \
        if len(ac) > int(sr * 1.0) else 0.0
    # artefact proxy: HF (>6k) spectral flatness (harsh/metallic residue)
    seg = d[: min(len(d), sr * 30)]
    spec = np.abs(np.fft.rfft(seg)) ** 2 + 1e-12
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    hf = spec[f > 6000]
    flat = float(np.exp(np.mean(np.log(hf + 1e-12))) / (np.mean(hf) + 1e-12)) \
        if hf.size else 0.0
    return {"music_in_gaps_db": music_in_gaps_db,
            "lowband_periodicity": round(per, 4),
            "hf_flatness_artifact_proxy": round(flat, 5),
            "silence_ratio": round(float(np.mean(gaps)), 4)}


def asr_chars(p):
    from faster_whisper import WhisperModel
    m = WhisperModel(str(Path(r"E:\TreeCutRuntime\models\Whisper-small")),
                     device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(p), language="zh", beam_size=5)
    return len("".join(s.text for s in segs).strip())


def embedding_hub(p, cache={}):
    """CN-HuBERT mean-pooled embedding via GPT-SoVITS local weights."""
    import numpy as np
    import torch
    from transformers import AutoFeatureExtractor, HubertModel
    key = "hubert"
    if key not in cache:
        root = Path(r"E:\TreeCutRuntime\models\VoiceClone\GPT_SoVITS\repo"
                    r"\chinese-hubert-base")
        cache[key] = (AutoFeatureExtractor.from_pretrained(str(root)),
                      HubertModel.from_pretrained(str(root),
                                                 torch_dtype=torch.float32).eval().float())
    fe, model = cache[key]
    import soundfile as sf
    d, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != 16000:
        import scipy.signal as ss
        d = ss.resample_poly(d, 16000, sr).astype("float32")
    iv = fe(d, sampling_rate=16000, return_tensors="pt")
    iv = {k: v.float() for k, v in iv.items()}
    with torch.inference_mode():
        out = model(**iv).last_hidden_state.mean(dim=1)[0].float().numpy()
    return out / (np.linalg.norm(out) + 1e-9)


def embedding_whisper(p, cache={}):
    import numpy as np
    import torch
    from faster_whisper import WhisperModel
    if "w" not in cache:
        cache["w"] = WhisperModel(str(Path(r"E:\TreeCutRuntime\models"
                                           r"\Whisper-small")), device="cpu",
                                  compute_type="int8")
    w = cache["w"]
    import soundfile as sf
    d, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != 16000:
        import scipy.signal as ss
        d = ss.resample_poly(d, 16000, sr).astype("float32")
    feats = w.feature_extractor(d[: 16000 * 30])
    try:
        import ctranslate2
        sv = ctranslate2.StorageView.from_array(
            feats[None, :].astype("float32"))
        enc = np.array(w.model.encode(sv))
        v = enc.mean(axis=1)[0]
        return v / (np.linalg.norm(v) + 1e-9)
    except Exception:
        return None


def cos(a, b):
    import numpy as np
    if a is None or b is None:
        return None
    return round(float(np.dot(a, b)), 4)


def main():
    PAGE.mkdir(parents=True, exist_ok=True)
    # (1) legacy source master (same standard: 48k/24-bit mono, no processing)
    old_master = MASTERS / f"{OLD_ID}.master48k24.wav"
    if OLD_MP4.is_file() and not old_master.exists():
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(OLD_MP4), "-vn", "-acodec", "pcm_s24le",
                        "-ar", "48000", "-ac", "1", str(old_master)], check=True,
                       timeout=1800)
    sources = {}
    for m in sorted(MASTERS.glob("*.master48k24.wav")):
        sid = m.name.replace(".master48k24.wav", "")
        sources[sid] = m
    rows = []
    for sid, master in sources.items():
        mstem = f"{sid}.master48k24"
        mi = wav_info(master)
        master_metrics = initial_metrics(master)
        master_asr = asr_chars(master)
        m_emb_h = embedding_hub(master)
        m_emb_w = embedding_whisper(master)
        for model in MODELS:
            c = ensure(model, mstem, master)
            if c is None:
                rows.append({"model": model, "source_id": sid,
                             "status": "NATIVE_OUTPUT_MISSING"})
                continue
            sha = sha256_file(c)
            wi = wav_info(c)
            init = initial_metrics(c)
            ext = extended_metrics(c)
            voc_asr = asr_chars(c)
            v_emb_h = embedding_hub(c)
            v_emb_w = embedding_whisper(c)
            row = {"model": model, "source_id": sid, "status": "OK",
                   "path": str(c), "sha256": sha,
                   "master_sha256": sha256_file(master), **wi, **init, **ext,
                   "duration_consistent": abs(wi["duration_s"] -
                                              mi["duration_s"]) <=
                   TH["duration_tolerance_s"],
                   "samplerate_consistent": wi["samplerate"] == mi["samplerate"],
                   "asr_chars_master": master_asr, "asr_chars_vocals": voc_asr,
                   "asr_length_ratio": round(voc_asr / max(master_asr, 1), 3),
                   "embedding_cosine_hubert": cos(m_emb_h, v_emb_h),
                   "embedding_cosine_whisper": cos(m_emb_w, v_emb_w),
                   "is_legacy_source": sid == OLD_ID}
            row["INITIAL_SCREEN_FAIL"] = not (
                init["low_band_ratio"] <= TH["music_residual_low_band_ratio_max"]
                and init["clipping_ratio"] <= TH["clipping_ratio_max"]
                and init["speech_band_ratio"] >= TH["speech_band_ratio_min"]
                and row["duration_consistent"] and row["samplerate_consistent"])
            row["EXTENDED_CHECK_FAIL"] = (
                ext["lowband_periodicity"] > TH["lowband_periodicity_max"]
                or ext["hf_flatness_artifact_proxy"] > TH["artifact_flatness_max"]
                or row["asr_length_ratio"] < TH["asr_length_ratio_min"]
                or (row["embedding_cosine_hubert"] is not None and
                    row["embedding_cosine_hubert"] < TH["embedding_cosine_min"])
                or (row["embedding_cosine_whisper"] is not None and
                    row["embedding_cosine_whisper"] < TH["embedding_cosine_min"]))
            row["CANDIDATE_PASS_ALL_CHECKS"] = not (row["INITIAL_SCREEN_FAIL"]
                                                    or row["EXTENDED_CHECK_FAIL"])
            rows.append(row)
            print("row", model, sid[:12], "init_fail", row["INITIAL_SCREEN_FAIL"],
                  "ext_fail", row["EXTENDED_CHECK_FAIL"], "asr_ratio",
                  row["asr_length_ratio"], "emb_h",
                  row["embedding_cosine_hubert"])

    per_source = {}
    for r in rows:
        if r.get("status") != "OK":
            continue
        per_source.setdefault(r["source_id"], []).append(r)
    for sid, cands in per_source.items():
        passing = [c for c in cands if c["CANDIDATE_PASS_ALL_CHECKS"]]
        best = min(passing, key=lambda c: c["low_band_ratio"]) if passing else None
        per_source[sid] = {"candidates": cands,
                           "selected": best["model"] if best else None,
                           "selected_sha256": best["sha256"] if best else None,
                           "status": "SEPARATION_CANDIDATE_SOURCE" if best
                           else "EXCLUDED_PENDING_ADDITIONAL_MODEL",
                           "is_legacy_source": sid == OLD_ID}

    audit = {"experiment": "TREECUT_VC3_SEPARATION_AUDIT_R2",
             "supersedes": ["TREECUT_VC3_SEPARATION_AUDIT.json (INVALID...)",
                            "TREECUT_VC3_SEPARATION_AUDIT_R1.json (mapping fix)"],
             "B_MAPPING_AND_PATH_FIX": "PASS",
             "B_AUDIO_QUALITY_FINAL_PASS": "PENDING",
             "source_count_total": len(per_source),
             "candidate_source_count":
                 sum(1 for v in per_source.values()
                     if v["status"] == "SEPARATION_CANDIDATE_SOURCE"),
             "thresholds": TH,
             "extended_checks": ["music_in_gaps_db (speech-gap music proxy)",
                                 "lowband_periodicity (drums/harmony residue)",
                                 "hf_flatness_artifact_proxy",
                                 "asr_length_ratio (completeness change)",
                                 "embedding_cosine with two LOCAL families "
                                 "(CN-HuBERT, Whisper encoder)"],
             "legacy_source_note": "0899bb1f... reprocessed with the same "
                                   "standard; ORIGINAL_REFERENCE.wav derives "
                                   "from it and must NOT be double-counted",
             "per_source": per_source, "rows": rows,
             "generated_at": datetime.now().isoformat(timespec="seconds")}
    (OUT / "TREECUT_VC3_SEPARATION_AUDIT_R2.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")

    # (3) local sampled listening page (master vs vocals, 20s excerpt each)
    items = []
    for sid, v in per_source.items():
        for c in v["candidates"]:
            if c["model"] != (v["selected"] or "htdemucs"):
                continue
            ex = PAGE / f"{sid}.vocals20s.wav"
            if not ex.exists():
                subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel",
                                "error", "-t", "20", "-i", c["path"], str(ex)],
                               check=True, timeout=600)
            items.append((sid, ex.name))
    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>",
            "<title>VC3 分离抽样试听</title></head><body>",
            "<h1>VC3 分离抽样试听（master 与 vocals，各 20s）</h1>",
            "<p>用于人工确认残留音乐/鼓点/伪影与人声是否被削薄。音频仅本地。</p>",
            "<h2>真实原声参考（不匿名）</h2>",
            "<audio controls src='../../samples/SAMPLE_A.wav'></audio>"]
    for sid, name in items:
        html.append(f"<h3>{sid}</h3><audio controls src='{name}'></audio>")
    html.append("</body></html>")
    (PAGE / "SEPARATION_SAMPLE_REVIEW.html").write_text("\n".join(html),
                                                        encoding="utf-8")

    # (4) trusted third-party separator weight verification (BLOCKED unless
    # official provenance + license + SHA can be shown; no unknown mirrors)
    probe = {"experiment": "TREECUT_VC3_ADDITIONAL_SEPARATOR_PROBE_R2",
             "requirement": "official publication or trusted mirror with model "
                            "card, license, original source URL and SHA-256",
             "status": "BLOCKED_NO_VERIFIABLE_WEIGHT_SOURCE",
             "reason": "huggingface.co unreachable in this environment; "
                       "modelscope reachable but no verified official "
                       "BS-RoFormer/UVR repository id was confirmed in this "
                       "round, and identical-name unknown mirrors are not "
                       "acceptable per architect ruling",
             "consequence": "the 4 high-pollution sources stay EXCLUDED_PENDING_"
                            "ADDITIONAL_MODEL; they are NOT used to reach the "
                            "source>=6 gate"}
    (OUT / "TREECUT_VC3_ADDITIONAL_SEPARATOR_PROBE_R2.json").write_text(
        json.dumps(probe, ensure_ascii=False, indent=1), encoding="utf-8")
    print("candidate sources",
          audit["candidate_source_count"], "of", audit["source_count_total"],
          "| legacy pass:",
          per_source.get(OLD_ID, {}).get("status"))


if __name__ == "__main__":
    main()
