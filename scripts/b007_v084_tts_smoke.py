# -*- coding: utf-8 -*-
"""V0.8.4 — TTS/SRT 冒烟：3 档中文脚本 + 30s 冒烟 + 校验。用法: --fast 只跑 SHORT。"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.output.production_narration import ProductionNarrationAdapter, validate_srt

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
WORK = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\tts_smoke")
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

SCRIPTS = {
    "SHORT": "这个岛台宽度做了一米二，台面用的岩板，耐刮又耐高温，抽屉做了静音滑轨。",
    "MEDIUM": ("岛台装修有几个关键尺寸一定要记住。高度做到九十五公分，站着切菜不弯腰；"
               "台面长度建议两米到两米四，宽度六十公分左右，收纳和操作都方便。"
               "台下可以做大抽屉，放锅具和杂物，取用顺手。水槽建议放在靠墙一侧，"
               "管线更好隐藏。整体配色尽量和橱柜统一，厨房看起来才整洁。"),
    "LONG": ("很多业主做岛台最担心水电怎么预留。我们总结了几个要点，照着做基本不翻车。"
             "第一，插座要留够，台面下方至少两组，方便以后用电器；岛台侧面留一个升降插座，"
             "吃火锅或者办公都方便。第二，水槽位置要先定好，冷热水管和下水要提前预埋，"
             "千万不要等台面装好再改，返工成本很高。第三，如果要做伸缩岛台，"
             "导轨和五金一定要选承重好的，展开后承重超过两百公斤才稳。第四，灯光也很重要，"
             "吊灯或者筒灯要提前预留线路，灯光一开，整个岛台的质感就出来了。"
             "最后提醒一句，收纳抽屉的深度和内部格局要按自己家的餐具尺寸来设计，"
             "不然装了也用不上。做好这几个细节，岛台既好看又实用。"),
    "SMOKE30S": ("这台两米四的伸缩岛台，拉开以后能坐八个人。岩板台面耐刮耐高温，"
                 "平时切菜、吃饭、办公都在这里。台下的大抽屉做了静音滑轨，"
                 "锅碗瓢盆全都能收进去。侧面还预留了升降插座，吃火锅很方便。"
                 "岛台底部做了感应灯，晚上起夜不用摸黑。整体配色和橱柜统一，"
                 "厨房显得又大又整洁。"),
}

ADAPTER = None


def validate(art, label: str, scripts: dict) -> dict:
    checks = {}
    if art.status == "NARRATION_READY":
        checks["wav_exists"] = art.wav and art.wav.exists()
        checks["wav_size_gt0"] = bool(art.wav and art.wav.stat().st_size > 0)
        checks["audio_duration_gt2"] = art.audio_duration > 2.0
        # full decode
        try:
            dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(art.wav), "-f", "null", "-"],
                                 capture_output=True, timeout=120)
            checks["full_decode"] = dec.returncode == 0
        except Exception:
            checks["full_decode"] = False
        checks["chars_per_second"] = art.chars_per_second
        checks["duration_sanity"] = not (art.text_chars >= 100 and art.audio_duration < 5)
        srt_text = art.srt.read_text(encoding="utf-8") if art.srt else ""
        checks["srt_non_empty"] = bool(srt_text.strip())
        v = validate_srt(srt_text, art.audio_duration) if srt_text else {"blocks": 0, "errors": ["empty"]}
        checks["srt_blocks"] = v["blocks"]
        checks["srt_errors"] = v["errors"]
        checks["text_coverage"] = art.text_coverage
        checks["text_coverage_ok"] = art.text_coverage >= 0.95
        checks["all_pass"] = (checks["wav_exists"] and checks["wav_size_gt0"]
                              and checks["audio_duration_gt2"] and checks["full_decode"]
                              and checks["srt_non_empty"] and not v["errors"]
                              and checks["text_coverage_ok"] and checks["duration_sanity"])
    else:
        checks["all_pass"] = False
        checks["status"] = art.status
        checks["error"] = art.error
    return checks


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="只跑 SHORT")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    global ADAPTER
    ADAPTER = ProductionNarrationAdapter()
    WORK.mkdir(parents=True, exist_ok=True)
    labels = ["SHORT"] if args.fast else list(SCRIPTS)
    results = {}
    for label in labels:
        d = WORK / label
        d.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        art = ADAPTER.generate(SCRIPTS[label], d)
        secs = round(time.time() - t0, 1)
        checks = validate(art, label, SCRIPTS)
        results[label] = {"text_chars": len(SCRIPTS[label]),
                          "audio_duration_s": art.audio_duration,
                          "chars_per_second": art.chars_per_second,
                          "backend": art.backend, "voice": art.voice,
                          "subtitle_count": art.subtitle_count,
                          "text_coverage": art.text_coverage,
                          "status": art.status, "checks": checks,
                          "elapsed_s": secs,
                          "wav": str(art.wav) if art.wav else None,
                          "srt": str(art.srt) if art.srt else None,
                          "metadata": art.to_dict()}
        print(f"[{label}] chars={len(SCRIPTS[label])} dur={art.audio_duration}s "
              f"cps={art.chars_per_second} status={art.status} checks_pass={checks.get('all_pass')} "
              f"coverage={art.text_coverage} ({secs}s)")
    (OUT / "TREECUT_TTS_SMOKE_RESULTS_V1.json").write_text(
        json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    allpass = all(r["checks"].get("all_pass") for r in results.values() if r["status"] == "NARRATION_READY")
    print(json.dumps({"all_pass": allpass,
                      "statuses": {k: v["status"] for k, v in results.items()}}, ensure_ascii=False))
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
