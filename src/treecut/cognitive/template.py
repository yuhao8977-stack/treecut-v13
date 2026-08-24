"""AI Business Cognitive System — Layer 6 模板匹配引擎 + 商业价值评分。

根据素材内容类型 + 账号适配度 + 镜头价值，推荐可用模板（T001-T004）并给出槽位建议。
同时计算商业价值评分（business_score 0-100，复用 quality_validation 的 5 维思路简化版）。
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.cognitive.store import CognitiveStore

# 内容类型 → 推荐模板映射
CONTENT_TEMPLATE_MAP = {
    "客户案例": "T001",
    "产品介绍": "T003",
    "工厂实力": "T002",
    "装修方案": "T003",
    "避坑知识": "T004",
}


@dataclass
class TemplateResult:
    asset_id: str
    template_id: str
    template_name: str
    match_score: float          # 0-1
    slots: list[dict] = field(default_factory=list)   # 槽位 + 建议
    business_score: float = 0.0  # 0-100
    business_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "match_score": round(self.match_score, 2),
            "slots": self.slots,
            "business_score": round(self.business_score, 1),
            "business_reasons": self.business_reasons,
        }


class TemplateEngine:
    """模板匹配 + 商业价值引擎。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()

    # ------------------------------------------------------------------

    def _get_content_type(self, asset_id: str) -> tuple[str, float]:
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute(
            "SELECT content_type, confidence FROM content_classification WHERE asset_id=?",
            (asset_id,)).fetchone()
        conn.close()
        return (row[0], row[1]) if row else ("", 0.0)

    def _get_scene_semantics(self, asset_id: str) -> list[dict]:
        return self.store.list_scene_semantics(asset_id)

    def _asset_value_features(self, asset_id: str) -> dict:
        """素材价值特征（用于镜头价值与商业评分）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        segs = conn.execute("SELECT COUNT(*) n FROM segments WHERE asset_id=?", (asset_id,)).fetchone()["n"]
        kfs = conn.execute("SELECT COUNT(*) n FROM keyframes WHERE asset_id=?", (asset_id,)).fetchone()["n"]
        trs = conn.execute("SELECT COUNT(*) n FROM transcripts WHERE asset_id=?", (asset_id,)).fetchone()["n"]
        ocrs = conn.execute("SELECT COUNT(*) n FROM ocr_text WHERE asset_id=?", (asset_id,)).fetchone()["n"]
        conn.close()
        return {"segments": segs, "keyframes": kfs, "transcripts": trs, "ocr": ocrs}

    def _estimate_lens_value(self, features: dict, content_type: str) -> float:
        """镜头价值粗估（0-100）：多段/多关键帧/有解说 → 高价值。"""
        score = 30.0
        if features["segments"] >= 3:
            score += 15
        if features["keyframes"] >= 6:
            score += 20
        if features["transcripts"] >= 3:
            score += 20
        if features["ocr"] > 0:
            score += 10
        if content_type in ("客户案例", "产品介绍"):
            score += 5
        return min(100.0, score)

    # ------------------------------------------------------------------

    def recommend(self, asset_id: str) -> TemplateResult:
        """为素材推荐模板 + 槽位建议 + 商业价值。"""
        content_type, conf = self._get_content_type(asset_id)
        features = self._asset_value_features(asset_id)
        lens_value = self._estimate_lens_value(features, content_type)
        semantics = self._get_scene_semantics(asset_id)

        # 模板匹配
        template_id = CONTENT_TEMPLATE_MAP.get(content_type, "")
        templates = self.store.list_templates()
        tpl = next((t for t in templates if t["template_id"] == template_id), None)
        if not tpl:
            tpl = templates[0] if templates else None
        if not tpl:
            return TemplateResult(asset_id, "", "", 0.0, business_score=lens_value,
                                  business_reasons=["无模板配置"])

        structure = json.loads(tpl.get("structure") or "[]")
        slot_rules = json.loads(tpl.get("slot_rules") or "{}")
        slots = []
        for slot in structure:
            role = slot.get("role", "")
            rule = slot_rules.get(role, "")
            # 槽位建议：基于素材可用特征
            advice = self._slot_advice(role, features, semantics)
            slots.append({
                "role": role,
                "time": slot.get("t", ""),
                "required": slot.get("required", False),
                "advice": advice,
            })

        # 匹配度：内容类型置信度 × 0.6 + 镜头价值/100 × 0.4
        match_score = conf * 0.6 + (lens_value / 100.0) * 0.4

        # 商业价值评分（简化 5 维聚合）
        business, reasons = self._business_score(content_type, lens_value, features)

        return TemplateResult(
            asset_id=asset_id,
            template_id=tpl["template_id"],
            template_name=tpl.get("template_name", ""),
            match_score=match_score,
            slots=slots,
            business_score=business,
            business_reasons=reasons,
        )

    def _slot_advice(self, role: str, features: dict, semantics: list[dict]) -> str:
        """槽位填充建议。"""
        sem_names = [s.get("semantic", "") for s in semantics[:3]]
        sem_txt = "、".join(sem_names) if sem_names else "（无场景语义）"
        if role in ("结果展示", "产品亮相", "产品展示"):
            return f"优先选用高镜头价值画面；当前素材场景语义: {sem_txt}"
        if role in ("功能卖点", "卖点拆解", "生产过程"):
            return (f"建议选取功能/细节素材；素材有 {features['keyframes']} 关键帧、"
                    f"{features['segments']} 场景段可供选择")
        if role == "CTA":
            return "使用模板预设 CTA 文案"
        if role in ("客户背景", "避坑讲解"):
            return f"结合 ASR 解说文本组织口播；当前素材有 {features['transcripts']} 段转写"
        return "常规素材即可"

    def _business_score(self, content_type: str, lens_value: float,
                        features: dict) -> tuple[float, list[str]]:
        """商业价值评分（0-100）。"""
        reasons = []
        score = 30.0
        # 内容类型加分
        type_bonus = {"客户案例": 25, "产品介绍": 20, "工厂实力": 15,
                      "装修方案": 18, "避坑知识": 20}
        if content_type in type_bonus:
            score += type_bonus[content_type]
            reasons.append(f"内容类型: {content_type} (+{type_bonus[content_type]})")
        # 镜头价值
        score += lens_value * 0.3
        reasons.append(f"镜头价值 {lens_value:.0f} (+{lens_value * 0.3:.0f})")
        # 有解说/文字
        if features["transcripts"] >= 3:
            score += 8
            reasons.append("有丰富解说 (+8)")
        if features["ocr"] > 0:
            score += 5
            reasons.append("画面含文字信息 (+5)")
        score = min(100.0, score)
        return score, reasons

    def batch(self, asset_ids: list[str]) -> dict:
        """批量模板推荐。"""
        results = []
        by_template: dict[str, int] = {}
        for aid in asset_ids:
            r = self.recommend(aid)
            results.append(r)
            if r.template_id:
                by_template[r.template_id] = by_template.get(r.template_id, 0) + 1
        scores = [r.business_score for r in results]
        return {
            "processed": len(results),
            "avg_business": round(sum(scores) / len(scores), 1) if scores else 0,
            "by_template": by_template,
            "results": [r.to_dict() for r in results],
        }
