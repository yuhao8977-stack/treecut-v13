# -*- coding: utf-8 -*-
"""TREECUT VC0 — voice reference freeze + offline clone A/B pipeline.

Read-only on the authorized source MP4 (audio only). Outputs:
  LOCAL (never git): E:\\TreeCutRuntime\\voice_profiles\\VOICE_001\\  (wavs,
  segments, asr transcripts, local manifest, blind samples)
  REPO (anonymous, no sound): reports/storage/TREECUT_VC0_*.json + report md.
Voice-owner authorization recorded separately (VOICE_OWNER_AUTHORIZED=YES).
No production chain change; no Melo replacement; no training; no picture use.
"""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MP4 = Path(r"C:\Users\admin\Desktop\0899bb1ff653be0070d46332d1b0d96a.mp4")
PROFILE = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001")
SEG = PROFILE / "segments"
ASR = PROFILE / "asr"
SAMPLES = PROFILE / "samples"
REPO_STORAGE = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
FFPROBE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffprobe.exe")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
E_MODELS = Path(r"E:\TreeCutRuntime\models")
ORIG = PROFILE / "source_original_audio.wav"   # 48k mono PCM immutable
WORK = PROFILE / "source_working_24k.wav"      # 24k mono PCM
sys.path.insert(0, str(E_SRC))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wav_probe(path):
    import soundfile as sf
    info = sf.info(str(path))
    return {"duration_s": round(info.duration, 3), "samplerate": info.samplerate,
            "channels": info.channels, "frames": info.frames}


def loudness(path):
    proc = subprocess.run(
        [str(FFMPEG), "-hide_banner", "-i", str(path), "-af",
         "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, timeout=300)
    err = proc.stderr.decode("utf-8", errors="replace")
    try:
        block = err[err.index("{"): err.rindex("}") + 1]
        d = json.loads(block)
        return {"input_i_lufs": float(d.get("input_i", 0)),
                "input_tp_dbtp": float(d.get("input_tp", 0)),
                "input_lra": float(d.get("input_lra", 0))}
    except Exception:
        return {"parse_error": err[-300:]}


def peak_rms_clip(path):
    import numpy as np
    import soundfile as sf
    data, _ = sf.read(str(path), dtype="float32")
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    rms = float(np.sqrt(np.mean(data ** 2))) if data.size else 0.0
    clip = float(np.mean(np.abs(data) >= 0.999)) if data.size else 0.0
    return {"peak": round(peak, 5), "rms_db": round(20 * np.log10(rms + 1e-9), 2),
            "clipping_ratio": round(clip, 6)}


def extract_wavs():
    for seg in (SEG, ASR, SAMPLES):
        seg.mkdir(parents=True, exist_ok=True)
    if not ORIG.exists():
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(MP4), "-vn", "-acodec", "pcm_s16le",
                        "-ar", "48000", "-ac", "1", str(ORIG)], check=True)
    if not WORK.exists():
        subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(MP4), "-vn", "-acodec", "pcm_s16le",
                        "-ar", "24000", "-ac", "1", str(WORK)], check=True)
    return {"original": {"path": str(ORIG), "sha256": sha256_file(ORIG),
                         **wav_probe(ORIG), **loudness(ORIG),
                         **peak_rms_clip(ORIG)},
            "working": {"path": str(WORK), "sha256": sha256_file(WORK),
                        **wav_probe(WORK), **loudness(WORK),
                        **peak_rms_clip(WORK)}}


def vad_segments(path, frame_s=0.02, energy_db=-50.0, min_s=0.4, gap_s=0.6):
    """Energy VAD on mono float samples; returns list of (start_s, end_s)."""
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32")
    n = int(sr * frame_s)
    frames = len(data) // n
    rms = np.sqrt(np.mean(data[:frames * n].reshape(frames, n) ** 2, axis=1))
    thr = 10 ** (energy_db / 20)
    active = rms >= thr
    segs = []
    start = None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        elif not a and start is not None:
            if (i - start) * frame_s >= min_s:
                segs.append((start * frame_s, i * frame_s))
            start = None
    if start is not None and (len(active) - start) * frame_s >= min_s:
        segs.append((start * frame_s, len(active) * frame_s))
    # merge gaps shorter than gap_s
    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] < gap_s:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged, {"frame_s": frame_s, "energy_db": energy_db, "raw_segments": len(segs)}


