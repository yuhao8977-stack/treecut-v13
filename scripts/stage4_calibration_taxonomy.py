# -*- coding: utf-8 -*-
"""V3 — 生成 CALIBRATION_TAXONOMY_V1（从引擎 SEMANTIC_MAPPINGS 程序化提取）。

只含当前 BusinessCognition 引擎实际可输出的标签（AI_OUTPUT_VOCABULARY_V1）：
  5 user_needs + 5 business_values = 10 标签。
这是 Calibration Scope（引擎能力），不是完整 Human Business Taxonomy。
来源 = 全局 Engine Capability（SEM_001-007），非当前 segment 的 AI 答案 → 不构成 AI answer leakage。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json")

# 中文名（与 Human Taxonomy 一致，用于 UI 显示）
CN = {
    "STORAGE": "收纳", "CHARGING_POWER": "充电取电", "GUEST_CAPACITY": "待客扩容",
    "DINING": "日常用餐", "OFFICE": "办公学习",
    "STORAGE_EFFICIENCY": "收纳效率", "POWER_CONVENIENCE": "取电便利",
    "FLEXIBLE_CAPACITY": "灵活扩容", "DINING_CONVENIENCE": "用餐便利",
    "WORK_FROM_HOME": "居家办公",
}


def main():
    sys.path.insert(0, os.path.join(REPO, "src"))
    from treecut.services.business_cognition_v2 import SEMANTIC_MAPPINGS

    needs, values = set(), set()
    for rule in SEMANTIC_MAPPINGS:
        for c in rule["claims"]:
            if c["status"] == "SUPPORTED":
                if c["category"] == "USER_NEED":
                    needs.add(c["value"])
                elif c["category"] == "BUSINESS_VALUE":
                    values.add(c["value"])

    tax = {
        "manifest": "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1",
        "scope": "AI_OUTPUT_VOCABULARY_V1 — 当前引擎 SEM_001-007 实际可输出的 SUPPORTED 标签",
        "guard": "Calibration Scope，非完整 Human Business Taxonomy；"
                 "不得解释为 TreeCut 只有这 10 个业务标签；"
                 "来源=全局 Engine Capability，非当前 segment AI 答案 → 无 AI answer leakage",
        "user_needs": [{"id": n, "cn": CN.get(n, n)} for n in sorted(needs)],
        "business_values": [{"id": v, "cn": CN.get(v, v)} for v in sorted(values)],
        "label_states": ["CLEARLY_SUPPORTED", "POSSIBLE_BUT_INSUFFICIENT",
                         "NOT_SUPPORTED", "UNKNOWN"],
        "default_state": "NOT_SUPPORTED",
        "state_definitions": {
            "CLEARLY_SUPPORTED": "仅根据当前视频和可靠证据，这个业务意义已经被明确证明。",
            "POSSIBLE_BUT_INSUFFICIENT": "这个方向可能成立，但当前镜头本身不足以证明。",
            "NOT_SUPPORTED": "当前视频不支持这个业务意义。",
            "UNKNOWN": "信息不足，我无法可靠判断。",
        },
        "evidence_levels": ["SUFFICIENT", "PARTIAL", "INSUFFICIENT", "UNKNOWN"],
        "conflict_levels": ["YES", "NO", "UNKNOWN"],
        "conflict_types": ["SCENE_CONTEXT", "ASR_CONTEXT", "MATERIAL", "OTHER"],
    }
    json.dump(tax, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("user_needs:", [n["id"] for n in tax["user_needs"]])
    print("business_values:", [v["id"] for v in tax["business_values"]])
    print("共", len(needs) + len(values), "标签")
    assert len(needs) == 5 and len(values) == 5, "引擎输出词汇应为 5+5"


if __name__ == "__main__":
    main()
