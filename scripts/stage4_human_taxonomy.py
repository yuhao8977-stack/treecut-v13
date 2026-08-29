# -*- coding: utf-8 -*-
"""Stage 2 — Human24 固定 Taxonomy 提取（从知识库生成，非 AI 生成）。

生成 BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json：
  - user_needs[]（P4-USER_NEED-*，21）
  - business_values[]（P4-BUSINESS_VALUE-*，18）
  - decision_factors[]（P4-DECISION_FACTOR-*，16）
  - search_intents[]（P4-SEARCH_INTENT-*，13）
  - shot_functions[]（P4-SHOT_FUNCTION-*，15）
  - trust_signals[]（从 content_roles TRUST typical_evidence + craft_trust 定义固定业务词典）
  - content_roles[]（TRAFFIC/SEARCH/TRUST/CONVERSION，固定 4 类）
  - mother_themes[]（SPACE_SOLUTION/FAMILY_SCENE/DECISION_AVOID_PIT/AESTHETIC_STYLE/CRAFT_TRUST，固定 5 类）
  - affinity_levels[]（STRONG/MEDIUM/WEAK/NOT_SUPPORTED/UNKNOWN）
Guard：固定业务词典，不随 AI 输出变化；Human 从全量独立勾选。
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "knowledge_brain.db")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json")

# trust_signals 固定业务词典（来源：content_roles TRUST typical_evidence +
# craft_trust KB-03 工艺定义；非 AI 生成）
TRUST_SIGNALS = [
    {"id": "FACTORY_PRODUCTION", "cn": "工厂生产/加工"},
    {"id": "PRECISION_CRAFT", "cn": "工艺精度（拼接/封边/圆弧）"},
    {"id": "STRUCTURE_DETAIL", "cn": "结构/细节展示"},
    {"id": "REAL_CUSTOMER_CASE", "cn": "真实住宅/客户案例"},
    {"id": "INSTALLATION", "cn": "安装/测量"},
    {"id": "QUALITY_CONTROL", "cn": "品控/标准"},
]


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def grab(prefix):
        rows = conn.execute("SELECT knowledge_id, title FROM knowledge_entries "
                            "WHERE knowledge_id LIKE ? ORDER BY knowledge_id",
                            (prefix + "%",)).fetchall()
        return [{"id": r["knowledge_id"][len(prefix):], "cn": r["title"]} for r in rows]

    tax = {
        "taxonomy_version": "HUMAN24_FIXED_V1",
        "guard": "固定业务词典（来自 Knowledge Brain V1.2 P4 定义）；非 AI 生成、不随 AI 输出变化",
        "source": "knowledge_brain.db V1.2",
        "user_needs": grab("P4-USER_NEED-"),
        "business_values": grab("P4-BUSINESS_VALUE-"),
        "decision_factors": grab("P4-DECISION_FACTOR-"),
        "search_intents": grab("P4-SEARCH_INTENT-"),
        "shot_functions": grab("P4-SHOT_FUNCTION-"),
        "trust_signals": TRUST_SIGNALS,
        "content_roles": [
            {"id": "TRAFFIC", "cn": "流量"}, {"id": "SEARCH", "cn": "搜索"},
            {"id": "TRUST", "cn": "信任"}, {"id": "CONVERSION", "cn": "转化"}],
        "mother_themes": [
            {"id": "SPACE_SOLUTION", "cn": "空间解决方案"},
            {"id": "FAMILY_SCENE", "cn": "家庭生活场景"},
            {"id": "DECISION_AVOID_PIT", "cn": "决策避坑"},
            {"id": "AESTHETIC_STYLE", "cn": "审美风格"},
            {"id": "CRAFT_TRUST", "cn": "工艺信任"}],
        "affinity_levels": ["STRONG", "MEDIUM", "WEAK", "NOT_SUPPORTED", "UNKNOWN"],
    }
    json.dump(tax, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    for k in ("user_needs", "business_values", "decision_factors", "search_intents",
              "shot_functions", "trust_signals", "content_roles", "mother_themes"):
        print(f"  {k}: {len(tax[k])}")
    conn.close()


if __name__ == "__main__":
    main()
