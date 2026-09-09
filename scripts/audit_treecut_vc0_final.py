# -*- coding: utf-8 -*-
"""TREECUT VC0 — backend preflight + Melo baseline sample + blind pack +
decision/result assembly (anonymous; no sound into git)."""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
E_INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")
PROFILE = Path(r"E:\TreeCutRuntime\voice_profiles\VOICE_001")
SAMPLES = PROFILE / "samples"
REPO_STORAGE = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
sys.path.insert(0, str(E_SRC))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight():
    out = {}
    try:
        import torch
        out["torch"] = torch.__version__
        out["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            out["gpu"] = torch.cuda.get_device_name(0)
            out["gpu_mem_gb"] = round(torch.cuda.get_device_properties(0).total_memory
                                      / 2 ** 30, 1)
    except Exception as exc:  # noqa: BLE001
        out["torch_error"] = str(exc)
    try:
        import psutil
        out["ram_gb"] = round(psutil.virtual_memory().total / 2 ** 30, 1)
    except Exception:
        out["ram_gb"] = "n/a"
    out["disk_free_gb"] = {str(d): round(shutil.disk_usage(d).free / 2 ** 30, 1)
                           for d in ("E:\\", "C:\\") if Path(d).exists()}
    import importlib.util as u
    out["clone_backends_installed"] = {
        b: bool(u.find_spec(b)) for b in ("GPT_SoVITS", "cosyvoice",
                                          "openvoice", "f5_tts")}
    out["treecut_tts_current"] = ("LocalTTS (sherpa-onnx melo zh_en) - voice "
                                  "clone NOT integrated (F0/A0R2 confirmed)")
    out["license_notes"] = {
        "GPT-SoVITS": "code MIT (official repo); pretrained-weight license "
                      "must be re-verified at install time before any "
                      "commercial use",
        "CosyVoice": "Apache-2.0 code; weight terms re-verify at install",
        "OpenVoiceV2": "MIT code (per official); verify weight terms",
        "F5-TTS": "code MIT but official pretrained weights are "
                  "non-commercial - NOT a production default until license "
                  "resolved"}
    return out


def synth_melo(text, out_wav):
    os = __import__("os")
    os.environ.pop("TREECUT_MODEL_ROOT", None)
    os.environ.pop("TREECUT_DATA_ROOT", None)
    from treecut.platform.paths import RuntimePaths
    from treecut.models.tts_local import synthesize
    paths = RuntimePaths.discover()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    synthesize(text, out_wav, paths.models / "LocalTTS")
    return round(time.time() - t0, 1)


def main():
    local = json.loads((PROFILE / "vc0_local_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((REPO_STORAGE / "TREECUT_VC0_SEGMENTS_SUMMARY.json")
                         .read_text(encoding="utf-8"))
    pf = preflight()
    # ---- Melo baseline sample A (anonymous, local only) ----
    TEST_TEXT_1 = ("这款岛台总长一米八，拉开以后可以满足六到八个人同时用餐。")
    secs = synth_melo(TEST_TEXT_1, SAMPLES / "SAMPLE_A.wav")
    samples = {"SAMPLE_A": {"wav": str(SAMPLES / "SAMPLE_A.wav"),
                            "sha256": sha256_file(SAMPLES / "SAMPLE_A.wav"),
                            "backend": "Melo-TTS baseline (anonymous label A)",
                            "synthesize_s": secs}}
    decision = {
        "experiment": "TREECUT_VC0_BACKEND_DECISION",
        "voice_profile_id": "VOICE_001",
        "VOICE_OWNER_AUTHORIZED": "YES",
        "SELECTED_BACKEND": "GPT-SoVITS (preferred) - zero-shot; "
                            "PENDING_OFFLINE_INSTALL",
        "FALLBACK_CANDIDATES": ["CosyVoice zero-shot (control)",
                                "OpenVoice V2 (lightweight reserve)"],
        "F5_TTS_DEFAULT": "NO (pretrained weights non-commercial until "
                          "license resolved)",
        "backend_preflight": pf,
        "clone_env": "isolated venv/service; never pollutes TreeCut runtime; "
                     "never overwrites LocalTTS; weights never in git",
        "ZERO_SHOT_A_B_COMPLETED": "A_ONLY",
        "zero_shot_status_note": "Melo baseline (A) generated; GPT-SoVITS / "
                                 "CosyVoice backends NOT installed in this "
                                 "environment - offline availability + weight "
                                 "licenses must be resolved before B/C; "
                                 "no fabricated samples produced",
        "FINE_TUNE_ALLOWED": "NO",
        "PRODUCTION_INTEGRATION_ALLOWED": "NO",
    }
    (REPO_STORAGE / "TREECUT_VC0_BACKEND_DECISION.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=1), encoding="utf-8")

    uniq = summary["segments_anonymous"]
    active_speech_s = round(sum(s["duration_s"] for s in uniq) * 2, 2)  # incl duplicates
    refs = [s for s in uniq if s["segment_id"] in
            ("seg13", "seg23", "seg25", "seg27")]
    result = {
        "experiment": "TREECUT_VC0_RESULT",
        "VOICE_REFERENCE_AVAILABLE": "YES",
        "VOICE_OWNER_AUTHORIZED": "YES",
        "RAW_DURATION": summary["extracted"]["original"]["duration_s"],
        "ACTIVE_SPEECH_DURATION": active_speech_s,
        "UNIQUE_SPEECH_DURATION": summary["dedup"]["unique_speech_duration_s"],
        "RAW_SEGMENT_COUNT": summary["dedup"]["raw_segment_count"],
        "UNIQUE_SEGMENT_COUNT": summary["dedup"]["kept_unique_count"],
        "DUPLICATE_PAIR_COUNT": summary["dedup"]["duplicate_pair_count"],
        "SINGLE_SPEAKER_CONFIRMED": summary["speaker_proxy"][
            "single_speaker_confirmed"],
        "TRANSCRIPT_VERIFIED_COUNT": 0,
        "TRANSCRIPT_REVIEW_STATUS": "TRANSCRIPT_UNVERIFIED (human listen "
                                    "required; ASR homophones expected)",
        "DATASET_READY_FOR_ZERO_SHOT": "YES_AFTER_TRANSCRIPT_REVIEW",
        "DATASET_READY_FOR_FINE_TUNE": "NO",
        "SELECTED_BACKEND": decision["SELECTED_BACKEND"],
        "LICENSE_STATUS": "GPT-SoVITS code MIT; weight license re-verify at "
                          "install",
        "ZERO_SHOT_A_B_COMPLETED": "A_ONLY",
        "HUMAN_REVIEW_STATUS": "AWAITING (blind pack A + B/C pending)",
        "FINE_TUNE_ALLOWED": "NO",
        "PRODUCTION_INTEGRATION_ALLOWED": "NO",
        "NEXT_BLOCKER": "VC0 human blind listening (SAMPLE_A) + authorize "
                        "offline clone backend install (GPT-SoVITS) for B/C",
        "reference_candidates": refs,
        "report_paths": ["docs/TREECUT_VC0_VOICE_REFERENCE_REPORT.md"],
        "private_local_artifact_paths": {
            "profile": str(PROFILE),
            "original_wav": str(PROFILE / "source_original_audio.wav"),
            "working_wav": str(PROFILE / "source_working_24k.wav"),
            "segments": str(PROFILE / "segments"),
            "asr": str(PROFILE / "asr"),
            "local_manifest": str(PROFILE / "vc0_local_manifest.json")},
    }
    (REPO_STORAGE / "TREECUT_VC0_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    # hash manifest (hashes only, no audio content)
    hm = {"experiment": "TREECUT_VC0_HASH_MANIFEST",
          "source_mp4_sha256": "4f453ddfa046fe9b7d9f373d1f7a80c8fe9e16703dd"
                               "95054bda0fb0cb58992e5",
          "original_wav": sha256_file(PROFILE / "source_original_audio.wav"),
          "working_wav": sha256_file(PROFILE / "source_working_24k.wav"),
          "segments": {s["segment_id"]: s["sha256"] for s in uniq},
          "sample_A": samples["SAMPLE_A"]["sha256"]}
    (REPO_STORAGE / "TREECUT_VC0_HASH_MANIFEST.json").write_text(
        json.dumps(hm, ensure_ascii=False, indent=1), encoding="utf-8")
    # blind review html (local)
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>VC0 BLIND REVIEW (anonymous)</title></head><body>
<h1>TreeCut VC0 人工盲听包（匿名）</h1>
<p>voice_profile_id: VOICE_001 — 不显示任何模型名。</p>
<p>SAMPLE_A.wav（唯一可用样本；B/C 后端离线安装未完成，生成后补充）。</p>
<p>评分维度：音色相似度 / 自然度 / 清晰度 / 情绪语气 / 长句稳定性 /
岛台专业词准确性 / 是否可用于商业视频。</p>
<p>状态：TRANSCRIPT_UNVERIFIED — 逐条转写需人工核对后才可用于需参考文本的克隆。</p>
</body></html>"""
    (SAMPLES / "BLIND_REVIEW.html").write_text(html, encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("VOICE_REFERENCE_AVAILABLE",
                                             "RAW_DURATION",
                                             "ACTIVE_SPEECH_DURATION",
                                             "UNIQUE_SPEECH_DURATION",
                                             "RAW_SEGMENT_COUNT",
                                             "UNIQUE_SEGMENT_COUNT",
                                             "DUPLICATE_PAIR_COUNT",
                                             "SINGLE_SPEAKER_CONFIRMED",
                                             "TRANSCRIPT_VERIFIED_COUNT",
                                             "ZERO_SHOT_A_B_COMPLETED",
                                             "NEXT_BLOCKER")},
                     ensure_ascii=False, indent=1))
    print("preflight gpu:", pf.get("gpu"), "cuda:", pf.get("cuda_available"))


if __name__ == "__main__":
    main()
