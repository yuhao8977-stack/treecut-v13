# -*- coding: utf-8 -*-
"""TREECUT VC2 Phase B — bounded zero-shot parameter sweep (doc schema read,
no guessing): T1 short across refs x seeds x top_k x temperature; rank by
F0-median distance to ~183Hz, pause ratio toward ~0.11, ASR CER; top-8 middle
(T3); top-4 long (25s calibration + LONG_STRESS). Anonymous JSON."""
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
import os
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DATA_ROOT", None)
SEG = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\segments")
EXP = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\experiments\VC2_1")
SAMPLES = EXP / "sweep"
SAMPLES.mkdir(parents=True, exist_ok=True)
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
GSV = "http://127.0.0.1:9880/tts"
LOCAL = json.loads((Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001") /
                    "vc0_local_manifest.json").read_text(encoding="utf-8"))
SEG_PROMPT = {s["segment_id"]: s["transcript"] for s in LOCAL["segments"]}
T1 = "这款岛台总长一米八，拉开以后可以满足六到八个人同时用餐。"
T3 = "您家现在装修到哪个阶段了？水电位置有没有提前预留？"
CAL25 = ("小户型也能拥有实用岛台，平时收起来不占过道，需要时轻轻拉开，"
         "就能多出备餐和用餐空间。台面下方可以分区收纳，抽屉放常用小物，"
         "柜体放餐具。岩板耐刮耐热，日常一擦就干净。尺寸还能按户型定制，"
         "想了解适合您家的方案，可以把厨房尺寸发给我。")
LONG_STRESS = ("小户型也能拥有实用岛台。平时收起来不占过道，需要时轻轻拉出，"
               "立刻多出一张工作台。它既能当办公桌，也能招待朋友用餐，一物三用不浪费。"
               "台面下方做了分区收纳，抽屉放文具，柜门里放餐具。常用物品放在顺手的高度，"
               "拿取不用弯腰。边角都做了圆润处理，家里有小孩也不用担心磕碰。"
               "台面宽度可以按户型定制，过道再窄也能放得下。高度同样可以调节，"
               "站着办公或坐着用餐都舒服。岩板表面耐刮耐热，泼了水一擦就干净。"
               "滑轮带有锁定，拉出后固定不晃动，用起来更安心。总之，"
               "这台小岛台让日常生活方便了许多。")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def post(text, ref, params, name):
    payload = {"text": text, "text_lang": "zh",
               "ref_audio_path": str(SEG / f"{ref}.wav"),
               "prompt_text": SEG_PROMPT.get(ref, ""), "prompt_lang": "zh",
               **params, "media_type": "wav", "streaming_mode": False}
    req = urllib.request.Request(GSV, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = resp.read()
    p = SAMPLES / name
    p.write_bytes(data)
    return p, round(time.time() - t0, 1)


def analyze(wav, text):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(wav), dtype="float32")
    dur = len(data) / sr
    fr = int(sr * 0.02)
    n = len(data) // fr
    rms = np.sqrt(np.mean(data[:n * fr].reshape(n, fr) ** 2, axis=1))
    pause = float(np.mean(rms < 10 ** (-45 / 20)))
    f0s = []
    step = int(sr * 0.03)
    for st in range(0, len(data) - step, step):
        blk = data[st:st + step]
        if float(np.sqrt(np.mean(blk ** 2))) < 0.01:
            continue
        ac = np.correlate(blk - blk.mean(), blk - blk.mean(), "full")[len(blk) - 1:]
        lag = np.argmax(ac[80:int(sr / 60)]) + 80 if len(ac) > 80 else 0
        if lag > 0:
            f0 = sr / lag
            if 70 <= f0 <= 400:
                f0s.append(f0)
    f0med = float(np.median(f0s)) if f0s else None
    clip = float(np.mean(np.abs(data) >= 0.999))
    return {"duration_s": round(dur, 3), "pause_ratio": round(pause, 4),
            "f0_median_hz": round(f0med, 1) if f0med else None,
            "clipping": round(clip, 7)}


