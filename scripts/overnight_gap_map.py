#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Overnight — Gap Map + AUTO_ROI_GAP_REPORT（只读汇总，基于已产出证据）。"""
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")


def load(n):
    return json.loads((OUT / n).read_text(encoding="utf-8"))


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    funnel = load("TREECUT_OVERNIGHT_FUNNEL_V1.json")
    probe = load("TREECUT_PRODUCTION_CONTRACT_PROBE_V1.json")
    pool = load("TREECUT_OVERNIGHT_NON_HOLDOUT_BENCHMARK_POOL_V1.json")
    probe_by = {c["capability"]: c for c in probe["capabilities"]}

    gap_map = {
        "experiment": "TREECUT_OVERNIGHT_GAP_MAP_V1",
        "generated_at": now,
        "main_blockers_ranked": [
            {"rank": 1, "gap": "MMVV 只 SHADOW（MMVV_ENFORCEMENT 硬阻断）",
             "evidence": probe_by["方向/状态(几何)"]["blocker"],
             "affects": "动作证据无法自动阻断错误选镜；最终成片正确性依赖人工"},
            {"rank": 2, "gap": "A3 泛化未验证（冻结算法未在 unseen 上作答）",
             "evidence": "缺 Human ROI；blind 已建，明日起可标",
             "affects": "EXTEND 检索/几何判断是否可泛化未知"},
            {"rank": 3, "gap": "检索语义缺口：RETRACT 路径召回=0；路径关键词误导桶存在",
             "evidence": f"funnel keyword recall RETRACT=0；EXTEND 358 命中/190 家族，最大桶「11.29 产品视频拍摄」28",
             "affects": "动作召回完整性；误召回"},
            {"rank": 4, "gap": "生产组装链未闭环（shot_usage=0、模板 4、E2E 编排 CODE_EXISTS）",
             "evidence": probe_by["Story/Timeline"]["blocker"], "affects": "脚本→3 候选成片未实现"},
            {"rank": 5, "gap": "无授权 Voice/BGM 输入",
             "evidence": "VOICE_PRODUCTION_INPUT_REQUIRED / BGM_LIBRARY_INPUT_REQUIRED",
             "affects": "成片音轨只能 fallback/诊断"},
        ],
        "where_blocked_summary": {
            "有素材": f"G1 池≈{funnel['G1_eligible_mp4_approx']}（mp4 23253，review APPROVED 仅 88）",
            "有 segment": "B007 30 note 全覆盖(609 seg)；X1 大池 segments 41834",
            "语义证据": "ASR 51543 / OCR 289218 行存在(asset 键控)",
            "动作候选": "路径关键词候选存在(EXTEND358 等)，但语义/几何动作真值未全量校准",
            "claim 匹配": "G3 仅 TESTED_SYNTHETIC",
            "MMVV": "SHADOW_ONLY + Core5/A2 闭合(受控集)",
            "production shot": "shot_usage=0（尚未有真实成片选镜落库）",
        },
        "conclusion": ("缺口不在“没素材/没代码”，而在：①动作→生产证据链(MMVV 未强制、泛化未验) "
                       "②检索语义层(RETRACT/误导桶) ③组装闭环(shot/模板/编排) ④外部输入(Voice/BGM)。"),
    }
    (OUT / "TREECUT_OVERNIGHT_GAP_MAP_V1.json").write_text(
        json.dumps(gap_map, ensure_ascii=False, indent=1), encoding="utf-8")

    auto_roi = {
        "experiment": "AUTO_ROI_GAP_REPORT",
        "generated_at": now,
        "status": "NOT_SCORABLE_TONIGHT",
        "evidence": {
            "qwen_semantic_roi": "TREECUT_MMV_SEMANTIC_ROI_V1.json status=BLOCKED：qwen2.5vl 多对象 JSON bbox 回显联合名/绝对坐标/伪 JSON，MODEL_DETECTED ROI 不可信",
            "fallback": "布局启发式 + 运动簇归属（小簇排除）— 残差高/人带重叠弱（KNOWN6_R2）",
            "roi_ownership": "TREECUT_MMV_ROI_OWNERSHIP_V1.json：ISLAND_BODY 含 TABLETOP/DRAWER/TRACK_SOCKET；SOCKET motion 不得计入 TABLETOP；person 带 mask 排除",
            "mmvv_roi_usage": "A1/A21/A2 全部使用 L3_HUMAN_ROI（A21 绑定=人工框索引）— 无同帧机器 ROI 可对比",
        },
        "needed_for_scoring": "在 A1 calibration 帧上以受控实验重跑可信机器 ROI（新 VLM 或修复回显）→ 与 200 个人工框比 label accuracy/bbox IoU/missing；禁碰 A3 blind",
        "note": "未用 A3 GT 训练或调自动 ROI",
    }
    (OUT / "TREECUT_OVERNIGHT_AUTO_ROI_GAP_REPORT.json").write_text(
        json.dumps(auto_roi, ensure_ascii=False, indent=1), encoding="utf-8")
    print("WROTE gap map + auto-roi report")
    print("pool_size:", pool["pool_size"])


if __name__ == "__main__":
    main()
