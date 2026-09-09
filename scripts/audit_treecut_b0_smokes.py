# -*- coding: utf-8 -*-
"""TREECUT B0 — default-path smokes on the E install (no manual env).

1. DEFAULT_PATH_RESOLUTION: RuntimePaths.discover() with TREECUT_MODEL_ROOT unset
   must resolve to the permanent ASCII model root via the local pointer file.
2. Model discovery smoke: expected model dirs present under resolved root.
3. TTS_SMOKE: LocalTTS one Chinese sentence -> wav (sha256/duration).
No 30-minute E2E in this task.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
PERMANENT = Path(r"E:\TreeCutRuntime\models")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
WAV = Path(r"E:\EchoBird-main\_treecut_audit_temp\b0_tts_smoke.wav")

sys.path.insert(0, str(E_SRC))
sys.stdout.reconfigure(encoding="utf-8")
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DATA_ROOT", None)
EXPECTED_DIRS = ["BGE-M3", "Chinese-CLIP-ViT-B-16", "Florence-2-base", "LocalTTS",
                 "Qwen3-VL-4B-Instruct-FP8", "SenseVoiceSmall", "Whisper-small"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    from treecut.platform.paths import RuntimePaths
    paths = RuntimePaths.discover()
    resolved = paths.models.resolve()
    result = {
        "experiment": "TREECUT_B0_SMOKES",
        "DEFAULT_PATH_RESOLUTION": {
            "resolved_models": str(resolved),
            "expected_permanent": str(PERMANENT.resolve()),
            "pass": resolved == PERMANENT.resolve(),
            "env_TREECUT_MODEL_ROOT_was_set": False,
            "pointer_used": (Path(paths.data_root) / "config" / "models_path.txt").is_file(),
        },
        "MODEL_DISCOVERY": {d: (resolved / d).is_dir() for d in EXPECTED_DIRS},
        "all_expected_dirs_present": all((resolved / d).is_dir() for d in EXPECTED_DIRS),
    }
    tts = {"pass": False}
    try:
        from treecut.models.tts_local import synthesize
        text = "小户型也能有实用岛台，伸缩设计兼顾办公、用餐和会客。"
        WAV.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        wav = synthesize(text, WAV, resolved / "LocalTTS")
        import wave
        with wave.open(str(wav), "rb") as wf:
            dur = round(wf.getnframes() / wf.getframerate(), 3)
            rate = wf.getframerate()
        tts = {"pass": True, "wav": str(wav), "size": wav.stat().st_size,
               "sha256": sha256_file(wav), "sample_rate": rate, "duration_s": dur,
               "seconds": round(time.time() - t0, 1)}
    except Exception as exc:  # noqa: BLE001
        tts["error"] = f"{type(exc).__name__}: {exc}"
    result["TTS_SMOKE"] = tts
    result["overall"] = (result["DEFAULT_PATH_RESOLUTION"]["pass"]
                         and result["all_expected_dirs_present"] and tts["pass"])
    (OUT / "TREECUT_B0_SMOKES.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