def similarity(a, b):
    """Normalized max cross-correlation on ~6k downsampled amplitude (0..1)."""
    import numpy as np
    from scipy import signal
    def prep(x):
        x = np.abs(x)
        step = max(1, len(x) // 60000)
        return x[::step]
    a2, b2 = prep(a), prep(b)
    n = min(len(a2), len(b2))
    if n < 2000:
        return 0.0
    a2, b2 = a2[:n], b2[:n]
    a2 = (a2 - a2.mean()) / (a2.std() + 1e-9)
    b2 = (b2 - b2.mean()) / (b2.std() + 1e-9)
    corr = signal.fftconvolve(a2, b2[::-1], mode="full")
    denom = len(a2)
    peak = float(np.max(np.abs(corr)) / denom) if denom else 0.0
    return round(peak, 4)


def slice_wav(path, start, end, out):
    subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(path),
                    "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1",
                    str(out)], check=True)


def run_asr(seg_paths):
    """faster-whisper small (models/Whisper-small), language zh; transcripts
    are TRANSCRIPT_UNVERIFIED until human review."""
    from faster_whisper import WhisperModel
    model = WhisperModel(str(E_MODELS / "Whisper-small"), device="cpu",
                         compute_type="int8")
    out = {}
    for sid, p in seg_paths.items():
        try:
            segs, info = model.transcribe(str(p), language="zh", beam_size=5)
            text = "".join(s.text for s in segs).strip()
        except Exception as exc:  # noqa: BLE001
            text = f"__ASR_ERROR__: {exc}"
        out[sid] = text
    return out


