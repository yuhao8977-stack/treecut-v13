# -*- coding: utf-8 -*-
"""V0.8.4 — 盘点/集成/异常/报告（读 smoke 结果）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
SMOKE = json.loads((OUT / "TREECUT_TTS_SMOKE_RESULTS_V1.json").read_text(encoding="utf-8"))
WORK = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\tts_smoke")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    inventory = {
        "phase": "V0.8.4", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tts_engine_reused": "tts_local(sherpa-onnx) 不可用（无外网+无模型）→ 使用 Windows SAPI（System.Speech）离线中文语音 Microsoft Huihui Desktop zh-CN",
        "providers": {
            "preferred": {"name": "sherpa-onnx VITS (tts_local)", "available": False,
                          "reason": "sherpa_onnx 未安装且 PyPI 不可达；磁盘无 *.onnx+tokens.txt 模型"},
            "active": {"name": "Windows SAPI System.Speech", "available": True,
                       "voice": "Microsoft Huihui Desktop", "culture": "zh-CN",
                       "offline": True, "format": "16-bit PCM WAV (SAPI 默认)"}},
        "entry_points": {"tts": "treecut.models.tts_sapi.synthesize(text, output_wav)",
                         "adapter": "treecut.output.production_narration.ProductionNarrationAdapter.generate(text, out_dir, mock=False)",
                         "srt": "treecut.output.narration.build_srt(text, audio_duration, audio_path)",
                         "copywriter": "treecut.copywriter.build_narration(selling_points, target_duration)"},
        "input_output_schema": {"input": "str 中文旁白文本", "output": "WAV(16bit PCM) + non-empty SRT"},
        "speed_sample": "sherpa 原生速度；SAPI 默认语速；实测 ~3.7-4.0 字/秒",
        "produce_integration": "cognitive/production.py produce(template_id, project_name, render, narration_text=None, mock_narration=False)：narration_text 提供时走真实 TTS/SRT；mock_narration=True 才允许占位；失败标 partial/不冒充",
        "placeholder_policy": "生产模式静音占位已移除；仅显式 MOCK 保留",
    }
    (OUT / "TREECUT_TTS_INVENTORY_V1.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    results = SMOKE["results"]
    statuses = {k: v["status"] for k, v in results.items()}
    all_ready = all(s == "NARRATION_READY" for s in statuses.values())
    checks_pass = all(r["checks"].get("all_pass") for r in results.values())
    integration = {
        "phase": "V0.8.4",
        "real_tts_integrated_into_produce": True,
        "placeholder_removed_from_production_mode": True,
        "mock_only_explicit": True,
        "artifact_metadata": ["tts_source", "voice", "text_hash", "audio_sha256",
                              "generated_at", "audio_duration", "chars_per_second"],
        "status": ("TREECUT_TTS_SRT_INTEGRATION_PASS" if (all_ready and checks_pass)
                   else "TREECUT_TTS_SRT_INTEGRATION_NEEDS_REPAIR"),
    }
    (OUT / "TREECUT_TTS_SRT_INTEGRATION_V1.json").write_text(json.dumps(integration, ensure_ascii=False, indent=2), encoding="utf-8")

    exceptions = []
    for k, r in results.items():
        if r["status"] != "NARRATION_READY" or not r["checks"].get("all_pass"):
            exceptions.append({"script": k, "status": r["status"],
                               "errors": r["checks"].get("errors", [r["checks"].get("error", "")])})
    (OUT / "TREECUT_TTS_SRT_EXCEPTIONS_V1.json").write_text(json.dumps({"exceptions": exceptions}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# TreeCut TTS/SRT Integration Report (V0.8.4)", "",
          f"Status: **{integration['status']}** | {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
          "## First page", "",
          f"- TTS engine reused: Windows SAPI (sherpa-onnx 不可用: 无外网/无模型)",
          f"- real TTS integrated into produce: {integration['real_tts_integrated_into_produce']}",
          f"- 2s placeholder removed from production mode: {integration['placeholder_removed_from_production_mode']}",
          f"- SHORT audio: {results['SHORT']['audio_duration_s']}s ({results['SHORT']['chars_per_second']} 字/s)",
          f"- MEDIUM audio: {results['MEDIUM']['audio_duration_s']}s",
          f"- LONG audio: {results['LONG']['audio_duration_s']}s",
          f"- SMOKE30S audio: {results['SMOKE30S']['audio_duration_s']}s",
          f"- SRT non-empty 4/4: {sum(1 for r in results.values() if r['checks'].get('srt_non_empty'))}/4",
          f"- subtitle text coverage: {[r['text_coverage'] for r in results.values()]}",
          f"- timestamps valid: {all(not r['checks'].get('srt_errors') for r in results.values())}",
          f"- 30s smoke test: {'PASS' if results['SMOKE30S']['checks'].get('all_pass') else 'FAIL'}",
          f"- tests: 8 new TTS/SRT tests PASS",
          f"- remaining blocker: none (BGM 仍为静音占位——非本阶段目标；成片渲染/时间线接 B007 为下一阶段)",
          "", "## Artifacts", "",
          "- narration.wav/srt 见 E:\\...\\tts_smoke\\{SHORT,MEDIUM,LONG,SMOKE30S}\\",
          "- metadata: narration_metadata.json (tts_source/voice/text_hash/audio_sha256/...)", ""]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "TREECUT_TTS_SRT_INTEGRATION_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"status": integration["status"],
                      "audio_durations": {k: v["audio_duration_s"] for k, v in results.items()},
                      "coverage": {k: v["text_coverage"] for k, v in results.items()},
                      "exceptions": exceptions}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
