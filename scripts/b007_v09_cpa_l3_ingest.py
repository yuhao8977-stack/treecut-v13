# -*- coding: utf-8 -*-
"""V0.9 Checkpoint A — L3 Review16 集成（append-only，operator=user）。
将用户 16 段口头审核结构化；不覆盖 L1/L2。"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
R16 = json.loads((OUT / "B007_L3_REVIEW16_V2.json").read_text(encoding="utf-8"))
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"

# 用户口头描述（按 HTML 显示顺序 H1..H8, R1..R8），结构化字段仅取"明确"项，其余 UNKNOWN
USER = [
    # H1 SA-66f672d6:0
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product_visibility": "no", "human_note": "客户家讲解演示功能；画面主要是人像/特效，产品不可见；具体功能/细节看不出",
     "storage": "UNKNOWN", "power": "UNKNOWN", "flexible": "UNKNOWN", "dining": "UNKNOWN"},
    # H2 SD-670630e9:0 餐椅
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "岛台+餐椅", "product_visibility": "yes", "action": "讲解演示",
     "feature_demonstration": "yes", "power": "yes", "material": "UNKNOWN",
     "human_note": "客户家，讲岛台配的椅子，动作=讲解演示，有人物有产品，有功能演示，看得到产品，有电源插座"},
    # H3 SB-63c5675a:0
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product": "岛台+水槽+桌面", "product_visibility": "yes", "material": "岩板",
     "shot_function": "全景", "storage": "no",
     "human_note": "客户家，能看到岛台、水槽、桌面；看不见收纳；材质岩板；全景；无人物"},
    # H4 SB-66d7c509:0
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product_visibility": "yes", "action": "讲解演示", "shot_function": "全景",
     "human_note": "客户家，有人物，看得见产品，讲解演示，全景；其他无"},
    # H5 SA-6544d761:8
    {"scene": "DESIGN_DIAGRAM", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product_visibility": "no", "human_note": "设计图：厨房布局/功能布局图，无产品无人物无功能演示"},
    # H6 SA-64f158f4:1
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product_visibility": "yes", "power": "yes", "shot_function": "对比图",
     "human_note": "客户家对比图（装修前 vs 安装后），看得见产品与电源插座，无人物"},
    # H7 SA-64e42823:69
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product": "岛台", "product_visibility": "yes", "material": "岩板",
     "shot_function": "产品展示", "action": "无/展示", "human_note": "客户家产品展示，无人物，有岛台与椅子，材质岩板"},
    # H8 SA-66f672d6:16
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product": "伸缩岛台(嵌入式烤箱/抽屉/轨道插座/桌面)", "product_visibility": "yes",
     "material": "岩板", "storage": "yes", "power": "yes", "flexible": "yes",
     "human_note": "客户家，可见桌面、嵌入式烤箱、抽屉、轨道插座；岩板伸缩岛台；无人物"},
    # R1 RC-6A7B28AB:0
    {"scene": "FACTORY", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "黑白配伸缩岛台(抽屉/桌面/轨道插座)", "product_visibility": "yes",
     "storage": "yes", "power": "yes", "flexible": "yes", "action": "伸缩功能演示",
     "shot_function": "工厂展示区全景", "human_note": "工厂展示区，黑白配伸缩岛台，抽屉桌面轨道插座，全景，有人物，在做桌面伸缩功能演示"},
    # R2 RC-6A8EDCCA:0
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "伸缩岛台(亚克力桌腿/黑岩板桌面/白岩板台面)", "product_visibility": "yes",
     "power": "yes", "flexible": "yes", "material": "岩板+亚克力", "human_note": "客户家伸缩岛台，亚克力桌腿，黑岩板桌面，白岩板台面，轨道插座，有桌子有人物"},
    # R3 RC-6A411F31:0
    {"scene": "FACTORY", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "操作台(水槽/抽屉/柜子/轨道插座)", "product_visibility": "yes",
     "storage": "yes", "power": "yes", "action": "讲解", "shot_function": "产品展示区单独操作台",
     "human_note": "工厂内产品展示区单独操作台，水槽、抽屉、柜子、轨道插座，有人物在讲解"},
    # R4 RC-6A85B849:0
    {"scene": "SHOWROOM", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product_visibility": "no", "human_note": "展厅，有人物，没有产品，无工艺演示"},
    # R5 RC-6A8EDCCA:1
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "no",
     "product_visibility": "yes", "power": "yes", "storage": "yes",
     "human_note": "客户家，厨房打开有轨道插座，有抽屉，其他无"},
    # R6 RC-6A411FEB:7
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "伸缩岛台(岩板)", "product_visibility": "yes", "material": "岩板",
     "power": "yes", "flexible": "yes", "human_note": "客户家岩板伸缩岛台，桌面轨道插座，有椅子和人物"},
    # R7 RC-6A85B849:11
    {"scene": "INSTALLATION_SITE", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product_visibility": "yes", "action": "入户安装", "human_note": "入户安装画面：工人在抬产品进门，看得到产品但看不到细节"},
    # R8 RC-6A92B9E8:5
    {"scene": "CUSTOMER_HOME", "scene_evidence": "SUPPORTED", "human_presence": "yes",
     "product": "岛台(嵌入式电器区域)", "product_visibility": "partial", "action": "展示(人钻进嵌入区域)",
     "human_note": "客户家，部分产品可见：人物钻进岛台嵌入式电器嵌入区域展示；插座/抽屉/柜子/桌面看不到"},
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    order = [{"part": "historical", "seg": s} for s in R16["historical"]] + \
            [{"part": "recent", "seg": s} for s in R16["recent"]]
    assert len(order) == 16 and len(USER) == 16

    # 读 L2 candidates（Qwen）供对比 —— 本步骤不读取，仅写 L3
    rows_out = []
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    conn_w = sqlite3.connect(DB, timeout=30)
    conn_w.execute("CREATE TABLE IF NOT EXISTS b007_l3_review16_v1("
                   "id INTEGER PRIMARY KEY AUTOINCREMENT, segment_id TEXT, sample_id TEXT, stratum TEXT, "
                   "selection_role TEXT, operator TEXT, review_time TEXT, l3_json TEXT)")
    for (o, u) in zip(order, USER):
        seg = o["seg"]
        sid = seg["segment_id"]
        nid = seg["note_id"]
        l3 = {"scene": u.get("scene", "UNKNOWN"), "scene_evidence": u.get("scene_evidence", "SUPPORTED"),
              "product": u.get("product", "UNKNOWN"), "material": u.get("material", "UNKNOWN"),
              "function": u.get("function", "UNKNOWN"), "action": u.get("action", "UNKNOWN"),
              "shot_function": u.get("shot_function", "UNKNOWN"),
              "human_presence": u.get("human_presence", "UNKNOWN"),
              "product_visibility": u.get("product_visibility", "UNKNOWN"),
              "feature_demonstration": u.get("feature_demonstration", "UNKNOWN"),
              "storage_evidence": u.get("storage", "UNKNOWN"),
              "power_evidence": u.get("power", "UNKNOWN"),
              "flexible_capacity_evidence": u.get("flexible", "UNKNOWN"),
              "dining_context_evidence": u.get("dining", "UNKNOWN"),
              "human_note": u.get("human_note", "")}
        conn_w.execute("DELETE FROM b007_l3_review16_v1 WHERE segment_id=?", (sid,))
        conn_w.execute("INSERT INTO b007_l3_review16_v1(segment_id,sample_id,stratum,selection_role,"
                       "operator,review_time,l3_json) VALUES(?,?,?,?,?,?,?)",
                       (sid, seg["sample_id"], seg["stratum"], seg["selection_role"],
                        "user", now, json.dumps(l3, ensure_ascii=False)))
        rows_out.append({"order": f"{o['part'][0].upper()}{order.index(o) + 1}",
                         "part": o["part"], "sample_id": seg["sample_id"],
                         "selection_role": seg["selection_role"], "segment_id": sid,
                         "l3": l3})
    conn_w.commit()
    conn_w.close()

    integration = {"phase": "V0.9-CP-A", "mode": "APPEND_ONLY_L3",
                   "generated_at": now, "operator": "user",
                   "count": len(rows_out), "entries": rows_out,
                   "policy": "不覆盖 L1 observation / L2 model cognition；L1/L2 原表未改动"}
    (OUT / "B007_L3_REVIEW16_INTEGRATION_V1.json").write_text(
        json.dumps(integration, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps([{"id": r["order"], "sample": r["sample_id"], "role": r["selection_role"],
                       "scene": r["l3"]["scene"], "human": r["l3"]["human_presence"],
                       "product": (r["l3"]["product"] or "UNKNOWN")[:18],
                       "storage/power/flexible/dining": [r["l3"]["storage_evidence"],
                                                         r["l3"]["power_evidence"],
                                                         r["l3"]["flexible_capacity_evidence"],
                                                         r["l3"]["dining_context_evidence"]]}
                      for r in rows_out], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
