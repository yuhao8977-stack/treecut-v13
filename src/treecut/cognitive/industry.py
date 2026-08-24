"""AI Business Cognitive System — Layer 3/4 行业知识引擎（Phase 1）。

从 ASR 文本 / OCR 文本 / 素材路径提取行业特征：
  - 产品识别（product）：岛台/伸缩岛台/餐边柜/橱柜…
  - 材料识别（material）：岩板/潘多拉/黑胡桃/木纹…
  - 功能识别（function）：伸缩/收纳/抽屉/插座/隐藏电器…
  - 场景识别（scene）：客户家/工厂/展厅/厨房/安装…
  - 内容分类（content_type）：客户案例/产品介绍/工厂实力/装修方案/避坑知识

匹配算法：知识库关键词命中 + 权重累加 → 置信度归一化。
输出写入 content_classification / scene_semantics 新表。
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.cognitive.knowledge import KnowledgeLoader
from treecut.cognitive.store import CognitiveStore

# 功能关键词（来自行业知识，不依赖 product 域）
FUNCTION_KEYWORDS = {
    "伸缩": ["伸缩", "展开", "收缩", "折叠", "抽拉", "变形"],
    "收纳": ["收纳", "抽屉", "薄抽", "深抽", "储物", "分类"],
    "隐藏": ["隐藏", "隐形", "无把手", "嵌入式"],
    "插座": ["插座", "轨道插座", "充电", "电源"],
    "隐藏电器": ["烤箱", "洗碗机", "蒸箱", "冰箱", "电器"],
    "水吧": ["水吧", "水槽", "水龙头", "吧台"],
}

# 内容类型规则（domain=content_type 已入库，此处定义评分逻辑）
CONTENT_TYPE_RULES = {
    "客户案例": {"keywords": ["客户", "案例", "完工", "入户", "女士", "先生", "小姐",
                             "交付", "家里", "实景"], "weight": 1.0},
    "产品介绍": {"keywords": ["尺寸", "高度", "宽度", "材质", "功能", "台面",
                             "配置", "岛台", "岩板", "收纳"], "weight": 1.0},
    "工厂实力": {"keywords": ["工厂", "机器", "工人", "生产", "加工", "车间",
                             "设备", "工艺"], "weight": 0.9},
    "装修方案": {"keywords": ["户型", "方案", "设计", "规划", "布局", "效果图",
                             "装修"], "weight": 0.8},
    "避坑知识": {"keywords": ["避坑", "不要", "注意", "错误", "建议", "提醒",
                             "踩坑", "千万别"], "weight": 0.8},
}

# ======================================================================
# V2 双层内容类型（第一轮人工校准升级）
#
# 第一层 content_type_main：内容主体，回答"这个视频主要卖什么/为什么拍"
#   产品介绍 / 客户案例 / 装修方案 / 知识分享 / 品牌展示 / 功能展示
# 第二层 content_elements：内容元素，回答"里面有什么"
#   客户案例背景 / 尺寸展示 / 材质展示 / 功能展示 / 空间展示 /
#   收纳展示 / 安装过程 / 前后对比 / 客户反馈 / 工厂工艺
#
# 客户案例判定采用【证据机制】：
#   强证据 ≥2 个才判定客户案例；客户称呼词（女士/小姐/委托/定制）
#   只作为"客户案例背景"元素，不构成客户案例证据。
# ======================================================================

# 主类型强证据（每个命中 +1 证据分；客户案例需 ≥2）
MAIN_TYPE_EVIDENCE = {
    "客户案例": {
        "强证据": ["完工", "交付", "实景", "入户", "家里", "客户家", "安装完成",
                   "已经装好", "装好了", "效果", "落地", "对比", "客户反馈",
                   "满意", "入住", "新家"],
        "弱证据": ["女士", "小姐", "先生", "委托", "定制", "客户", "案例"],
    },
    "产品介绍": {
        "强证据": ["尺寸", "材质", "功能", "台面", "岛台", "收纳", "设计",
                   "这款", "这一款", "颜色", "岩板", "抽屉", "配置", "工艺",
                   "产品", "产品类", "空镜"],
        "弱证据": ["介绍", "展示", "讲解", "产品展示"],
    },
    "功能展示": {
        "强证据": ["收纳", "抽屉", "伸缩", "展开", "折叠", "隐藏", "插座",
                   "烤箱", "洗碗机", "升降", "轨道", "储物", "水吧", "功能",
                   "水龙头", "水槽"],
        "弱证据": ["演示", "操作", "试用"],
    },
    "装修方案": {
        "强证据": ["户型", "方案", "规划", "布局", "动线", "效果图", "设计图",
                   "小户型", "空间利用", "装修"],
        "弱证据": ["设计", "建议"],
    },
    "知识分享": {
        "强证据": ["避坑", "不要", "注意", "错误", "建议", "提醒", "踩坑",
                   "千万别", "别买", "后悔", "干货"],
        "弱证据": ["知识", "经验", "分享"],
    },
    "品牌展示": {
        "强证据": ["工厂", "车间", "机器", "生产线", "设备", "工艺", "加工",
                   "我们厂", "实力", "自有工厂", "工厂类"],
        "弱证据": ["品牌", "公司", "团队"],
    },
}

# 内容元素识别规则（命中即加入元素列表）
CONTENT_ELEMENTS_RULES = {
    "客户案例背景": ["女士", "小姐", "先生", "委托", "定制", "客户", "李", "王", "张",
                    "陈", "刘", "婉小姐", "业主", "房东"],
    "尺寸展示": ["尺寸", "高度", "宽度", "长度", "厚度", "公分", "厘米", "米",
                "80", "90", "100", "120", "多少"],
    "材质展示": ["岩板", "木纹", "实木", "黑胡桃", "潘多拉", "肤感", "雅光",
                "哑光", "石木", "不锈钢", "大理石", "石英石", "亚克力"],
    "功能展示": ["收纳", "抽屉", "伸缩", "展开", "折叠", "隐藏", "插座", "烤箱",
                "洗碗机", "轨道", "储物", "水吧", "升降"],
    "空间展示": ["厨房", "客厅", "餐厅", "阳台", "小户型", "开放式", "中岛",
                "空间", "户型"],
    "安装过程": ["安装", "装好", "施工", "组装", "落地", "现场"],
    "前后对比": ["对比", "之前", "以前", "改造前", "改造后", "变化", "差别"],
    "客户反馈": ["满意", "反馈", "说好", "好评", "喜欢", "推荐"],
    "工厂工艺": ["工厂", "车间", "机器", "加工", "切割", "打磨", "封边", "工艺",
                "生产线", "设备"],
    "真人讲解": ["大家好", "我是", "今天", "教", "给", "你看", "来看", "讲讲",
                "介绍一下", "推荐"],
}

# 内容元素 → 主类型线索（用于兜底判定）
ELEMENT_TO_MAIN = {
    "客户案例背景": "客户案例",
    "尺寸展示": "产品介绍",
    "材质展示": "产品介绍",
    "功能展示": "功能展示",
    "空间展示": "装修方案",
    "安装过程": "客户案例",
    "前后对比": "客户案例",
    "客户反馈": "客户案例",
    "工厂工艺": "品牌展示",
}

# 简体→繁体高频映射（ASR 为繁体时归一化，避免简体关键词库失效）
SIMPLIFY_MAP = str.maketrans(
    "剛開門戶車體廠處單對說這來時間裡內嗎讓當過還後從點問題顏色個樣開關鍵盤邊",
    "刚开门户车体厂处单对说这来时间里内吗让当过还后从点问题颜色个样开关键盘边",
)


def simplify_traditional(text: str) -> str:
    """繁体→简体归一化（覆盖家具行业常见高频字）。"""
    return text.translate(SIMPLIFY_MAP)


@dataclass
class IndustryResult:
    asset_id: str
    products: list[dict] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    functions: list[dict] = field(default_factory=list)
    scenes: list[dict] = field(default_factory=list)
    content_types: list[dict] = field(default_factory=list)
    top_content_type: str = ""
    top_confidence: float = 0.0
    # V2 双层内容类型
    content_type_main: str = ""          # 主类型：产品介绍/客户案例/装修方案/知识分享/品牌展示
    content_elements: list[str] = field(default_factory=list)  # 内容元素
    evidence: dict = field(default_factory=dict)  # 证据命中明细
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "products": self.products,
            "materials": self.materials,
            "functions": self.functions,
            "scenes": self.scenes,
            "content_types": self.content_types,
            "top_content_type": self.top_content_type,
            "top_confidence": round(self.top_confidence, 2),
            "content_type_main": self.content_type_main,
            "content_elements": self.content_elements,
            "evidence": self.evidence,
            "seconds": round(self.seconds, 2),
        }


class IndustryEngine:
    """行业知识引擎：特征抽取 + 内容分类。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        self.knowledge = KnowledgeLoader(db_path)

    # ------------------------------------------------------------------
    # 文本采集
    # ------------------------------------------------------------------

    def _collect_text(self, asset_id: str) -> dict:
        """读取该素材的 ASR/OCR/路径文本 + 视觉语义补充。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        media = conn.execute(
            "SELECT relative_path FROM media_files m JOIN assets a ON a.media_id=m.id "
            "WHERE a.asset_id=?", (asset_id,)).fetchone()
        asr_rows = conn.execute(
            "SELECT text_raw FROM transcripts WHERE asset_id=? AND text_raw != ''",
            (asset_id,)).fetchall()
        ocr_rows = conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text != ''",
            (asset_id,)).fetchall()
        # 视觉语义补充（CLIP 补认知结果，解决空镜素材文本缺失）
        vision_text = ""
        try:
            cls = conn.execute(
                "SELECT reasons FROM content_classification WHERE asset_id=?",
                (asset_id,)).fetchone()
            if cls and cls["reasons"]:
                reasons = json.loads(cls["reasons"])
                vt = reasons.get("vision", {})
                if isinstance(vt, dict):
                    labels = []
                    # 功能/材质标签优先（对内容意图判定更关键）
                    for grp in ("function", "material", "product", "scene"):
                        labels.extend(vt.get(grp, []) if isinstance(vt.get(grp), list) else [])
                    if labels:
                        vision_text = " ".join(f"视觉:{lab}" for lab in labels[:8])
        except Exception:
            pass
        if not vision_text:
            vision = conn.execute(
                "SELECT semantic FROM scene_semantics WHERE asset_id=? AND semantic LIKE '视觉:%'",
                (asset_id,)).fetchall()
            if vision:
                vision_text = " ".join(r["semantic"] for r in vision[:6])
        conn.close()
        return {
            "path": media["relative_path"] if media else "",
            "asr": " ".join(r["text_raw"] for r in asr_rows)[:3000],
            "ocr": " ".join(r["text"] for r in ocr_rows)[:3000],
            "vision": vision_text,
        }

    # ------------------------------------------------------------------
    # 关键词匹配
    # ------------------------------------------------------------------

    def _match_keywords(self, text: str, keywords: list[str]) -> list[str]:
        return [kw for kw in keywords if kw and kw in text]

    def _score_entries(self, text: str, domain: str) -> list[dict]:
        """按知识库条目匹配并打分（命中关键词数 × 权重）。"""
        scored = []
        for entry in self.knowledge.query(domain=domain):
            kws = json.loads(entry.get("keywords", "[]"))
            hits = self._match_keywords(text, kws)
            if hits:
                weight = float(entry.get("weight", 1.0))
                score = min(1.0, 0.4 + 0.15 * len(hits)) * weight
                scored.append({
                    "name": entry["name"],
                    "score": round(score, 3),
                    "matched": hits[:5],
                })
        scored.sort(key=lambda x: -x["score"])
        return scored

    def _match_functions(self, text: str) -> list[dict]:
        """功能识别（独立关键词表）。"""
        results = []
        for func, kws in FUNCTION_KEYWORDS.items():
            hits = self._match_keywords(text, kws)
            if hits:
                results.append({"name": func, "score": round(min(1.0, 0.5 + 0.15 * len(hits)), 3),
                                "matched": hits[:5]})
        results.sort(key=lambda x: -x["score"])
        return results

    def _classify_content(self, text: str) -> list[dict]:
        """内容类型分类（规则引擎 + 置信度）。"""
        results = []
        for ctype, rule in CONTENT_TYPE_RULES.items():
            hits = self._match_keywords(text, rule["keywords"])
            if hits:
                weight = rule["weight"]
                # 置信度：命中数越多越高，最多 0.95
                conf = min(0.95, 0.4 + 0.12 * len(hits)) * weight
                results.append({"type": ctype, "confidence": round(conf, 3),
                                "matched": hits[:5]})
        results.sort(key=lambda x: -x["confidence"])
        return results

    # ------------------------------------------------------------------
    # V2 双层内容类型（第一轮人工校准）
    # ------------------------------------------------------------------

    def _classify_content_v2(self, text: str, asr_text: str = "") -> tuple[str, float, list[str], dict]:
        """V2 内容理解：主类型 + 内容元素 + 证据。

        主类型判定原则：
          1. 客户案例必须 ≥2 个强证据（完工/实景/入户/前后对比/客户反馈…）
          2. 客户称呼词（女士/小姐/委托/定制）只作为"客户案例背景"元素，
             不构成客户案例证据 —— 反向排除（P0-2）
          3. 有实质讲解（ASR≥12字）+ 产品词 → 产品介绍（P0-1 内容意图）
          4. 无讲解空镜 + 功能演示标签（抽屉/收纳/伸缩/隐藏/插座）→ 功能展示
          5. 兜底：路径"产品类/空镜"信号或内容元素线索
        """
        # 1) 内容元素识别
        elements = []
        element_hits = {}
        for elem, kws in CONTENT_ELEMENTS_RULES.items():
            hits = self._match_keywords(text, kws)
            if hits:
                elements.append(elem)
                element_hits[elem] = hits[:5]
        # 去重保序
        seen, elements = set(), []
        for e, hits in element_hits.items():
            if e not in seen:
                seen.add(e)
                elements.append(e)

        # 2) 主类型证据评分
        scores: dict[str, float] = {}
        evidence: dict[str, dict] = {}
        for mtype, rules in MAIN_TYPE_EVIDENCE.items():
            strong = self._match_keywords(text, rules["强证据"])
            weak = self._match_keywords(text, rules["弱证据"])
            s = len(strong)
            w = len(weak)
            # 强证据权重 1.0，弱证据 0.3；客户案例弱证据（称呼词）不构成证据
            if mtype == "客户案例":
                score = s * 1.0 + w * 0.1   # 称呼词几乎不计分
            else:
                score = s * 1.0 + w * 0.3
            scores[mtype] = score
            evidence[mtype] = {"strong": strong[:8], "weak": weak[:8],
                               "score": round(score, 2)}

        # 3) 主类型决策
        # 客户案例硬门槛：≥2 强证据
        case_strong = len(evidence["客户案例"]["strong"])
        product_s = scores.get("产品介绍", 0)
        func_s = scores.get("功能展示", 0)
        brand_s = scores.get("品牌展示", 0)
        has_product_talk = product_s >= 1.0
        has_func_talk = func_s >= 1.0
        in_factory = brand_s >= 1.0 or "工厂" in element_hits.get("工厂工艺", [])
        # 有实质讲解（ASR 有效长度 ≥12 字）
        has_talk = len(asr_text.strip()) >= 12
        # 产品类路径（空镜素材无 ASR/OCR，路径是唯一信号）
        is_product_folder = ("产品类" in text or "空镜" in text or "产品空镜" in text)

        main_type = ""
        if case_strong >= 2:
            main_type = "客户案例"
        elif has_talk and has_product_talk:
            # 有实质讲解 + 产品词 → 产品介绍优先（内容意图核心修正）
            main_type = "产品介绍"
        elif not has_talk and has_func_talk:
            # 空镜 + 功能演示标签 → 功能展示
            main_type = "功能展示"
        elif has_product_talk:
            main_type = "产品介绍"
        elif has_func_talk:
            main_type = "功能展示"
        elif is_product_folder:
            # 空镜产品素材：无讲解文本，按产品介绍处理
            main_type = "产品介绍"
        elif scores.get("装修方案", 0) >= 1.0:
            main_type = "装修方案"
        elif scores.get("知识分享", 0) >= 1.0:
            main_type = "知识分享"
        elif in_factory:
            main_type = "品牌展示"
        else:
            # 兜底：内容元素线索
            clue: dict[str, int] = {}
            for e in elements:
                t = ELEMENT_TO_MAIN.get(e)
                if t:
                    clue[t] = clue.get(t, 0) + 1
            if clue:
                main_type = max(clue, key=clue.get)
            else:
                main_type = "其他"

        # 4) 置信度（V2：证据区分度，消除 0.52 锁定）
        s_main = scores.get(main_type, 0)
        others = sorted((v for k, v in scores.items() if k != main_type), reverse=True)
        runner = others[0] if others else 0.0
        if main_type == "客户案例":
            conf = min(0.95, 0.5 + case_strong * 0.15)
        else:
            # 主类型得分 / (主类型 + 次高分) 归一化，保证区分度
            denom = s_main + runner
            conf = min(0.95, 0.45 + 0.45 * (s_main / denom if denom else 0.5))
        conf = max(0.2, min(0.95, conf))

        return main_type, round(conf, 3), elements, evidence

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def analyze(self, asset_id: str, persist: bool = True) -> IndustryResult:
        """对单素材运行行业理解，可选持久化到 cognitive 新表。"""
        started = time.perf_counter()
        texts = self._collect_text(asset_id)
        full_text = f"{texts['asr']} {texts['ocr']} {texts['path']} {texts['vision']}"
        full_text = simplify_traditional(full_text)

        products = self._score_entries(full_text, "product")
        materials = self._score_entries(full_text, "material")
        scenes = self._score_entries(full_text, "scene")
        functions = self._match_functions(full_text)
        content_types = self._classify_content(full_text)
        # V2 双层内容类型（传原始 ASR 判断"是否有实质讲解"）
        asr_text = simplify_traditional(texts["asr"])
        main_type, main_conf, elements, evidence = self._classify_content_v2(full_text, asr_text)

        result = IndustryResult(
            asset_id=asset_id,
            products=products, materials=materials, functions=functions,
            scenes=scenes, content_types=content_types,
            top_content_type=main_type or (content_types[0]["type"] if content_types else ""),
            top_confidence=main_conf or (content_types[0]["confidence"] if content_types else 0.0),
            content_type_main=main_type,
            content_elements=elements,
            evidence=evidence,
            seconds=time.perf_counter() - started,
        )

        if persist:
            self._persist(result, full_text)
        return result

    def _persist(self, result: IndustryResult, full_text: str) -> None:
        """写入 content_classification + scene_semantics。"""
        # 保留已有 vision 标签（CLIP 结果不被覆盖）
        prev_vision = {}
        try:
            conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
            row = conn.execute(
                "SELECT reasons FROM content_classification WHERE asset_id=?",
                (result.asset_id,)).fetchone()
            conn.close()
            if row and row[0]:
                prev = json.loads(row[0])
                vt = prev.get("vision")
                if isinstance(vt, dict):
                    prev_vision = vt
        except Exception:
            pass
        # 内容分类（V2：主类型 + 内容元素）
        if result.content_type_main or result.content_types:
            top_type = result.content_type_main or result.content_types[0]["type"]
            conf = result.top_confidence or (
                result.content_types[0]["confidence"] if result.content_types else 0.0)
            sub_types = ",".join(c["type"] for c in result.content_types[1:3])
            reasons = json.dumps({
                "matched_top": result.content_types[0].get("matched", []) if result.content_types else [],
                "products": [p["name"] for p in result.products[:3]],
                "materials": [m["name"] for m in result.materials[:3]],
                "functions": [f["name"] for f in result.functions[:3]],
                "content_elements": result.content_elements,
                "evidence": result.evidence,
                "vision": prev_vision or {},
            }, ensure_ascii=False)
            self.store.save_classification(
                result.asset_id, top_type, sub_types,
                confidence=conf, reasons=reasons,
                model_version="brain-industry-v2",
                content_elements=result.content_elements,
            )
        # 场景语义（scene_semantics）
        semantics = []
        for scene in result.scenes[:3]:
            semantics.append({
                "segment_id": None,
                "semantic": scene["name"],
                "action": "",
                "lens_value": 0,
                "confidence": scene["score"],
                "model_version": "brain-industry-v1",
            })
        # 产品/材料作为附加语义
        for p in result.products[:2]:
            semantics.append({
                "segment_id": None, "semantic": f"产品:{p['name']}",
                "action": "", "lens_value": 0,
                "confidence": p["score"], "model_version": "brain-industry-v1",
            })
        if semantics:
            self.store.save_scene_semantics(result.asset_id, semantics)

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------

    def batch(self, asset_ids: list[str], persist: bool = True,
              progress=None) -> dict:
        """批量行业理解。返回统计。"""
        results = []
        by_content: dict[str, int] = {}
        for i, aid in enumerate(asset_ids):
            r = self.analyze(aid, persist=persist)
            results.append(r)
            if r.top_content_type:
                by_content[r.top_content_type] = by_content.get(r.top_content_type, 0) + 1
            if progress and (i + 1) % 20 == 0:
                progress(f"行业理解 {i + 1}/{len(asset_ids)}")
        return {
            "processed": len(results),
            "by_content_type": by_content,
            "with_content": sum(1 for r in results if r.top_content_type),
            "with_product": sum(1 for r in results if r.products),
            "with_material": sum(1 for r in results if r.materials),
            "with_function": sum(1 for r in results if r.functions),
            "results": [r.to_dict() for r in results],
        }
