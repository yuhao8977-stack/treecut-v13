# -*- coding: utf-8 -*-
"""TREECUT VC1-ZS — backend manifest (weights sha), blind package, result,
evidence index + report. No audio/git. Runs under any python."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

SAMPLES = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\samples")
SEG = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001\segments")
REPO = Path(r"C:\Users\admin\github\treecut-v13")
REPO_STORAGE = REPO / "reports" / "storage"
DOCS = REPO / "docs"
WEIGHTS = Path(r"E:\TreeCutRuntime\models\VoiceClone\GPT_SoVITS\repo")
ENV = Path(r"E:\TreeCutRuntime\voice_clone_envs\GPT_SoVITS")
BLIND = Path(r"C:\Users\admin\Desktop\TreeCut_VC1_ZS_试听")
FFMPEG = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffmpeg.exe")
GSV_SRC = ENV / "GPT-SoVITS"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def loudness(wav):
    proc = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(wav), "-af",
                           "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                           "-f", "null", "-"], capture_output=True, timeout=300)
    err = proc.stderr.decode("utf-8", errors="replace")
    try:
        block = err[err.index("{"): err.rindex("}") + 1]
        d = json.loads(block)
        return {"lufs": float(d.get("input_i", 0)),
                "tp": float(d.get("input_tp", 0))}
    except Exception:
        return {"lufs": None, "tp": None}


def main():
    # backend manifest
    commit = subprocess.run(["git", "-C", str(GSV_SRC), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    weight_shas = {}
    for p in sorted(WEIGHTS.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".pth", ".ckpt", ".bin"):
            weight_shas[str(p.relative_to(WEIGHTS))] = sha256_file(p)
    manifest = {
        "experiment": "TREECUT_VC1_BACKEND_MANIFEST",
        "official_repo_url": "https://github.com/RVC-Boss/GPT-SoVITS",
        "repo_commit": commit,
        "venv": str(ENV / "venv"),
        "code_license": "MIT (repo LICENSE)",
        "weight_license": "INTERNAL_TEST_ONLY_PENDING_COMMERCIAL_CONFIRM "
                          "(weights from HF mirror lj1995/GPT-SoVITS v2final; "
                          "commercial terms not verified)",
        "weight_source": "https://hf-mirror.com/lj1995/GPT-SoVITS (sparse git "
                         "clone, ssl verify off, git-lfs 3.7.1)",
        "weights_dir": str(WEIGHTS),
        "weight_file_sha256": weight_shas,
        "config": "E:\\EchoBird-main\\_treecut_audit_temp\\vc1_tts_infer.yaml "
                  "(v2 custom: cuda half, absolute paths)",
        "local_env_patches": [
            "jieba_fast shim package (jieba fallback; no py3.12 wheel)",
            "langsegmenter: fast_langdetect offline fallback -> zh",
            "api_v2.py: traceback logging on 400",
            "bert_path env -> bert-type tokenizer dir (vocab.txt) for g2pw",
            "requirements filtered: pyopenjtalk/jieba_fast/opencc source builds "
            "skipped; opencc binary wheel installed"],
        "gpu": "RTX 3050 6GB; is_half true",
    }
    (REPO_STORAGE / "TREECUT_VC1_BACKEND_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # blind package (local desktop)
    if BLIND.exists():
        shutil.rmtree(BLIND)
    BLIND.mkdir(parents=True)
    shutil.copy2(SEG / "seg23.wav", BLIND / "ORIGINAL_REFERENCE.wav")
    # fair A/B per test: EVAL normalized Melo vs GPT (both -16 LUFS target)
    groups = {"TEST_01": ("T1",), "TEST_02": ("T3",), "TEST_03": ("T5",)}
    import random
    random.seed(20260909)
    rev_map = {}
    for g, (tid,) in groups.items():
        m = SAMPLES / f"EVAL_{tid}_melo_refseg23.wav"
        gv = SAMPLES / f"EVAL_{tid}_gpt_refseg23.wav"
        order = ["melo", "gpt"]
        random.shuffle(order)
        lab = {}
        for i, b in enumerate(order):
            src = m if b == "melo" else gv
            tag = f"{g}_SAMPLE_{'A' if i == 0 else 'B'}.wav"
            shutil.copy2(src, BLIND / tag)
            lab[tag] = b
        rev_map[g] = lab
    (BLIND / "reviewer_map.json").write_text(
        json.dumps({"seed": 20260909, "groups": rev_map,
                    "note": "do not open before scoring"}, ensure_ascii=False,
                   indent=1), encoding="utf-8")
    samples = sorted(p.name for p in BLIND.iterdir()
                     if p.suffix == ".wav" and p.name != "ORIGINAL_REFERENCE.wav")
    html = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>TreeCut VC1-ZS 盲听评审（匿名）</title></head><body>
<h1>TreeCut VC1-ZS 零样本盲听（不显示模型名）</h1>
<p>ORIGINAL_REFERENCE.wav = 目标参考音色（不参与匿名评分）。</p>
<p>每组听两个样本后评分：音色相似度 / 自然度 / 清晰度 / 情绪语气 /
长句稳定性 / 数字与岛台专业词准确性 / 是否愿意用于商业视频 / 具体问题备注。</p>
"""
    for g in groups:
        html += f"<h2>{g}</h2>"
        for tag in [f"{g}_SAMPLE_A.wav", f"{g}_SAMPLE_B.wav"]:
            html += (f'<audio controls src="{tag}"></audio><br>\n'
                     f'{tag} 评分:<input size="3"> 备注:<input size="40"><br>')
    html += '<p>完成后把评分填回并另存 reviewer 结果。机器指标仅辅助，以人耳为准。</p></body></html>'
    (BLIND / "BLIND_REVIEW.html").write_text(html, encoding="utf-8")

    met = json.loads((REPO_STORAGE / "TREECUT_VC1_SAMPLE_METRICS.json")
                     .read_text(encoding="utf-8"))
    eval_stats = {}
    for r in met["rows"]:
        key = f"{r['test']}_{r['backend']}_{r['ref']}"
        eval_stats[key] = loudness(SAMPLES / f"EVAL_{r['test']}_{r['backend']}"
                                   f"_ref{r['ref']}.wav")
    ev = {"fair_loudness_check": eval_stats}
    met["fair_loudness_check"] = eval_stats
    (REPO_STORAGE / "TREECUT_VC1_SAMPLE_METRICS.json").write_text(
        json.dumps(met, ensure_ascii=False, indent=1), encoding="utf-8")

    result = {
        "experiment": "TREECUT_VC1_RESULT",
        "REFERENCE_REVIEW_COMPLETED": "NO",
        "SINGLE_SPEAKER_HUMAN_CONFIRMED": "NO_PENDING_REVIEW_PAGE",
        "VERIFIED_REFERENCE_COUNT": 0,
        "GPT_SOVITS_INSTALLED": "YES",
        "CODE_LICENSE_STATUS": "MIT",
        "WEIGHT_LICENSE_STATUS": "INTERNAL_TEST_ONLY_PENDING_COMMERCIAL_CONFIRM",
        "ZERO_SHOT_GENERATED": "YES",
        "FAIR_LOUDNESS_NORMALIZATION": "YES (EVAL target -16 LUFS / <=-1.5 dBTP; "
                                       "measured values in sample metrics)",
        "ZERO_SHOT_PASS": "PENDING_HUMAN_BLIND_REVIEW",
        "HUMAN_BLIND_REVIEW_STATUS": "AWAITING",
        "FINE_TUNE_NEEDED": "PENDING_DECISION",
        "FINE_TUNE_ALLOWED": "NO",
        "PRODUCTION_INTEGRATION_ALLOWED": "NO",
        "TREECUT_TTS_REPLACED": "NO",
        "generated_count": len(met["rows"]),
        "NEXT_BLOCKER": "human blind review of Desktop\\TreeCut_VC1_ZS_试听 "
                        "(A/B groups) -> decide zero-shot pass / fine-tune VC2",
        "blind_package": str(BLIND),
    }
    (REPO_STORAGE / "TREECUT_VC1_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    idx_entries = []
    for f in sorted(REPO_STORAGE.glob("TREECUT_VC1_*.json")):
        idx_entries.append({"path": f.name, "sha256": sha256_file(f)})
    idx = {"experiment": "TREECUT_VC1_EVIDENCE_INDEX", "count": len(idx_entries),
           "entries": idx_entries}
    (REPO_STORAGE / "TREECUT_VC1_EVIDENCE_INDEX.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