def main():
    t0 = time.time()
    meta = {"voice_profile_id": "VOICE_001",
            "VOICE_OWNER_AUTHORIZED": "YES",
            "authorization_note": "voice owner confirmed authorization",
            "source": {"file": MP4.name,
                       "sha256": "4f453ddfa046fe9b7d9f373d1f7a80c8fe9e16703dd"
                                 "95054bda0fb0cb58992e5"}}
    meta["extracted"] = extract_wavs()
    segs, vad_info = vad_segments(WORK)
    meta["vad"] = {"segment_count": len(segs), **vad_info}

    # cut segment wavs + metrics
    import numpy as np
    import soundfile as sf
    raw, sr = sf.read(str(WORK), dtype="float32")
    seg_meta = []
    raw_segs = {}
    for i, (s, e) in enumerate(segs, 1):
        sid = f"seg{i:02d}"
        a = int(s * sr)
        b = min(int(e * sr), len(raw))
        raw_segs[sid] = raw[a:b]
        wav = SEG / f"{sid}.wav"
        if not wav.exists():
            slice_wav(WORK, s, e, wav)
        seg_meta.append({"segment_id": sid, "start_s": round(s, 3),
                         "end_s": round(e, 3),
                         "duration_s": round(e - s, 3),
                         "sha256": sha256_file(wav)})
    # dedup
    sim = {}
    keys = list(raw_segs)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            s = similarity(raw_segs[keys[i]], raw_segs[keys[j]])
            sim[(keys[i], keys[j])] = s
    pairs = [(k, v) for k, v in sim.items() if v >= 0.9]
    pairs.sort(key=lambda x: -x[1])
    used = set()
    dup_groups = []
    for (a, b), sc in pairs:
        if a in used or b in used:
            continue
        used.add(a)
        used.add(b)
        dup_groups.append((a, b, sc))
    keep = set()
    for a, b, sc in dup_groups:
        ma = peak_rms_clip(SEG / f"{a}.wav")
        mb = peak_rms_clip(SEG / f"{b}.wav")
        # keep the one with higher RMS unless it clips harder
        score = lambda m: m["rms_db"] - 60.0 * m["clipping_ratio"]
        keep.add(a if score(ma) >= score(mb) else b)
    unique = [m for m in seg_meta if m["segment_id"] in keep]
    unique.sort(key=lambda m: m["start_s"])
    dup_map = []
    for a, b, sc in dup_groups:
        kept = a if a in keep else b
        dropped = b if kept == a else a
        dup_map.append({"kept": kept, "dropped": dropped, "similarity": sc})
    total_unique = round(sum(m["duration_s"] for m in unique), 3)
    meta["dedup"] = {"raw_segment_count": len(segs),
                     "duplicate_pair_count": len(dup_groups),
                     "kept_unique_count": len(unique),
                     "unique_speech_duration_s": total_unique,
                     "pairs": dup_groups}

    # per kept segment full metrics + ASR (local only)
    asr_texts = {}
    if len(unique):
        seg_paths = {m["segment_id"]: SEG / f"{m['segment_id']}.wav" for m in unique}
        asr_texts = run_asr(seg_paths)
    local_manifest = {"voice_profile_id": "VOICE_001", "meta": meta,
                      "asr_language": "zh", "transcript_review_status":
                          "TRANSCRIPT_UNVERIFIED", "segments": []}
    for m in unique:
        sid = m["segment_id"]
        wav = SEG / f"{sid}.wav"
        lev = loudness(wav)
        prc = peak_rms_clip(wav)
        m.update(lev)
        m.update(prc)
        m["duplicate_of"] = next((d["dropped"] for d in dup_map
                                  if d["kept"] == sid), None)
        m["speaker_consistency"] = "AUTO_PROXY_PENDING"
        m["transcript"] = asr_texts.get(sid, "")
        m["transcript_review_status"] = "TRANSCRIPT_UNVERIFIED"
        m["dataset_eligible"] = False
        m["exclusion_reason"] = "awaiting human transcript + speaker review"
        local_manifest["segments"].append(m)
    (PROFILE / "vc0_local_manifest.json").write_text(
        json.dumps(local_manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (PROFILE / "vc0_vad_info.json").write_text(
        json.dumps({"vad": meta["vad"], "dedup": meta["dedup"]},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # speaker proxy (spectral centroid across kept segments) - anonymous
    from scipy import signal as sp_sig
    cents = []
    for m in unique:
        data, _ = sf.read(str(SEG / f"{m['segment_id']}.wav"), dtype="float32")
        f, t, zxx = sp_sig.stft(data, fs=24000, nperseg=1024)
        power = np.abs(zxx) ** 2
        cents.append(float(np.sum(f[:, None] * power) / (np.sum(power) + 1e-9)))
    speaker_proxy = {"mean_centroid_hz": round(float(np.mean(cents)), 1)
                     if cents else None,
                     "std_centroid_hz": round(float(np.std(cents)), 1)
                     if cents else None,
                     "single_speaker_confirmed": "NO"}

    # anonymous repo summary (NO transcript text, NO audio)
    anon = {"experiment": "TREECUT_VC0_SEGMENTS_SUMMARY",
            "voice_profile_id": "VOICE_001",
            "source_sha256": meta["source"]["sha256"],
            "extracted": {k: {kk: vv for kk, vv in v.items() if kk != "path"}
                          for k, v in meta["extracted"].items()},
            "vad": meta["vad"], "dedup": meta["dedup"],
            "speaker_proxy": speaker_proxy,
            "segments_anonymous": [
                {k: m[k] for k in ("segment_id", "start_s", "end_s",
                                   "duration_s", "sha256", "rms_db",
                                   "peak", "clipping_ratio",
                                   "input_i_lufs", "input_tp_dbtp",
                                   "duplicate_of") if k in m}
                for m in unique],
            "transcript_verified_count": 0,
            "review_status": "TRANSCRIPT_UNVERIFIED",
            "asr_text_stored_locally_only": True}
    (REPO_STORAGE / "TREECUT_VC0_SEGMENTS_SUMMARY.json").write_text(
        json.dumps(anon, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"vad": meta["vad"], "dedup": meta["dedup"],
                      "speaker_proxy": speaker_proxy}, ensure_ascii=False))
    print("elapsed_s", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
