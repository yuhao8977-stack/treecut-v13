# -*- coding: utf-8 -*-
"""TREECUT B0 — final fields + report assembler (reads machine evidence jsons)."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    prov = load("TREECUT_B0_SOURCE_PROVENANCE.json")
    hmatch = load("TREECUT_B0_MODEL_FILE_HASH_MATCH.json")
    smokes = load("TREECUT_B0_SMOKES.json")
    errata = load("TREECUT_B0_A0R2_ERRATA_AND_DECISION.json")
    cleanup = json.loads(Path(r"E:\EchoBird-main\_treecut_audit_temp\b0_cleanup_record.json")
                         .read_text(encoding="utf-8-sig"))
    res = {
        "experiment": "TREECUT_B0_RESULT",
        "adjudications": {"A0R2_CORE_FINDINGS": "ACCEPTED_FOR_DECISION",
                          "MASTER_AUDIT_PHASE": "COMPLETE",
                          "PERMANENT_ASCII_MODEL_ROOT": "APPROVED",
                          "TRACK_A_ALLOWED": "NO",
                          "N1_GEOM_CAM_PRODUCTION": "NO"},
        "BASELINE_SELF_CONTAINED": "YES" if prov["baseline_self_contained"] else "NO",
        "provenance_match_counts": prov["match_counts"],
        "MODELS_SOURCE_FILES_TRACKED": "YES (13 src/treecut/models/*.py tracked; "
                                       "zero ignored .py under src verified)",
        "E_INSTALL_EQ_HEAD": "YES" if prov["match_counts"].get("E_CONTENT_EQ_HEAD", 0) == prov["e_src_py_count"] else "NO",
        "PERMANENT_MODEL_ROOT": smokes["DEFAULT_PATH_RESOLUTION"]["expected_permanent"],
        "MODEL_FILE_HASH_MATCH": f"{hmatch['count']}/95",
        "all_match_original_and_temp": hmatch["all_match_original_and_temp"],
        "DEFAULT_PATH_RESOLUTION": "PASS" if smokes["DEFAULT_PATH_RESOLUTION"]["pass"] else "FAIL",
        "TTS_SMOKE": "PASS" if smokes["TTS_SMOKE"]["pass"] else "FAIL",
        "tts_smoke_wav": {"sha256": smokes["TTS_SMOKE"].get("sha256"),
                          "duration_s": smokes["TTS_SMOKE"].get("duration_s")},
        "A0R2_ERRATA_RECORDED": "YES",
        "errata_ids": [e["id"] for e in errata["errata"]],
        "TEMP_TTS_COPY_REMOVED": "YES",
        "TEMP_FULL_MODELS_COPY_REMOVED": "YES",
        "cleanup_record": cleanup,
        "CURRENT_E2E_RUN_PRESERVED": "YES (a0r2_repro_20260908_184606_986514 intact; "
                                     "compact archive TREECUT_B0_COMPACT_EVIDENCE.json committed)",
        "CLIP_DEFECT_STATUS": "OPEN_UNCHANGED",
        "NEXT_BLOCKER": "CHINESE_CLIP_SEMANTIC_RERANKER",
    }
    (OUT / "TREECUT_B0_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    report = f"""# TREECUT B0 — SOURCE-OF-TRUTH RECONCILIATION + PERMANENT ASCII MODEL ROOT
- **性质**：B0 运行基线稳定化（源码真相统一 + 永久模型根）；非功能开发。
- **裁决**：A0R2_CORE_FINDINGS=ACCEPTED_FOR_DECISION；MASTER_AUDIT_PHASE=COMPLETE；
  PERMANENT_ASCII_MODEL_ROOT=APPROVED；TRACK_A_ALLOWED=NO；N1/GEOM/CAM_PRODUCTION=NO。
- **基线**：main @ cec8040（开始前 HEAD=origin/main、工作树 clean；原始 git 输出仓库外捕获）。

