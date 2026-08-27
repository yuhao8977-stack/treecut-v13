# -*- coding: utf-8 -*-
"""TreeCut Phase 2.5.1 — Annotation Schema V2 冻结定义。

ANNOTATION_DICTIONARY_V2：唯一业务维度与枚举（架构监工冻结口径）。
本模块只定义常量/枚举/词典映射，不修改任何历史标签。

冻结的业务维度：
  scene_family / scene_subtype
  product_family / product_variant
  material
  component
  function
  action_group / atomic_action
  shot_scale / shot_role
  people_presence / product_visibility / quality
"""
from __future__ import annotations

DICTIONARY_VERSION = "ANNOTATION_DICTIONARY_V2"

# ---------------------------------------------------------------------------
# 枚举（冻结）
# ---------------------------------------------------------------------------

SCENE_FAMILY = ("FACTORY", "CUSTOMER_HOME", "SHOWROOM", "INSTALLATION_SITE",
                "OTHER", "UNKNOWN")
SCENE_SUBTYPE = ("FACTORY_WORKSHOP", "FACTORY_SHOWROOM", "FACTORY_WAREHOUSE",
                 "FACTORY_OTHER", "NOT_APPLICABLE", "UNKNOWN")

PRODUCT_FAMILY = ("ISLAND", "BAR", "SIDEBOARD", "DINING_TABLE",
                  "OTHER", "UNKNOWN")
PRODUCT_VARIANT = ("STANDARD_ISLAND", "EXTENDABLE_ISLAND", "FLOATING_ISLAND",
                   "FLOOR_ISLAND", "NOT_APPLICABLE", "OTHER", "UNKNOWN")

MATERIAL = ("岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃",
            "其他", "UNKNOWN")

COMPONENT = ("DRAWER", "CABINET_DOOR", "TRACK_SOCKET", "COUNTERTOP", "SINK",
             "APPLIANCE_SLOT", "ACRYLIC_SUPPORT", "OTHER", "UNKNOWN",
             "NOT_APPLICABLE")

FUNCTION = ("STORAGE", "EXTENDABLE", "POWER", "DINING", "OFFICE", "WATER_BAR",
            "EMBEDDED_APPLIANCE", "CHILD_SAFETY", "OTHER", "UNKNOWN",
            "NOT_APPLICABLE")

ACTION_GROUP = ("STATIC", "SPEAKING", "EXTEND", "DRAWER", "CABINET",
                "POWER_INTERACTION", "WATER_INTERACTION", "OTHER", "UNKNOWN")
ATOMIC_ACTION = ("STATIC_DISPLAY", "PERSON_SPEAKING", "PULL_OUT", "RETRACT",
                 "PULL_OUT_THEN_RETRACT", "RETRACT_THEN_PULL_OUT",
                 "OPEN_DRAWER", "CLOSE_DRAWER", "OPEN_THEN_CLOSE_DRAWER",
                 "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET",
                 "OPEN_SINK_COVER", "OTHER", "UNKNOWN", "NOT_APPLICABLE")

SHOT_SCALE = ("WIDE", "MEDIUM", "CLOSE", "CLOSE_UP", "UNKNOWN")
SHOT_ROLE = ("PERSON_TALKING", "FUNCTION_DEMO", "SPACE_OVERVIEW",
             "PRODUCT_SHOWCASE", "DETAIL_SHOWCASE", "CRAFT_SHOWCASE",
             "INSTALLATION", "OTHER", "UNKNOWN")

PEOPLE_PRESENCE = ("YES", "NO", "UNKNOWN")

# 可训练真值字段（Schema V2 输出结构）
TRUTH_FIELDS = ("scene_family", "scene_subtype", "product_family",
                "product_variant", "material", "component", "function",
                "action_group", "atomic_action", "shot_scale", "shot_role",
                "people_presence", "product_visibility", "quality")

# ---------------------------------------------------------------------------
# 词典映射（v1/v2 中文标签 → Schema V2 枚举）
# 审计性质：把历史粗粒度/漂移词典归一化到冻结枚举；不修改历史标签本身。
# ---------------------------------------------------------------------------

SCENE_MAP = {
    "工厂": ("FACTORY", "UNKNOWN"),
    "工厂展示区": ("FACTORY", "FACTORY_SHOWROOM"),
    "加工车间": ("FACTORY", "FACTORY_WORKSHOP"),
    "客户住宅": ("CUSTOMER_HOME", "NOT_APPLICABLE"),
    "展厅": ("SHOWROOM", "NOT_APPLICABLE"),
    "安装现场": ("INSTALLATION_SITE", "NOT_APPLICABLE"),
    "其他": ("OTHER", "NOT_APPLICABLE"),
    "UNKNOWN": ("UNKNOWN", "UNKNOWN"),
}

PRODUCT_MAP = {
    "岛台": ("ISLAND", "UNKNOWN"),          # v1 粗词无法区分变体
    "伸缩岛台": ("ISLAND", "EXTENDABLE_ISLAND"),
    "悬浮岛台": ("ISLAND", "FLOATING_ISLAND"),
    "落地岛台": ("ISLAND", "FLOOR_ISLAND"),
    "吧台": ("BAR", "NOT_APPLICABLE"),
    "餐边柜": ("SIDEBOARD", "NOT_APPLICABLE"),
    "茶桌": ("DINING_TABLE", "NOT_APPLICABLE"),
    "其他": ("OTHER", "NOT_APPLICABLE"),
    "UNKNOWN": ("UNKNOWN", "UNKNOWN"),
}

