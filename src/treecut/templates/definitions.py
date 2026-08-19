"""P5: 内容模板定义 — CT01/CT02（版本化 JSON）。

命名规则：CT = Content Template（与账号编号 B001-B010 完全解耦）。
"""
from __future__ import annotations

import json
from pathlib import Path

# CT01 小户型空间解决型
CT01 = {
    "template_id": "CT01",
    "name": "小户型空间解决型",
    "version": "1.0",
    "content_goal": ["traffic", "search", "conversion"],
    "user_problem": "我家面积小/过道窄，能不能做岛台？",
    "min_duration": 35,
    "max_duration": 50,
    "slots": [
        {"order": 1, "name": "问题/强视觉", "min_duration": 1.5, "max_duration": 3.0,
         "semantic_query": "小户型岛台强视觉整体或伸缩变化", "preferred_tags": ["小户型", "岛台整体", "动态"]},
        {"order": 2, "name": "空间全景", "min_duration": 3.0, "max_duration": 5.0,
         "required_tags": ["客户家", "全景"], "preferred_tags": ["无人"]},
        {"order": 3, "name": "收起状态", "min_duration": 2.0, "max_duration": 4.0,
         "semantic_query": "岛台收起状态", "preferred_tags": ["收起", "岛台整体"]},
        {"order": 4, "name": "伸缩展开", "min_duration": 3.0, "max_duration": 5.0,
         "semantic_query": "岛台伸缩展开动作", "required_tags": ["伸缩"], "preferred_tags": ["动态"]},
        {"order": 5, "name": "过道/尺寸证明", "min_duration": 2.0, "max_duration": 4.0,
         "semantic_query": "卷尺测量尺寸 过道空间", "preferred_tags": ["测量"]},
        {"order": 6, "name": "收纳", "min_duration": 2.0, "max_duration": 4.0,
         "required_tags": ["收纳"], "preferred_tags": ["薄抽", "深抽", "抽屉"]},
        {"order": 7, "name": "插座", "min_duration": 2.0, "max_duration": 3.5,
         "semantic_query": "轨道插座使用", "preferred_tags": ["轨道插座", "插座"]},
        {"order": 8, "name": "整体结果", "min_duration": 3.0, "max_duration": 5.0,
         "semantic_query": "岛台整体效果展示", "preferred_tags": ["岛台整体", "客户家"]},
    ],
}

# CT02 真实客户伸缩案例型
CT02 = {
    "template_id": "CT02",
    "name": "真实客户伸缩案例型",
    "version": "1.0",
    "content_goal": ["conversion", "trust"],
    "user_problem": "平时人少不想占地，人多又坐不下怎么办？",
    "min_duration": 40,
    "max_duration": 60,
    "slots": [
        {"order": 1, "name": "家庭需求钩子", "min_duration": 2.0, "max_duration": 4.0,
         "semantic_query": "家庭用餐人数问题", "preferred_tags": ["多人就餐", "吃饭"]},
        {"order": 2, "name": "客户家全景", "min_duration": 3.0, "max_duration": 5.0,
         "required_tags": ["客户家", "全景"]},
        {"order": 3, "name": "尺寸展示", "min_duration": 2.0, "max_duration": 4.0,
         "semantic_query": "岛台尺寸 卷尺", "preferred_tags": ["测量"]},
        {"order": 4, "name": "收起状态", "min_duration": 2.0, "max_duration": 4.0,
         "preferred_tags": ["收起", "岛台整体"]},
        {"order": 5, "name": "展开动作", "min_duration": 3.0, "max_duration": 5.0,
         "required_tags": ["伸缩"], "semantic_query": "岛台展开 伸缩动作", "preferred_tags": ["动态"]},
        {"order": 6, "name": "人数场景", "min_duration": 2.0, "max_duration": 4.0,
         "semantic_query": "多人围坐岛台", "preferred_tags": ["多人就餐", "聚餐"]},
        {"order": 7, "name": "收纳", "min_duration": 2.0, "max_duration": 4.0,
         "required_tags": ["收纳"]},
        {"order": 8, "name": "电器使用", "min_duration": 2.0, "max_duration": 3.5,
         "semantic_query": "岛台电器使用 插座", "preferred_tags": ["烤箱", "轨道插座"]},
        {"order": 9, "name": "整体", "min_duration": 3.0, "max_duration": 5.0,
         "semantic_query": "客户家岛台整体效果", "preferred_tags": ["客户家", "岛台整体"]},
    ],
}

TEMPLATES: dict[str, dict] = {"CT01": CT01, "CT02": CT02}


def list_templates() -> list[dict]:
    return list(TEMPLATES.values())


def get_template(template_id: str) -> dict | None:
    return TEMPLATES.get(template_id)
