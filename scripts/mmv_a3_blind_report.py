#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MMVV A3 — POSTBLIND 错误分析 + 泛化报告生成（评分后阶段）。"""
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DOCS = REPO / "docs"
sys.stdout.reconfigure(encoding="utf-8")


def load(n):
    return json.loads((OUT / n).read_text(encoding="utf-8"))


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    pred = load("TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json")
    scored = load("TREECUT_MMVV_A3_SCORED_RESULTS.json")
    obs = load("TREECUT_MMVV_A3_OBSERVABILITY_HUMAN_V1.json")
    obs_map = {a["opaque_case_id"]: a["observability_label"] for a in obs["answers"]}
    pred_map = {c["opaque_case_id"]: c for c in pred["cases"]}
    rows = []
    for r in scored["rows"]:
        c = pred_map[r["opaque_case_id"]]
        geo = c["geometry_evidence"]
        cam = c["camera_evidence"]
        unusable = sum(1 for p in cam["pairs"] if p["pair_state"] != "SAME_SCENE")
        rows.append({
            "opaque_case_id": r["opaque_case_id"],
            "original_case_id": r["original_case_id"],
            "media_id": r["media_id"],
            "human_gt": r["human_gt"],
            "machine_verdict": r["machine_verdict"],
            "category": r["category"],
            "geometry_state": geo["state_progress"],
            "geometry_direction": geo["direction_action"],
            "camera_state": c["camera_case"],
            "camera_pairs_unusable": f"{unusable}/{len(cam['pairs'])}",
            "target_frames_used": len(geo["frames_used"]),
            "target_visibility": c["target_identity_state"],
            "key_reason_codes": list(dict.fromkeys(c["reason_codes"] + geo["reason_codes"])),
            "observability": obs_map.get(r["opaque_case_id"]),
            "correct": (r["category"] in ("TP", "TN")),
            "error_attribution": ("-"
                if r["category"] in ("TP", "TN")
                else ("ALGORITHM_OR_REPRESENTATION_LIMITATION: camera channel "
                      f"({cam['state']}; {unusable}/{len(cam['pairs'])} pairs unusable -> "
                      f"CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE)")),
        })
    analysis = {
        "experiment": "MMVV_A3_POSTBLIND_ERROR_ANALYSIS",
        "generated_at": now,
        "prediction_sha256": scored.get("prediction_sha256"),
        "summary": scored["summary"],
        "note": ("6/6 UNSURE，FP=0。Observability 6/6 ACTION_PROCESS_VISIBLE → "
                 "positive 侧 UNSURE 不得归因为‘5帧无动作信息’，一律归因算法/表征层 "
                 "(此处为 camera 通道在 unseen 案例上不可用)。False PASS=0，无 Observability 辩解需求。"),
        "observability_all_visible": True,
        "rows": rows,
        "channel_findings": {
            "camera": ("24 相邻帧对中 20 对 CAMERA_MODEL_UNRELIABLE "
                       "(多为 FORWARD_BACKWARD_TRACKS_UNSTABLE / NO_RELIABLE_CAMERA_MODEL) "
                       "→ A2.2 R1 background-masked camera 冻结法在 6 个 unseen 案例上多数无法建模 "
                       "(背景 track 不足/不稳定)。冻结 validator 相机闸 fail-safe → 全 UNSURE，0 FP。"),
            "geometry_raw": ("若相机闸不存在，geometry 通道: H001/H003/H004=EXTEND PROGRESSION_UP "
                             "(H001/H003 为 NO_EXTEND → 会 False PASS 风险)，H002/H006=RETRACT "
                             "PROGRESSION_DOWN (YES_EXTEND，方向反)，H005=STATIC。即几何通道单独亦不可信。"),
            "target_identity": ("全部案例目标框均 TARGET_SINGLE(每帧恰 1)；H001 前 2 帧 TARGET_NOT_VISIBLE "
                                "(EXTENSION_TABLETOP 仅 3/5 帧可见) — 身份通道本身无歧义失败。"),
            "defect_candidates": [
                "A3_POSTBLIND_DEFECT_CAM01: background-masked camera 背景 track 不足(低纹理/大排除区/人手运动)在 unseen 泛化失败",
                "A3_POSTBLIND_DEFECT_GEOM01: 目标框几何方向在 2/3 正例呈 RETRACT-down、在 2/3 负例呈 EXTEND-up → 目标框覆盖语义(伸缩桌板 vs 桌腿联动)未分离",
                "A3_POSTBLIND_DEFECT_ID01: H001 EXTENSION_TABLETOP 仅 3/5 帧可见(遮挡/出镜)",
            ],
            "no_repair": "本轮不改阈值/ROI/相机排除/目标选择/帧；修复须用新 calibration 数据，A3 结果永久保留为历史。",
        },
    }
    (OUT / "TREECUT_MMVV_A3_POSTBLIND_ERROR_ANALYSIS.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 报告 md ----
    L = []
    L.append("# TreeCut MMVV A3 — Blind Generalization Report（正式盲测结果）")
    L.append(f"\n- 生成: {now} · algorithm freeze: `ca34678` · ROI sha: `{pred.get('roi_sha256')}`")
    L.append(f"- prediction sha: `{scored.get('prediction_sha256')}`")
    L.append(f"- A3_PREDICTION_LOCK_COMMIT: `8caf9f6`（先于 GT reveal）")
    L.append("\n## 第一屏（A3 official status）")
    L.append(f"- A3 status: **A3_CORE_GENERALIZATION_PARTIAL**")
    L.append(f"- 机器 6 案例: 全部 **UNSURE**（`CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE`）")
    L.append(f"- GT 对应: UNSURE_POS=3 / UNSURE_NEG=3 · **FP=0** · FN=0 · TP=0 · TN=0")
    L.append(f"- coverage = 0.0（PASS+FAIL=0/6）· positive_pass=0 · negative_fail=0 · false_pass=0")
    L.append(f"- EXTEND_POSITIVE_RECOGNITION = **NOT_ESTABLISHED**")
    s = scored["summary"]
    L.append(f"- 汇总: {json.dumps({k: s[k] for k in ('TP','TN','FP','FN','UNSURE_POS','UNSURE_NEG','coverage')}, ensure_ascii=False)}")
    L.append("\n## 逐案例表")
    L.append("| case | 原case/media | GT | machine | 几何 state/dir | 相机 | 目标帧 | key codes | obs | 归因 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| {r['opaque_case_id']} | {r['original_case_id']}({r['media_id']}) | {r['human_gt']} | "
                 f"{r['machine_verdict']} | {r['geometry_state']}/{r['geometry_direction']} | "
                 f"{r['camera_state']} ({r['camera_pairs_unusable']} unusable) | {r['target_frames_used']}/5 | "
                 f"{'/'.join(r['key_reason_codes'][:3])} | {r['observability']} | {r['error_attribution'][:60]} |")
    L.append("\n## 结论与边界")
    L.append("- **6/6 UNSURE 且 0 False PASS**：冻结 validator 相机闸在 unseen 上 fail-safe 生效，未产出任何假阳性。")
    L.append("- Observability 6/6 可观察 → 正例 UNSURE 归因为 **ALGORITHM_OR_REPRESENTATION_LIMITATION**（相机通道 + 几何方向见 POSTBLIND_ERROR_ANALYSIS），不得归因采样。")
    L.append("- 相机通道泛化失败：24 对中 20 对 CAMERA_MODEL_UNRELIABLE → A2.2 R1 背景掩码相机未能在 unseen 案例建立模型（背景 track 不足）。")
    L.append("- 几何原始证据（若相机闸不存在）：2/3 正例呈 RETRACT-down、2/3 负例呈 EXTEND-up → 目标框几何方向本身不可信（缺陷候选 GEOM01）。")
    L.append("- **解释边界**：本结果仅说明——在 6 unseen + L3 ROI + 冻结 5 帧下，MMVV 几何/时序核心**未建立正例识别**（coverage 0、方向不一致）；"
             "不能说 MMVV Production Ready / Auto ROI Ready / Camera Validated / G2·G3·脚本→成片 Ready。")
    L.append("- 不修复：A3 6 案例永久保留为历史盲测；修复须用新 calibration 数据（缺陷候选已记录）。")
    L.append("\n## 审计链")
    L.append("- Commit A（prediction lock，GT 前）: `8caf9f6`")
    L.append("- Commit B（scoring/report，GT 后）: 见本次提交")
    L.append("- 产物: TREECUT_MMVV_A3_MACHINE_PREDICTIONS_BLIND.json(+.sha256.txt) / _PREDICTION_LOCK_V1.json / _SCORED_RESULTS.json / _POSTBLIND_ERROR_ANALYSIS.json / 本报告")
    (DOCS / "TREECUT_MMVV_A3_BLIND_GENERALIZATION_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print("WROTE analysis + report")
    print("rows:")
    for r in rows:
        print(f"  {r['opaque_case_id']} {r['original_case_id']} {r['human_gt']} {r['machine_verdict']} {r['category']}")


if __name__ == "__main__":
    main()
