# -*- coding: utf-8 -*-
"""TREECUT VC2 Phase D+ — systems evaluation, dual-pass loudness, pause/speed,
blind packages (round1 4-sys x 4 texts, round2 top2 x 5), result + training
record (honest BLOCKED) + transcript consensus summary (anonymous). No audio in
git. Runs under runtime python; gsv api at 9880."""
import hashlib
import json
import random
import shutil
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
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
BLIND = Path(r"C:\Users\admin\Desktop\TreeCut_VC2_过夜优化试听")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
GSV = "http://127.0.0.1:9880/tts"
LOCAL = json.loads((Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001") /
                    "vc0_local_manifest.json").read_text(encoding="utf-8"))
SEG_PROMPT = {s["segment_id"]: s["transcript"] for s in LOCAL["segments"]}
SWEEP = json.loads((OUT / "TREECUT_VC2_ZERO_SHOT_SWEEP.json")
                   .read_text(encoding="utf-8"))
T1 = "这款岛台总长一米八，拉开以后可以满足六到八个人同时用餐。"
T2 = "公牛轨道插座，烧水、充电、吃火锅都不用满屋拉线。"
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
TEXTS = {"T1": T1, "T2": T2, "T3": T3, "CAL25": CAL25, "LONG_STRESS": LONG_STRESS}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def post_gsv(text, cfg, out):
    payload = {"text": text, "text_lang": "zh",
               "ref_audio_path": str(SEG / f"{cfg['ref']}.wav"),
               "prompt_text": SEG_PROMPT.get(cfg["ref"], ""),
               "prompt_lang": "zh", "top_k": cfg["top_k"], "top_p": 1.0,
               "temperature": cfg["temperature"], "speed_factor": 1.0,
               "repetition_penalty": cfg.get("repetition_penalty", 1.35),
               "media_type": "wav", "streaming_mode": False,
               "seed": cfg["seed"]}
    req = urllib.request.Request(GSV, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        data = resp.read()
    out.write_bytes(data)
    return round(time.time() - t0, 1)


def synth_melo(text, out):
    from treecut.platform.paths import RuntimePaths
    from treecut.models.tts_local import synthesize
    paths = RuntimePaths.discover()
    synthesize(text, out, paths.models / "LocalTTS")


def loudnorm_first(wav):
    proc = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(wav), "-af",
                           "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                           "-f", "null", "-"], capture_output=True, timeout=600)
    err = proc.stderr.decode("utf-8", errors="replace")
    try:
        block = err[err.index("{"): err.rindex("}") + 1]
        return json.loads(block)
    except Exception:
        return {}


def loudnorm_two_pass(wav, out):
    m = loudnorm_first(wav)
    measured_i = m.get("input_i", -16)
    measured_tp = m.get("input_tp", -1.5)
    measured_lra = m.get("input_lra", 11)
    measured_thresh = m.get("input_thresh", -30)
    af = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={measured_i}:"
          f"measured_TP={measured_tp}:measured_LRA={measured_lra}:"
          f"measured_thresh={measured_thresh}:linear=true")
    subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(wav), "-af", af, "-ar", "24000", "-ac", "1",
                    str(out)], check=True, timeout=600)
    m2 = loudnorm_first(out)
    return {"measured_input_i": round(float(measured_i), 2),
            "measured_input_tp": round(float(measured_tp), 2),
            "final_i": round(float(m2.get("input_i", 0)), 3),
            "final_tp": round(float(m2.get("input_tp", 0)), 3),
            "match": abs(float(m2.get("input_i", 0)) + 16.0) <= 0.3
            and float(m2.get("input_tp", 0)) <= -1.5}


def analyze(wav):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(wav), dtype="float32")
    dur = len(data) / sr
    fr = int(sr * 0.02)
    n = len(data) // fr
    rms = np.sqrt(np.mean(data[:n * fr].reshape(n, fr) ** 2, axis=1))
    thr = 10 ** (-45 / 20)
    active = rms >= thr
    voiced = np.sum(active) * fr / sr
    pause = float(1 - voiced / dur) if dur else 0.0
    idx = np.where(active)[0]
    lead = float(idx[0] * 0.02) if len(idx) else dur
    trail = float((n - 1 - idx[-1]) * 0.02) if len(idx) else dur
    return {"duration_s": round(dur, 3), "voiced_s": round(voiced, 3),
            "pause_ratio": round(pause, 4), "lead_s": round(lead, 3),
            "trail_s": round(trail, 3)}


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