# function/component：v1/v2 function 字段 → (component, function)
FUNCTION_MAP = {
    "抽屉": ("DRAWER", "STORAGE"),          # 组件词迁移：抽屉=component
    "抽屉收纳": ("DRAWER", "STORAGE"),
    "收纳": ("NOT_APPLICABLE", "STORAGE"),
    "伸缩": ("NOT_APPLICABLE", "EXTENDABLE"),
    "轨道插座": ("TRACK_SOCKET", "POWER"),
    "用电": ("UNKNOWN", "POWER"),
    "嵌入电器": ("APPLIANCE_SLOT", "EMBEDDED_APPLIANCE"),
    "隐藏电器": ("APPLIANCE_SLOT", "EMBEDDED_APPLIANCE"),
    "水槽": ("SINK", "WATER_BAR"),
    "水吧": ("UNKNOWN", "WATER_BAR"),
    "办公": ("UNKNOWN", "OFFICE"),
    "多人就餐": ("UNKNOWN", "DINING"),
    "其他": ("OTHER", "OTHER"),
    "UNKNOWN": ("UNKNOWN", "UNKNOWN"),
}

# action：v1/v2 → (action_group, atomic_action)
ACTION_MAP = {
    "讲解/演示": ("SPEAKING", "PERSON_SPEAKING"),
    "人物讲解": ("SPEAKING", "PERSON_SPEAKING"),
    "拉出/展开": ("EXTEND", "PULL_OUT"),    # v1 粗类（审计假设）
    "拉出": ("EXTEND", "PULL_OUT"),
    "展开": ("EXTEND", "PULL_OUT"),
    "缩回": ("EXTEND", "RETRACT"),
    "收纳/关闭": ("EXTEND", "RETRACT"),     # v1 粗类（审计假设）
    "收起": ("EXTEND", "RETRACT"),
    "拉出+缩回": ("EXTEND", "PULL_OUT_THEN_RETRACT"),
    "缩回+拉出": ("EXTEND", "RETRACT_THEN_PULL_OUT"),
    "打开抽屉": ("DRAWER", "OPEN_DRAWER"),
    "关闭抽屉": ("DRAWER", "CLOSE_DRAWER"),
    "打开+关闭抽屉": ("DRAWER", "OPEN_THEN_CLOSE_DRAWER"),
    "打开抽屉+关闭抽屉": ("DRAWER", "OPEN_THEN_CLOSE_DRAWER"),
    "打开柜门": ("CABINET", "OPEN_CABINET"),
    "插电": ("POWER_INTERACTION", "OPERATE_SOCKET"),
    "打开水槽盖拿起水龙头": ("WATER_INTERACTION", "OPEN_SINK_COVER"),
    "静态展示": ("STATIC", "STATIC_DISPLAY"),
    "其他": ("OTHER", "OTHER"),
    "UNKNOWN": ("UNKNOWN", "UNKNOWN"),
}

# shot_type：v1 景别 → shot_scale；v2 镜头内容 → shot_role
SHOT_SCALE_MAP = {"全景": "WIDE", "中景": "MEDIUM", "近景": "CLOSE",
                  "特写": "CLOSE_UP", "UNKNOWN": "UNKNOWN"}
SHOT_ROLE_MAP = {"人物讲解": "PERSON_TALKING", "功能演示": "FUNCTION_DEMO",
                 "空间扫镜": "SPACE_OVERVIEW", "其他-产品扫镜": "PRODUCT_SHOWCASE",
                 "其他": "OTHER", "UNKNOWN": "UNKNOWN"}

PEOPLE_MAP = {"yes": "YES", "no": "NO", "unknown": "UNKNOWN", "": "UNKNOWN"}


def freeze_schema() -> dict:
    """冻结字典（ANNOTATION_DICTIONARY_V2 内容）。"""
    return {
        "dictionary_version": DICTIONARY_VERSION,
        "scene_family": list(SCENE_FAMILY),
        "scene_subtype": list(SCENE_SUBTYPE),
        "product_family": list(PRODUCT_FAMILY),
        "product_variant": list(PRODUCT_VARIANT),
        "material": list(MATERIAL),
        "component": list(COMPONENT),
        "function": list(FUNCTION),
        "action_group": list(ACTION_GROUP),
        "atomic_action": list(ATOMIC_ACTION),
        "shot_scale": list(SHOT_SCALE),
        "shot_role": list(SHOT_ROLE),
        "people_presence": list(PEOPLE_PRESENCE),
        "truth_fields": list(TRUTH_FIELDS),
        "notes": (
            "ANNOTATION_DICTIONARY_V2 冻结（Phase 2.5.1）。"
            "product_family/variant、component/function、action_group/atomic_action、"
            "shot_scale/shot_role 强制分离；全字段支持 UNKNOWN/NOT_APPLICABLE；"
            "组合动作允许 sequence 结构，禁止写死无限枚举。"),
    }
