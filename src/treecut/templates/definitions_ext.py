"""P7: CT03-CT12 内容模板定义（扩展，与 CT01/CT02 同结构版本化）。

优先级顺序（总控指令 §P7）：CT03 → CT05 → CT06 → CT10 → CT11 → CT12
→ CT04 → CT07 → CT08 → CT09。
"""
from __future__ import annotations

CT03 = {
    "template_id": "CT03", "name": "岛台尺寸避坑型", "version": "1.0",
    "content_goal": ["search", "high_intent"],
    "user_problem": "高度/宽度/过道/伸缩长度怎么选？",
    "min_duration": 30, "max_duration": 50,
    "slots": [
        {"order": 1, "name": "错误/问题", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台尺寸错误 踩坑", "preferred_tags": ["测量"]},
        {"order": 2, "name": "卷尺证明", "min_duration": 2, "max_duration": 4,
         "semantic_query": "卷尺测量尺寸", "required_tags": ["测量"]},
        {"order": 3, "name": "正确范围", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台正确尺寸 高度宽度", "preferred_tags": ["岛台整体"]},
        {"order": 4, "name": "真实案例", "min_duration": 3, "max_duration": 5,
         "required_tags": ["客户家"], "preferred_tags": ["全景"]},
        {"order": 5, "name": "后果对比", "min_duration": 2, "max_duration": 4,
         "semantic_query": "尺寸错误后果 过道窄", "preferred_tags": ["过道"]},
        {"order": 6, "name": "总结", "min_duration": 2, "max_duration": 3,
         "semantic_query": "尺寸总结 建议", "preferred_tags": ["岛台整体"]},
    ],
}

CT04 = {
    "template_id": "CT04", "name": "岛台避坑清单型", "version": "1.0",
    "content_goal": ["favorite", "search"],
    "user_problem": "装岛台容易踩哪些坑？",
    "min_duration": 45, "max_duration": 70,
    "slots": [
        {"order": 1, "name": "强钩子", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台避坑 清单", "preferred_tags": ["岛台整体"]},
        {"order": 2, "name": "避坑1", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台工艺问题", "preferred_tags": ["工艺", "五金"]},
        {"order": 3, "name": "避坑2", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台收纳问题", "preferred_tags": ["收纳"]},
        {"order": 4, "name": "避坑3", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台尺寸问题", "preferred_tags": ["测量"]},
        {"order": 5, "name": "避坑4", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台插座用电问题", "preferred_tags": ["轨道插座"]},
        {"order": 6, "name": "避坑5", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台工艺细节", "preferred_tags": ["海棠角", "封边"]},
        {"order": 7, "name": "总结", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台避坑总结", "preferred_tags": ["岛台整体"]},
    ],
}

CT05 = {
    "template_id": "CT05", "name": "收纳解决型", "version": "1.0",
    "content_goal": ["favorite", "trust"],
    "user_problem": "台面为什么总乱？岛台怎么收？",
    "min_duration": 35, "max_duration": 50,
    "slots": [
        {"order": 1, "name": "乱台面痛点", "min_duration": 2, "max_duration": 4,
         "semantic_query": "台面杂乱", "preferred_tags": ["岛台整体"]},
        {"order": 2, "name": "薄抽", "min_duration": 2, "max_duration": 4,
         "required_tags": ["薄抽"], "preferred_tags": ["打开", "拉出"]},
        {"order": 3, "name": "深抽", "min_duration": 2, "max_duration": 4,
         "required_tags": ["深抽"], "preferred_tags": ["拉出", "放入"]},
        {"order": 4, "name": "柜门", "min_duration": 2, "max_duration": 4,
         "required_tags": ["柜门"], "preferred_tags": ["打开"]},
        {"order": 5, "name": "小家电", "min_duration": 2, "max_duration": 3.5,
         "semantic_query": "小家电收纳", "preferred_tags": ["小家电"]},
        {"order": 6, "name": "前后对比", "min_duration": 2, "max_duration": 4,
         "semantic_query": "收纳前后对比 整洁", "preferred_tags": ["岛台整体", "收纳"]},
    ],
}

CT06 = {
    "template_id": "CT06", "name": "大横厅/沙发后布局型", "version": "1.0",
    "content_goal": ["traffic", "favorite", "consult"],
    "user_problem": "沙发后/大横厅空位怎么利用？",
    "min_duration": 35, "max_duration": 55,
    "slots": [
        {"order": 1, "name": "空间全貌", "min_duration": 3, "max_duration": 5,
         "required_tags": ["大横厅"], "preferred_tags": ["全景"]},
        {"order": 2, "name": "沙发关系", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台与沙发关系", "preferred_tags": ["沙发后", "大横厅"]},
        {"order": 3, "name": "岛台与餐边柜", "min_duration": 3, "max_duration": 5,
         "preferred_tags": ["餐边柜"]},
        {"order": 4, "name": "就餐/办公", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台就餐办公使用", "preferred_tags": ["办公", "吃饭"]},
        {"order": 5, "name": "收纳", "min_duration": 2, "max_duration": 4,
         "required_tags": ["收纳"]},
        {"order": 6, "name": "插座", "min_duration": 2, "max_duration": 3.5,
         "preferred_tags": ["轨道插座", "插座"]},
        {"order": 7, "name": "全景收尾", "min_duration": 3, "max_duration": 5,
         "required_tags": ["大横厅"], "preferred_tags": ["全景", "岛台整体"]},
    ],
}

CT07 = {
    "template_id": "CT07", "name": "餐岛布局对比型", "version": "1.0",
    "content_goal": ["search", "favorite"],
    "user_problem": "餐岛一体还是分离更显大？",
    "min_duration": 35, "max_duration": 50,
    "slots": [
        {"order": 1, "name": "一体vs分离", "min_duration": 2, "max_duration": 4,
         "semantic_query": "餐岛一体与分离对比", "preferred_tags": ["岛台整体"]},
        {"order": 2, "name": "分离全景", "min_duration": 3, "max_duration": 5,
         "required_tags": ["全景"], "preferred_tags": ["客户家"]},
        {"order": 3, "name": "动线", "min_duration": 2, "max_duration": 4,
         "semantic_query": "餐岛动线", "preferred_tags": ["过道"]},
        {"order": 4, "name": "餐桌移动", "min_duration": 2, "max_duration": 4,
         "semantic_query": "餐桌移动 布局变化", "preferred_tags": ["动态"]},
        {"order": 5, "name": "功能", "min_duration": 2, "max_duration": 4,
         "preferred_tags": ["收纳", "插座"]},
        {"order": 6, "name": "材质", "min_duration": 2, "max_duration": 3.5,
         "semantic_query": "岛台材质纹理", "preferred_tags": ["岩板", "木纹"]},
    ],
}

CT08 = {
    "template_id": "CT08", "name": "有娃安全型", "version": "1.0",
    "content_goal": ["search", "trust"],
    "user_problem": "有宝宝岛台怎么防磕碰？",
    "min_duration": 30, "max_duration": 45,
    "slots": [
        {"order": 1, "name": "尖角风险", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台尖角磕碰风险", "preferred_tags": ["岛台整体"]},
        {"order": 2, "name": "圆弧", "min_duration": 2, "max_duration": 4,
         "required_tags": ["圆弧"], "preferred_tags": ["圆角"]},
        {"order": 3, "name": "圆柱/亚克力腿", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台圆腿 亚克力", "preferred_tags": ["亚克力"]},
        {"order": 4, "name": "台面耐污", "min_duration": 2, "max_duration": 4,
         "semantic_query": "台面耐污擦拭", "preferred_tags": ["岩板", "擦拭"]},
        {"order": 5, "name": "收纳", "min_duration": 2, "max_duration": 4,
         "required_tags": ["收纳"]},
        {"order": 6, "name": "整体", "min_duration": 2, "max_duration": 4,
         "semantic_query": "有娃家庭岛台整体", "preferred_tags": ["岛台整体", "客户家"]},
    ],
}

CT09 = {
    "template_id": "CT09", "name": "风格配色拆解型", "version": "1.0",
    "content_goal": ["favorite", "traffic"],
    "user_problem": "中古/原木/意式岛台怎么配色不翻车？",
    "min_duration": 30, "max_duration": 45,
    "slots": [
        {"order": 1, "name": "整体氛围", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台风格氛围", "preferred_tags": ["中古风", "奶油风"]},
        {"order": 2, "name": "台面纹理", "min_duration": 2, "max_duration": 4,
         "semantic_query": "台面纹理质感", "preferred_tags": ["岩板", "洞石"]},
        {"order": 3, "name": "柜体", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台柜体颜色", "preferred_tags": ["木纹", "黑胡桃"]},
        {"order": 4, "name": "桌腿", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台桌腿材质", "preferred_tags": ["亚克力"]},
        {"order": 5, "name": "空间搭配", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台与空间配色协调", "preferred_tags": ["客户家", "全景"]},
        {"order": 6, "name": "整体", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台风格整体效果", "preferred_tags": ["岛台整体"]},
    ],
}

CT10 = {
    "template_id": "CT10", "name": "工艺信任型", "version": "1.0",
    "content_goal": ["trust", "conversion"],
    "user_problem": "为什么同样外观看起来价格差很多？",
    "min_duration": 35, "max_duration": 50,
    "slots": [
        {"order": 1, "name": "问题工艺", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台工艺问题", "preferred_tags": ["五金"]},
        {"order": 2, "name": "正确工艺特写", "min_duration": 3, "max_duration": 5,
         "required_tags": ["海棠角"], "preferred_tags": ["封边", "托底轨"]},
        {"order": 3, "name": "结构演示", "min_duration": 3, "max_duration": 5,
         "semantic_query": "岛台结构工艺演示", "preferred_tags": ["柜体内部", "五金"]},
        {"order": 4, "name": "耐用/风险解释", "min_duration": 2, "max_duration": 4,
         "semantic_query": "工艺耐用性", "preferred_tags": ["封边"]},
        {"order": 5, "name": "客户成品", "min_duration": 3, "max_duration": 5,
         "required_tags": ["客户家"], "preferred_tags": ["岛台整体"]},
    ],
}

CT11 = {
    "template_id": "CT11", "name": "轨道插座/用电场景型", "version": "1.0",
    "content_goal": ["function_search", "favorite"],
    "user_problem": "岛台用电怎么不满屋拉线？",
    "min_duration": 25, "max_duration": 40,
    "slots": [
        {"order": 1, "name": "乱线痛点", "min_duration": 2, "max_duration": 3.5,
         "semantic_query": "岛台拉线痛点", "preferred_tags": ["岛台整体"]},
        {"order": 2, "name": "轨道插座", "min_duration": 2, "max_duration": 4,
         "required_tags": ["轨道插座"]},
        {"order": 3, "name": "插入动作", "min_duration": 2, "max_duration": 4,
         "semantic_query": "插头插入轨道插座", "preferred_tags": ["插电"]},
        {"order": 4, "name": "火锅", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台火锅场景", "preferred_tags": ["火锅", "聚餐"]},
        {"order": 5, "name": "咖啡/充电", "min_duration": 2, "max_duration": 4,
         "semantic_query": "岛台咖啡充电", "preferred_tags": ["咖啡", "充电"]},
        {"order": 6, "name": "整体", "min_duration": 2, "max_duration": 3.5,
         "semantic_query": "岛台用电整体", "preferred_tags": ["岛台整体"]},
    ],
}

CT12 = {
    "template_id": "CT12", "name": "嵌入电器定制型", "version": "1.0",
    "content_goal": ["search", "trust"],
    "user_problem": "烤箱/蒸烤箱怎么嵌才不翻车？",
    "min_duration": 30, "max_duration": 45,
    "slots": [
        {"order": 1, "name": "尺寸风险", "min_duration": 2, "max_duration": 4,
         "semantic_query": "嵌入式电器尺寸风险", "preferred_tags": ["嵌入电器"]},
        {"order": 2, "name": "测量", "min_duration": 2, "max_duration": 4,
         "required_tags": ["测量"]},
        {"order": 3, "name": "开孔", "min_duration": 2, "max_duration": 4,
         "required_tags": ["精准开孔"], "preferred_tags": ["嵌入"]},
        {"order": 4, "name": "嵌入", "min_duration": 2, "max_duration": 4,
         "required_tags": ["嵌入电器"], "preferred_tags": ["烤箱", "蒸烤箱"]},
        {"order": 5, "name": "缝隙", "min_duration": 2, "max_duration": 4,
         "semantic_query": "电器嵌入缝隙处理", "preferred_tags": ["封边"]},
        {"order": 6, "name": "整体", "min_duration": 2, "max_duration": 4,
         "semantic_query": "嵌入电器岛台整体", "preferred_tags": ["岛台整体"]},
    ],
}

TEMPLATES_EXT: dict[str, dict] = {
    "CT03": CT03, "CT04": CT04, "CT05": CT05, "CT06": CT06,
    "CT07": CT07, "CT08": CT08, "CT09": CT09, "CT10": CT10,
    "CT11": CT11, "CT12": CT12,
}