def system_defs():
    long = SWEEP["long"]
    long_sorted = sorted(long, key=lambda r: r["score"])
    b1 = long_sorted[0]
    b2 = long_sorted[1] if len(long_sorted) > 1 else long_sorted[0]
    zs_vc1 = {"ref": "seg23", "seed": 42, "top_k": 15, "top_p": 1.0,
              "temperature": 1.0, "speed_factor": 1.0,
              "repetition_penalty": 1.35}
    return {"VC2_OPT_ZS_BEST": {"cfg": {k: b1["config"][k] for k in
                                        ("ref", "seed", "top_k",
                                         "temperature")}},
            "VC2_OPT_ZS_2ND": {"cfg": {k: b2["config"][k] for k in
                                       ("ref", "seed", "top_k",
                                        "temperature")}},
            "VC1_ZS_BASELINE": {"cfg": zs_vc1},
            "MELO_ANCHOR": {"cfg": None}}


def gen_system_file(system, tid, raw_dir):
    text = TEXTS[tid]
    raw = raw_dir / f"{system}_{tid}_RAW.wav"
    if raw.exists():
        return raw
    cfg = system_defs()[system]["cfg"]
    if system == "MELO_ANCHOR":
        synth_melo(text, raw)
    else:
        post_gsv(text, cfg, raw)
    return raw