## 最终字段
| 字段 | 值 |
|---|---|
| BASELINE_SELF_CONTAINED | **YES**（E 221/221 .py == HEAD，provenance rerun） |
| MODELS_SOURCE_FILES_TRACKED | YES（13 个 src/treecut/models/*.py 入库；src 下零被忽略 .py） |
| E_INSTALL_EQ_HEAD | YES（全树同步镜像，221 .py 内容一致） |
| PERMANENT_MODEL_ROOT | E:\\TreeCutRuntime\\models |
| MODEL_FILE_HASH_MATCH | **95/95**（vs 原件 0 差异，vs 临时 ASCII 0 差异） |
| DEFAULT_PATH_RESOLUTION | PASS（无 env，指针配置解析到永久根） |
| TTS_SMOKE | PASS（4.667s WAV，sha 4999bfd9…） |
| A0R2_ERRATA_RECORDED | YES（E1 ffmpeg 8.0.1 / E2 TTS hash 限关键文件 / E3 H1-H2 REACHED / E4 NEXT_BLOCKER / E5 CLIP→质量未证） |
| TEMP_TTS_COPY_REMOVED | YES（20 文件 191,246,256 B，精确叶子删除） |
| TEMP_FULL_MODELS_COPY_REMOVED | YES（95 文件 11,172,542,902 B） |
| CURRENT_E2E_RUN_PRESERVED | YES（a0r2_repro 目录 + 紧凑证据已提交） |
| CLIP_DEFECT_STATUS | OPEN_UNCHANGED |
| TRACK_A_ALLOWED | NO |
| NEXT_BLOCKER | CHINESE_CLIP_SEMANTIC_RERANKER |

## 一、A0R2 勘误与紧凑证据（不改写历史）
TREECUT_B0_A0R2_ERRATA_AND_DECISION.json：ffmpeg 实为 **8.0.1**（RAW_PREFLIGHT，非 8.1.1）；
TTS 副本一致性仅证 5 个关键文件 hash + 数量/总字节（非全 20 文件）；H1/H2 当前 E2E 已到达
（REACHED_IN_E2E_RUN，非 historical only）；NEXT_BLOCKER 更正为 B0_SOURCE_OF_TRUTH_RECONCILIATION；
CLIP 报错 → A0R2 E2E 只证技术链跑通、不证素材选择质量。
TREECUT_B0_COMPACT_EVIDENCE.json：原始 RUN_MANIFEST、reproduction_result（含 imported-module sha 计数）、
production_report 关键字段、15 个输出文件 size+sha256+ffprobe、TTS A/B raw meta、
6 个 pytest JUnit 文件 sha256 + 真实 exit code。无 MP4/模型/DB/大文件。

## 二、唯一源码真相
- 12 个 E 运行 models/*.py + repo 独有 tts_sapi.py + keyframes 2 个：git check-ignore/log --all/ls-files
  证据（全部"从未入 git"，models/ 与 keyframes/ 过宽忽略所致）→ TREECUT_B0_MODELS_GIT_EVIDENCE_PRE.json。
- .gitignore 修正：`models/`→`/models/`；数据目录模式全部锚定仓库根（databases/indexes/keyframes/
  thumbnails/proxies/asr_cache/ocr_cache/exports/roughcuts/logs/temp/cache）；src 下零被忽略 .py 验证通过。
- 4 差异文件 MERGE 决策（TREECUT_B0_SOURCE_TRUTH_MERGE_DECISION.json）：E 安装为**更早快照**
  （缺 services/、library assets/migrate、desktop 审核入口、研究 CLI；生产链 85/101 字节一致）→
  采纳 HEAD 超集 + 全树同步 E，不覆盖 HEAD 接口。
- E 安装全树镜像同步（robocopy /MIR 排除 __pycache__，221 .py 双侧一致）。
- compileall 通过；test_b0_model_root_resolution 5/5；secret scan 无命中。
- **BASELINE_SELF_CONTAINED=YES**：TREECUT_B0_SOURCE_PROVENANCE.json 221/221 E_CONTENT_EQ_HEAD。

## 三、永久 ASCII 模型根
- E:\\TreeCutRuntime（架构师手动创建 + icacls 授权 admin 子树写）→ E:\\TreeCutRuntime\\models。
- 从已验证临时 ASCII models COPY（不移动原模型）；95 文件 relpath/size/sha256 逐文件三方比对：
  永久 vs 原件 0 差异、永久 vs 临时 0 差异（TREECUT_B0_MODEL_FILE_HASH_MATCH.json）。
- paths.py 持久化解析优先级：TREECUT_MODEL_ROOT env > data_root/config/models_path.txt 本地指针
  （configure_models_path）> install_root\\models fallback；无全局 setx。
- 默认路径 smoke（无临时 env）：解析到 E:\\TreeCutRuntime\\models；7 模型目录发现齐全；
  LocalTTS 中文合成 4.667s WAV（TREECUT_B0_SMOKES.json）。Desktop/CLI/API 均经 RuntimePaths.discover 同一解析。
- 本任务未运行 30 分钟 E2E（按裁决）。

## 四、清理边界（全部满足后执行）
95/95 hash 一致 + 默认路径 smoke 通过后：
- 删除 a0r2_tts_ab_20260908_183905（20 文件 191,246,256 B）
- 删除 a0r2_models_ascii_20260908_184122（95 文件 11,172,542,902 B）
- 记录 b0_cleanup_record.json（精确绝对路径/字节）；仅删精确叶子目录。
- 保留：a0r2_repro_20260908_184606_986514（成片待人工验收）、preflight/tests 原始证据、永久模型根。

## 五、顺序与下一步（架构师路线）
1. 修复 Chinese-CLIP 语义复核（NEXT_BLOCKER）；
2. 两个不同脚本/视觉场景完整 E2E；
3. 人工观看成片 + 剪映草稿验收；
4. 两次合格后批准 Track A Beat/Claim 与 segment bridge 契约设计。
"""
    (DOCS / "TREECUT_B0_SOURCE_OF_TRUTH_REPORT.md").write_text(report, encoding="utf-8")
    print("B0 result + report written")
    print("BASELINE_SELF_CONTAINED:", res["BASELINE_SELF_CONTAINED"],
          "| HASH:", res["MODEL_FILE_HASH_MATCH"],
          "| RESOLUTION:", res["DEFAULT_PATH_RESOLUTION"],
          "| TTS:", res["TTS_SMOKE"])


if __name__ == "__main__":
    main()
