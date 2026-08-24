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
        """读取该素材的 ASR/OCR/路径文本。"""
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
        conn.close()
        return {
            "path": media["relative_path"] if media else "",
            "asr": " ".join(r["text_raw"] for r in asr_rows)[:3000],
            "ocr": " ".join(r["text"] for r in ocr_rows)[:3000],
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
    # 主流程
    # ------------------------------------------------------------------

    def analyze(self, asset_id: str, persist: bool = True) -> IndustryResult:
        """对单素材运行行业理解，可选持久化到 cognitive 新表。"""
        started = time.perf_counter()
        texts = self._collect_text(asset_id)
        full_text = f"{texts['asr']} {texts['ocr']} {texts['path']}"

        products = self._score_entries(full_text, "product")
        materials = self._score_entries(full_text, "material")
        scenes = self._score_entries(full_text, "scene")
        functions = self._match_functions(full_text)
        content_types = self._classify_content(full_text)

        result = IndustryResult(
            asset_id=asset_id,
            products=products, materials=materials, functions=functions,
            scenes=scenes, content_types=content_types,
            top_content_type=content_types[0]["type"] if content_types else "",
            top_confidence=content_types[0]["confidence"] if content_types else 0.0,
            seconds=time.perf_counter() - started,
        )

        if persist:
            self._persist(result, full_text)
        return result

    def _persist(self, result: IndustryResult, full_text: str) -> None:
        """写入 content_classification + scene_semantics。"""
        # 内容分类
        if result.content_types:
            top = result.content_types[0]
            sub_types = ",".join(c["type"] for c in result.content_types[1:3])
            reasons = json.dumps({
                "matched_top": top.get("matched", []),
                "products": [p["name"] for p in result.products[:3]],
                "materials": [m["name"] for m in result.materials[:3]],
                "functions": [f["name"] for f in result.functions[:3]],
            }, ensure_ascii=False)
            self.store.save_classification(
                result.asset_id, top["type"], sub_types,
                confidence=top["confidence"], reasons=reasons,
                model_version="brain-industry-v1",
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