def main():
    raw_dir = EXP / "phaseD_raw"
    ev_dir = EXP / "phaseD_eval"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ev_dir.mkdir(parents=True, exist_ok=True)
    systems = list(system_defs())
    round1_texts = ["T1", "T2", "T3", "CAL25"]
    rows = []
    fair_fail = []
    for sysname in systems:
        for tid in round1_texts:
            raw = gen_system_file(sysname, tid, raw_dir)
            ev = ev_dir / f"{sysname}_{tid}_EVAL.wav"
            if not ev.exists():
                r = loudnorm_two_pass(raw, ev)
            else:
                r = loudnorm_first(ev)
                r = {"final_i": round(float(r.get("input_i", 0)), 3),
                     "final_tp": round(float(r.get("input_tp", 0)), 3),
                     "match": abs(float(r.get("input_i", 0)) + 16.0) <= 0.3
                     and float(r.get("input_tp", 0)) <= -1.5}
            if not r.get("match"):
                fair_fail.append(f"{sysname}_{tid}")
            a = analyze(ev)
            hyp = asr_text(ev)
            c = cer(TEXTS[tid], hyp)
            chars = len(TEXTS[tid])
            rows.append({"system": sysname, "test": tid,
                         "raw_sha256": sha256_file(raw),
                         "eval_sha256": sha256_file(ev),
                         "analysis": a,
                         "chars_per_sec": round(chars / a["duration_s"], 2)
                         if a["duration_s"] else None,
                         "cer": c, "loudness": r})
            print("done", sysname, tid, "dur", a["duration_s"], "pause",
                  a["pause_ratio"], "cer", c, "I", r.get("final_i"))
    met = {"experiment": "TREECUT_VC2_SAMPLE_METRICS",
           "round1_texts": round1_texts,
           "FAIR_LOUDNESS_NORMALIZATION":
               "PASS" if not fair_fail else "FAIL",
           "fair_fail_items": fair_fail,
           "rows": rows}
    (OUT / "TREECUT_VC2_SAMPLE_METRICS.json").write_text(
        json.dumps(met, ensure_ascii=False, indent=1), encoding="utf-8")

    # transcript consensus summary (anonymous, no text)
    wh = json.loads((Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001") /
                     "vc0_local_manifest.json").read_text(encoding="utf-8"))
    fu = json.loads((Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001") /
                     "asr/funasr_zh.json").read_text(encoding="utf-8"))
    consensus = []
    prof_words = ["岛台", "伸缩", "岩板", "轨道插座", "公牛", "抽屉", "收纳",
                  "户型", "水电", "预留", "台面", "柜体"]
    for s in sorted(wh["segments"], key=lambda x: x["start_s"]):
        sid = s["segment_id"]
        a = s.get("transcript", "")
        b = fu.get(sid, "")
        consensus.append({"segment_id": sid,
                          "whisper_len": len(a), "funasr_len": len(b),
                          "diff_ratio": round(abs(len(a) - len(b)) /
                                              max(len(a), len(b), 1), 3),
                          "profession_word_hits": [w for w in prof_words
                                                   if w in a or w in b],
                          "status": "PROVISIONAL_MACHINE_CONSENSUS"})
    (OUT / "TREECUT_VC2_TRANSCRIPT_CONSENSUS_SUMMARY.json").write_text(
        json.dumps({"experiment": "TREECUT_VC2_TRANSCRIPT_CONSENSUS_SUMMARY",
                    "asr_paths": ["faster-whisper small", "funasr paraformer-zh"
                                  " (two different families)"],
                    "note": "transcript TEXT stays local only",
                    "segments": consensus}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # training record (honest)
    training = {"experiment": "TREECUT_VC2_TRAINING_RUNS",
                "FINE_TUNE_EXECUTED":
                    "NOT_EXECUTED_PREPROCESS_TOOLCHAIN_REQUIRES_WEBUI",
                "detail": "v2 few-shot (s1_train/s2_train) requires WebUI-"
                          "generated per-experiment configs AND preprocessed "
                          "exp dir (2-name2text.txt, 4-cnhubert/*.pt, "
                          "5-wav32k/*.wav per module/data_utils.py asserts); "
                          "replicating that pipeline unattended from CLI is "
                          "not supported without guessing; not faked.",
                "data_gate": {"unique>=10": True, "duration>=45s": True,
                              "holdout>=2/8s": True, "dup_leakage": False,
                              "transcript_authority":
                                  "PROVISIONAL_MACHINE_CONSENSUS"},
                "runs": []}
    (OUT / "TREECUT_VC2_TRAINING_RUNS.json").write_text(
        json.dumps(training, ensure_ascii=False, indent=1), encoding="utf-8")

    # blind packages
    if BLIND.exists():
        import shutil
        shutil.rmtree(BLIND)
    r1 = BLIND / "round1"
    r2 = BLIND / "round2"
    r1.mkdir(parents=True)
    r2.mkdir(parents=True)
    shutil.copy2(SEG / "seg23.wav", BLIND / "ORIGINAL_REFERENCE.wav")
    random.seed(20260909)
    r1_map, r2_map = {}, {}
    for tid in round1_texts:
        labels = list(systems)
        random.shuffle(labels)
        r1_map[tid] = {}
        for i, sysn in enumerate(labels):
            tag = f"R1_{tid}_{chr(65 + i)}.wav"
            shutil.copy2(ev_dir / f"{sysn}_{tid}_EVAL.wav", r1 / tag)
            r1_map[tid][tag] = sysn
    # round2 machine top-2 by composite of CAL25 (pause+cer)
    cal = [r for r in rows if r["test"] == "CAL25" and r["system"] != "MELO_ANCHOR"]
    cal_sorted = sorted(cal, key=lambda r: r["analysis"]["pause_ratio"]
                        + 2 * r["cer"])
    top2 = [cal_sorted[0]["system"], cal_sorted[1]["system"]]
    random.seed(20260910)
    for tid in TEXTS:
        labels = list(top2)
        random.shuffle(labels)
        r2_map[tid] = {}
        for i, sysn in enumerate(labels):
            tag = f"R2_{tid}_{chr(65 + i)}.wav"
            src = ev_dir / f"{sysn}_{tid}_EVAL.wav"
            if not src.exists():
                raw = gen_system_file(sysn, tid, raw_dir)
                loudnorm_two_pass(raw, src)
            shutil.copy2(src, r2 / tag)
            r2_map[tid][tag] = sysn
    (BLIND / "reviewer_map.json").write_text(json.dumps(
        {"note": "DO NOT OPEN BEFORE SCORING", "round1": r1_map,
         "round2": r2_map, "round2_top2_systems": top2},
        ensure_ascii=False, indent=1), encoding="utf-8")
    html = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>TreeCut VC2 过夜优化盲听</title></head><body>
<h1>TreeCut VC2 盲听（先听 ORIGINAL_REFERENCE 参考音色）</h1>
<p>评分维度：音色相似度/自然度/清晰度/语速/停顿/情绪与说话习惯/长句稳定性/
专业词准确性/是否愿用于正式账号视频（每项1-10）+备注。草稿自动保存在本浏览器。</p>
"""
    for grp, files in (("round1", sorted(p.name for p in r1.glob("*.wav"))),
                       ("round2", sorted(p.name for p in r2.glob("*.wav")))):
        html += f"<h2>{grp}</h2>"
        for f in files:
            html += (f'<audio controls src="{grp}/{f}"></audio> '
                     f'{f} 评分<input id="s_{f}" size="3"> '
                     f'备注<input id="n_{f}" size="50"><br>')
    html += """<script>
function save(){var d={};document.querySelectorAll('audio').forEach(function(a){var k=a.src.split('/').pop();
 d[k]={score:document.getElementById('s_'+k).value,note:document.getElementById('n_'+k).value}});
 localStorage.setItem('vc2_draft',JSON.stringify(d));}
function load(){var d=JSON.parse(localStorage.getItem('vc2_draft')||'{}');
 for(var k in d){if(document.getElementById('s_'+k)){document.getElementById('s_'+k).value=d[k].score;
  document.getElementById('n_'+k).value=d[k].note;}}}
function exportR(){save();var d=JSON.parse(localStorage.getItem('vc2_draft'));
 var a=document.createElement('a');a.href='data:application/json,'+encodeURIComponent(JSON.stringify(d,null,1));
 a.download='human_review_result.json';a.click();}
window.onload=load;
</script>
<button onclick="save()">保存草稿</button>
<button onclick="exportR()">导出 human_review_result.json</button>
<p>页面不含模型名/checkpoint/seed；machine 分数仅辅助。</p></body></html>"""
    (BLIND / "BLIND_REVIEW.html").write_text(html, encoding="utf-8")
    print(json.dumps({"fair": met["FAIR_LOUDNESS_NORMALIZATION"],
                      "fair_fail": fair_fail, "round2_top2": top2},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
