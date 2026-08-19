"""P3: TC_CONTENT_TAGS 内容运营标签词典（与账号编号完全解耦）。

分类：SCENE / STATE / FEATURE / ACTION / SHOT / PERSON / CRAFT / STYLE / USE_CASE
"""
from __future__ import annotations

# 首批 40-60 个高价值标签（用户确认清单）
TC_CONTENT_TAGS: dict[str, list[str]] = {
    "SCENE": [
        "客户家", "工厂", "展厅", "厨房", "开放式厨房", "客厅", "餐厅",
        "客餐厅", "大横厅", "沙发后", "小户型", "过道", "餐边柜",
    ],
    "STATE": [
        "岛台整体", "收起", "展开", "伸缩", "旋转", "固定式", "活动式",
    ],
    "FEATURE": [
        "收纳", "薄抽", "深抽", "抽屉", "柜门", "轨道插座", "普通插座",
        "烤箱", "蒸烤箱", "小家电", "圆角", "圆弧", "嵌入电器",
    ],
    "ACTION": [
        "打开", "关闭", "拉出", "推回", "展开", "收起", "旋转",
        "插电", "放入", "拿出", "测量", "擦拭", "使用",
    ],
    "SHOT": [
        "全景", "中景", "特写", "静态", "动态", "推镜", "平移",
        "俯拍", "正面", "侧面",
    ],
    "PERSON": [
        "有人", "无人", "单人", "多人", "人物占比高", "人物占比低",
    ],
    "CRAFT": [
        "海棠角", "封边", "托底轨", "五金", "精准开孔", "嵌入", "柜体内部", "伸缩结构",
    ],
    "STYLE": [
        "潘多拉", "洞石", "岩板", "黑胡桃", "木纹", "亚克力",
        "奶油风", "中古风", "原木风", "意式", "极简",
    ],
    "USE_CASE": [
        "聚餐", "吃饭", "火锅", "咖啡", "办公", "充电", "备餐",
        "收纳", "多人就餐", "三口之家", "有娃家庭",
    ],
}

# 扁平集合（用于快速校验/推荐）
ALL_TAGS: set[str] = {tag for tags in TC_CONTENT_TAGS.values() for tag in tags}


def category_of(tag: str) -> str | None:
    for cat, tags in TC_CONTENT_TAGS.items():
        if tag in tags:
            return cat
    return None
