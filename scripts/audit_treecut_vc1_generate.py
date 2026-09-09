# -*- coding: utf-8 -*-
"""TREECUT VC1-ZS — batch zero-shot generation + fair EVAL + metrics.

Runs under runtime python (has treecut LocalTTS + faster_whisper). Talks to the
GPT-SoVITS api_v2 server on 127.0.0.1:9880 via urllib (no extra deps).
Outputs RAW + EVAL(-16 LUFS, <=-1.5 dBTP) wavs LOCAL; anonymous metrics JSON to
repo reports/storage. No audio into git.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DATA_ROOT", None)

SAMPLES = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\samples")
SEG = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\segments")
REPO_STORAGE = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
GSV = "http://127.0.0.1:9880/tts"

TEXTS = {
    "T1": "这款岛台总长一米八，拉开以后可以满足六到八个人同时用餐。",
    "T2": "公牛轨道插座，烧水、充电、吃火锅都不用满屋拉线。",
    "T3": "您家现在装修到哪个阶段了？水电位置有没有提前预留？",
    "T4": ("这是一款专为小户型设计的伸缩岛台。平时收起来不占过道，需要时轻轻拉出，"
           "就能多出一张工作台。台面下方做了分区收纳，抽屉放文具，柜门里放餐具。"
           "台面宽度和高度都可以按户型定制，边角圆润，家里有老人小孩也不用担心磕碰。"
           "岩板表面耐刮耐热，打理起来非常简单，用起来非常顺手。"),
    "T5": ("小户型也能拥有实用岛台。平时收起来不占过道，需要时轻轻拉出，立刻多出一张工作台。"
           "它既能当办公桌，也能招待朋友用餐，一物三用不浪费。台面下方做了分区收纳，"
           "抽屉放文具，柜门里放餐具。常用物品放在顺手的高度，拿取不用弯腰。"
           "边角都做了圆润处理，家里有小孩也不用担心磕碰。台面宽度可以按户型定制，"
           "过道再窄也能放得下。高度同样可以调节，站着办公或坐着用餐都舒服。"
           "岩板表面耐刮耐热，泼了水一擦就干净。滑轮带有锁定，拉出后固定不晃动，用起来更安心。"
           "总之，这台小岛台让日常生活方便了许多。"),
}

# local manifest has transcripts; read prompt texts for reference segments
LOCAL = json.loads((Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001") /
                    "vc0_local_manifest.json").read_text(encoding="utf-8"))
SEG_PROMPT = {s["segment_id"]: s["transcript"] for s in LOCAL["segments"]}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def post_gsv(text, ref_id):
    payload = {"text": text, "text_lang": "zh",
               "ref_audio_path": str(SEG / f"{ref_id}.wav"),
               "prompt_text": SEG_PROMPT.get(ref_id, ""),
               "prompt_lang": "zh", "top_k": 15, "top_p": 1.0,
               "temperature": 1.0, "text_split_method": "cut5",
               "batch_size": 1, "media_type": "wav",
               "streaming_mode": False, "seed": 42, "speed_factor": 1.0}
    req = urllib.request.Request(GSV, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = resp.read()
    return data, round(time.time() - t0, 1)


def synth_melo(text, out):
    from treecut.platform.paths import RuntimePaths
    from treecut.models.tts_local import synthesize
    paths = RuntimePaths.discover()
    t0 = time.time()
    synthesize(text, out, paths.models / "LocalTTS")
    return round(time.time() - t0, 1)


def loudnorm_eval(src, out):
    subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "24000", "-ac", "1", str(out)], check=True,
                   timeout=600)


def metrics(wav):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(wav), dtype="float32")
    dur = round(len(data) / sr, 3)
    peak = float(np.max(np.abs(data)))
    clip = float(np.mean(np.abs(data) >= 0.999))
    proc = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(wav), "-af",
                           "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                           "-f", "null", "-"], capture_output=True, timeout=300)
    err = proc.stderr.decode("utf-8", errors="replace")
    try:
        block = err[err.index("{"): err.rindex("}") + 1]
        d = json.loads(block)
        lufs = float(d.get("input_i", 0))
        tp = float(d.get("input_tp", 0))
    except Exception:
        lufs = tp = None
    return {"duration_s": dur, "lufs": lufs, "true_peak_dbtp": tp,
            "clipping_ratio": round(clip, 6), "peak": round(peak, 5)}


def asr_text(wav):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(Path(r"E:\TreeCutRuntime\models\Whisper-small")),
                         device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(wav), language="zh", beam_size=5)
    return "".join(s.text for s in segs).strip()


def cer(ref, hyp):
    import numpy as np
    a, b = list(ref), list(hyp)
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        dp[i][0] = i
    for j in range(len(b) + 1):
        dp[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                           dp[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return round(dp[-1][-1] / max(len(a), 1), 4)


def main():
    jobs = []  # (text_id, text, backend, ref, out_raw)
    # GPT-SoVITS: T1..T5 with ref seg23; T1 extra ref seg13; T3 extra ref seg25
    for tid, txt in TEXTS.items():
        jobs.append((tid, txt, "gpt", "seg23"))
    jobs.append(("T1", TEXTS["T1"], "gpt", "seg13"))
    jobs.append(("T3", TEXTS["T3"], "gpt", "seg25"))
    for tid, txt in TEXTS.items():
        jobs.append((tid, txt, "melo", "seg23"))
    rows = []
    for tid, txt, backend, ref in jobs:
        raw = SAMPLES / f"RAW_{tid}_{backend}_ref{ref}.wav"
        if backend == "gpt":
            data, secs = post_gsv(txt, ref)
            raw.write_bytes(data)
            gen_s = secs
        else:
            gen_s = synth_melo(txt, raw)
        ev = SAMPLES / f"EVAL_{tid}_{backend}_ref{ref}.wav"
        loudnorm_eval(raw, ev)
        m_raw = metrics(raw)
        m_ev = metrics(ev)
        hyp = asr_text(raw)
        row = {"test": tid, "backend": backend, "ref": ref,
               "text": txt, "text_sha256": hashlib.sha256(
                   txt.encode()).hexdigest(),
               "raw_sha256": sha256_file(raw), "eval_sha256": sha256_file(ev),
               "gen_seconds": gen_s, "raw": m_raw, "eval": m_ev,
               "asr_hyp": hyp, "cer": cer(txt, hyp)}
        rows.append(row)
        print("done", tid, backend, ref, m_raw["duration_s"],
              "cer", row["cer"])
    metrics_out = {"experiment": "TREECUT_VC1_SAMPLE_METRICS",
                   "eval_target": "integrated -16 LUFS, true peak <= -1.5 dBTP, "
                                  "24000Hz mono",
                   "rows": rows}
    (REPO_STORAGE / "TREECUT_VC1_SAMPLE_METRICS.json").write_text(
        json.dumps(metrics_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("metrics written rows", len(rows))


if __name__ == "__main__":
    main()
