# -*- coding: utf-8 -*-
"""Stage 3A.1 — AccountIdentityRegistryV1 + B003_KNOWN_CONTENT_ANCHORS_V1.json。

B003 身份正式注册（架构监工确认）：
  account_internal_id = B003
  display_name = BARBERRY坤宝岛台定制
  platform = XIAOHONGSHU
  confidence = HUMAN_CONFIRMED
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT_REG = os.path.join(DATA_ROOT, "ACCOUNT_IDENTITY_REGISTRY_V1.json")
OUT_ANC = os.path.join(DATA_ROOT, "B003_KNOWN_CONTENT_ANCHORS_V1.json")


def main():
    registry = {
        "manifest": "ACCOUNT_IDENTITY_REGISTRY_V1",
        "generated_at": "2026-08-30",
        "records": [
            {
                "account_internal_id": "B003",
                "platform": "XIAOHONGSHU",
                "display_name": "BARBERRY坤宝岛台定制",
                "aliases": ["BARBERRY坤宝岛台定制", "坤宝岛台定制", "BARBERRY"],
                "account_role": "PILOT_ACCOUNT",
                "status": "ACTIVE",
                "source_refs": ["ARCHITECT_CONFIRMED_2026-08-30"],
                "confidence": "HUMAN_CONFIRMED",
                "verified_by": "ARCHITECT",
                "verified_at": "2026-08-30",
                "notes": "架构监工直接确认的内部代号→平台显示名正式映射；"
                         "禁止仅依赖文件名中的 'B003' 搜索；"
                         "禁止以 B008 替代；'坤宝研究设计院' 需 Identity Evidence 才可合并",
            },
            {
                "account_internal_id": "B008",
                "platform": "XIAOHONGSHU",
                "display_name": "KUBON坤宝岛台工厂",
                "aliases": ["KUBON坤宝岛台工厂", "KUBON"],
                "account_role": "FUTURE_SECONDARY_PILOT_CANDIDATE",
                "status": "INDEPENDENT",
                "source_refs": ["FILE_NAME_B008_VIRAL_RECORD"],
                "confidence": "HIGH_CONFIDENCE",
                "verified_by": "SYSTEM",
                "verified_at": "2026-08-30",
                "notes": "保持独立账号数据源；本轮不进入 Content DNA；不替代 B003",
            },
            {
                "account_internal_id": "KBYSJY-UNKNOWN",
                "platform": "XIAOHONGSHU",
                "display_name": "坤宝研究设计院",
                "aliases": ["坤宝岛台研究所"],
                "account_role": "UNVERIFIED",
                "status": "PENDING_IDENTITY_CHECK",
                "source_refs": ["SRC-KBYSJY-ACCOUNT"],
                "confidence": "UNKNOWN",
                "verified_by": "SYSTEM",
                "verified_at": "2026-08-30",
                "notes": "29 条 note 存在；是否=B003 待 Identity Comparison，禁止强并",
            },
        ],
        "guard": "账号身份是数据血缘的根；未确认不得合并/替代",
    }
    json.dump(registry, open(OUT_REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    anchors = {
        "manifest": "B003_KNOWN_CONTENT_ANCHORS_V1",
        "generated_at": "2026-08-30",
        "known_account": "B003",
        "known_display_name": "BARBERRY坤宝岛台定制",
        "purpose": "DATA DISCOVERY / IDENTITY MATCHING ONLY（非完整 B003 内容清单）",
        "source": "HUMAN_CONFIRMED_HISTORY",
        "anchors": [
            {"title_fragment": "不是吧⁉️岛台直接掉地上😱", "known_account": "B003",
             "source": "HUMAN_CONFIRMED_HISTORY"},
            {"title_fragment": "岛台避坑9条💡照抄不翻车", "known_account": "B003",
             "source": "HUMAN_CONFIRMED_HISTORY"},
            {"title_fragment": "只有80平的家🏠看我是怎么做岛台的", "known_account": "B003",
             "source": "HUMAN_CONFIRMED_HISTORY"},
            {"title_fragment": "Vocal！大横厅设计布局🔥沙发后岛台‼️", "known_account": "B003",
             "source": "HUMAN_CONFIRMED_HISTORY"},
        ],
        "guard": "锚点仅用于发现与身份匹配；不得仅凭标题相似自动归属 B003",
    }
    json.dump(anchors, open(OUT_ANC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT_REG)
    print("->", OUT_ANC)


if __name__ == "__main__":
    main()