def asr_text(wav):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(Path(r"E:\TreeCutRuntime\models\Whisper-small")),
                         device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(wav), language="zh", beam_size=5)
    return "".join(s.text for s in segs).strip()


def cer(ref, hyp):
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


def run_round(label, text, configs, stage):
    rows = []
    for i, cfg in enumerate(configs):
        ref = cfg["ref"]
        name = f"{stage}_{label}_{i:02d}_r{ref}_s{cfg['seed']}_k{cfg['top_k']}_t{cfg['temperature']}.wav"
        wav, gen_s = post(text, ref, {k: cfg[k] for k in
                                      ("top_k", "top_p", "temperature",
                                       "seed", "speed_factor",
                                       "repetition_penalty")}, name)
        a = analyze(wav, text)
        hyp = asr_text(wav)
        c = cer(text, hyp)
        f0 = a["f0_median_hz"] or 183.0
        score = (0.4 * abs(f0 - 183.0) / 183.0 + 0.3 * max(0.0,
                 a["pause_ratio"] - 0.11) + 0.3 * c)
        rows.append({"candidate": name, "config": cfg, "ref": ref,
                     "sha256": sha256_file(wav), "metrics": a,
                     "cer": c, "gen_seconds": gen_s, "score": round(score, 4)})
        print("done", label, i, "score", round(score, 3), "dur", a["duration_s"],
              "pause", a["pause_ratio"], "f0", f0)
    rows.sort(key=lambda r: r["score"])
    return rows


def main():
    params_base = {"top_p": 1.0, "speed_factor": 1.0,
                   "repetition_penalty": 1.35}
    configs = []
    for ref in ("seg13", "seg23", "seg25", "seg27"):
        for seed in (1, 42):
            for top_k in (10, 15):
                for temp in (0.6, 1.0):
                    configs.append({"ref": ref, "seed": seed,
                                    "top_k": top_k, "top_p": 1.0,
                                    "temperature": temp,
                                    "speed_factor": 1.0,
                                    "repetition_penalty": 1.35})
    short = run_round("T1", T1, configs, "short")
    top8 = short[:8]
    mid_cfg = [{"ref": r["ref"], "seed": r["config"]["seed"],
                "top_k": r["config"]["top_k"], "top_p": 1.0,
                "temperature": r["config"]["temperature"],
                "speed_factor": r["config"]["speed_factor"],
                "repetition_penalty": r["config"]["repetition_penalty"]}
               for r in top8]
    mid = run_round("T3", T3, mid_cfg, "mid")
    top4 = mid[:4]
    long_cfg = [{"ref": r["ref"], "seed": r["config"]["seed"],
                 "top_k": r["config"]["top_k"], "top_p": 1.0,
                 "temperature": r["config"]["temperature"],
                 "speed_factor": r["config"]["speed_factor"],
                 "repetition_penalty": r["config"]["repetition_penalty"]}
                for r in top4]
    long = run_round("CAL25", CAL25, long_cfg, "long")
    longstress = run_round("LONG_STRESS", LONG_STRESS, long_cfg, "stress")
    sweep = {"experiment": "TREECUT_VC2_ZERO_SHOT_SWEEP",
             "method": "bounded staged: 32 short(T1) -> top8 mid(T3) -> "
                       "top4 long(CAL25 + LONG_STRESS)",
             "score_formula": "0.4*|f0-183|/183 + 0.3*max(0,pause-0.11) "
                              "+ 0.3*CER",
             "short": short, "mid": mid, "long": long,
             "long_stress": longstress,
             "best_overall_short": short[0] if short else None,
             "best_overall_mid": mid[0] if mid else None,
             "best_overall_long": long[0] if long else None}
    (OUT / "TREECUT_VC2_ZERO_SHOT_SWEEP.json").write_text(
        json.dumps(sweep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("sweep done short", len(short), "mid", len(mid), "long", len(long),
          "stress", len(longstress))


if __name__ == "__main__":
    main()
