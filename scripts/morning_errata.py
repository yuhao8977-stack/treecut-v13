# -*- coding: utf-8 -*-
"""主报告勘误(校准口径) + 状态矩阵冻结 + 提交准备。"""
import json, shutil, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
DESK = Path(r"C:\Users\admin\Desktop")
now = time.strftime("%Y-%m-%d %H:%M:%S")
errata = f"""
## 晨间勘误（{now}）— 校准口径与状态冻结（架构师裁定）

- **校准口径纠正**：G2 校准目标 = 80–120 **Segment/资产级**独立样本。当前真值：segment/asset 级 ≈ **20**，未达标；132 时序帧为 **TEMPORAL_EVIDENCE**（同一样本看得更细），**不等价 132 独立样本**。凡此前表述"帧级132满足80-120指导"一律作废（本文件与相关产物已改）。
- 校准扩充计划（cheap signals 先行，qwen 仅难例/人审子集）已写入 `TREECUT_G2_SEGMENT_CALIBRATION_STATUS_V2.json`。
- **状态矩阵冻结（架构师）**：G1=PASS ｜ G2/G3=ENGINEERING_READY_FOR_HUMAN_VALIDATION ｜ Dedup/G5=PROVISIONAL_PASS ｜ UI=USABLE_V1 ｜ VOICE=READY_FOR_INPUT ｜ BGM=LIBRARY_NOT_READY ｜ Regression=354/2/0
- 晨间人审包：`TREECUT_G2_HUMAN_REVIEW_V2.html`(20 queries×Top3+best+complete+boundary)、`TREECUT_G3_HUMAN_REVIEW_V2.html`(16 beats)、`TREECUT_DEDUP_HUMAN_REVIEW_V1.html`(真实 V2 镜头 4 对)；标记可导出 JSON（追加式，不动机器证据）。
- **G2 人审阶段门槛（第一阶段生产可用，非普适真理）**：已知硬负拒绝 100% / Top3 含可用动作 ≥85% / Top1 可用 ≥70% / 边界可用 ≥80%；分母=确实存在目标动作素材的 Query；无素材=NO_VALID_SOURCE_AVAILABLE，不算算法失败。
- **G3 门槛**：P0 核心主张错配 0 / Top3 含合适 ≥90% / Top1 合适 ≥80% / 无支撑核心主张通过 0 / 严重 SINGLE_CASE 故事冲突 0。
"""
for f in (OUT / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md", DOCS / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md"):
    open(f, "a", encoding="utf-8").write(errata)
shutil.copy2(DOCS / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md", DESK / "TREECUT_STAGE8_OVERNIGHT_HARDENING_V2.md")

f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["stage8_gates"] = d.get("stage8_gates", {})
d["stage8_gates"]["G2_ACTION_SUBCLIP"] = {"status": "ENGINEERING_READY_FOR_HUMAN_VALIDATION",
                                          "calibration_segment_level": 20, "target": "80-120",
                                          "calibration_met": False,
                                          "temporal_evidence_frames": 132,
                                          "frames_not_samples": True}
d["stage8_gates"]["G3_CLAIM_VISUAL"] = {"status": "ENGINEERING_READY_FOR_HUMAN_VALIDATION"}
d["stage8_gates"]["DEDUP"] = {"status": "PROVISIONAL_PASS"}
d["stage8_gates"]["G5_PRODUCTION_QA"] = {"status": "PROVISIONAL_PASS"}
d["stage8_gates"]["G4_VOICE_BGM"] = {"status": "VOICE_READY_FOR_INPUT_BGM_LIBRARY_NOT_READY"}
d["morning_validation"] = {
    "calibration_correction_applied": True,
    "human_review_packs": ["TREECUT_G2_HUMAN_REVIEW_V2.html", "TREECUT_G3_HUMAN_REVIEW_V2.html",
                           "TREECUT_DEDUP_HUMAN_REVIEW_V1.html"],
    "g2_targets": {"hard_neg_reject": "100%", "top3_usable": ">=85%", "top1_usable": ">=70%",
                   "boundary_usable": ">=80%", "denominator": "存在目标动作素材的Query",
                   "no_source": "NO_VALID_SOURCE_AVAILABLE"},
    "g3_targets": {"p0_mismatch": 0, "top3_suitable": ">=90%", "top1_suitable": ">=80%",
                   "unsupported_core_pass": 0, "story_conflict": 0}}
d["updated_at"] = now
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("erratum + state frozen")
