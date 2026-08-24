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
    "产品展示": "T003",
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

    def _get_account_dna(self) -> dict | None:
        """读取账号 DNA（坤宝岛台默认第一个）。"""
        accounts = self.store.list_accounts()
        if not accounts:
            return None
        return accounts[0]

    def _get_text(self, asset_id: str) -> str:
        """读取 ASR+OCR 全文 + 视觉语义（用于商业评分证据判定）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        parts = []
        for r in conn.execute(
                "SELECT text_raw FROM transcripts WHERE asset_id=? AND text_raw != ''",
                (asset_id,)):
            parts.append(r["text_raw"])
        for r in conn.execute(
                "SELECT text FROM ocr_text WHERE asset_id=? AND text != ''",
                (asset_id,)):
            parts.append(r["text"])
        # 视觉语义补充（CLIP 结果，空镜素材的产品/材质/功能信号）
        try:
            cls = conn.execute(
                "SELECT reasons FROM content_classification WHERE asset_id=?",
                (asset_id,)).fetchone()
            if cls and cls["reasons"]:
                reasons = json.loads(cls["reasons"])
                vt = reasons.get("vision", {})
                if isinstance(vt, dict):
                    labels = []
                    for grp in ("function", "material", "product", "scene"):
                        labels.extend(vt.get(grp, []) if isinstance(vt.get(grp), list) else [])
                    if labels:
                        parts.append(" ".join(f"视觉:{lab}" for lab in labels[:8]))
        except Exception:
            pass
        conn.close()
        return " ".join(parts)

    def _get_classification(self, asset_id: str) -> dict:
        """读取 V2 分类（主类型 + 元素 + 证据）。"""
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute(
            "SELECT content_type, confidence, content_elements, reasons "
            "FROM content_classification WHERE asset_id=?",
            (asset_id,)).fetchone()
        conn.close()
        if not row:
            return {"content_type": "", "confidence": 0.0,
                    "elements": [], "evidence": {}}
        try:
            reasons = json.loads(row[3] or "{}")
            evidence = reasons.get("evidence", {})
        except Exception:
            evidence = {}
        return {"content_type": row[0], "confidence": row[1] or 0.0,
                "elements": json.loads(row[2] or "[]") if row[2] else [],
                "evidence": evidence}

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
        """为素材推荐模板 + 槽位建议 + 商业价值（V2）。"""
        cls = self._get_classification(asset_id)
        content_type = cls["content_type"]
        conf = cls["confidence"]
        elements = cls["elements"]
        features = self._asset_value_features(asset_id)
        lens_value = self._estimate_lens_value(features, content_type)
        semantics = self._get_scene_semantics(asset_id)
        text = self._get_text(asset_id)
        account = self._get_account_dna()

        # V2 商业价值：5×20 维度 + 账号 DNA 调节
        business, reasons = self._business_score_v2(
            content_type, elements, text, lens_value, account)

        # 模板匹配（V2：置信度门槛，低置信/无匹配 → 无推荐）
        template_id = ""
        if content_type and conf >= 0.6:
            template_id = CONTENT_TEMPLATE_MAP.get(content_type, "")
        templates = self.store.list_templates()
        tpl = next((t for t in templates if t["template_id"] == template_id), None)
        if not tpl:
            return TemplateResult(
                asset_id, "", "无推荐", 0.0,
                business_score=business, business_reasons=reasons + [
                    "内容类型置信度不足或无匹配模板，暂不推荐"])

        structure = json.loads(tpl.get("structure") or "[]")
        slot_rules = json.loads(tpl.get("slot_rules") or "{}")
        slots = []
        for slot in structure:
            role = slot.get("role", "")
            rule = slot_rules.get(role, "")
            advice = self._slot_advice(role, features, semantics)
            slots.append({
                "role": role,
                "time": slot.get("t", ""),
                "required": slot.get("required", False),
                "advice": advice,
            })

        # 匹配度：内容类型置信度 × 0.6 + 镜头价值/100 × 0.4
        match_score = conf * 0.6 + (lens_value / 100.0) * 0.4

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

    def _business_score_v2(self, content_type: str, elements: list[str],
                           text: str, lens_value: float,
                           account: dict | None) -> tuple[float, list[str]]:
        """商业价值评分 V2（5×20 维度 + 账号 DNA 调节，人工校准版）。

        人工校准基准（第一轮 20 条：人工均值 产品介绍≈63 / 客户案例≈75 /
        功能展示≈50 / 其他≈0）：先按内容类型给基准分，再按证据微调五维，
        使总分贴近人工分布；纯空镜无产品做账号 DNA 惩罚。
        """
        reasons = []
        elem = set(elements)
        t = text or ""
        has_product = any(k in t for k in ("岛台", "茶桌", "餐桌", "餐边柜", "橱柜",
                                           "吧台", "台面", "岩板", "产品", "柜"))
        has_talk = bool(t.strip())

        # --- 内容类型基准分（人工校准） ---
        base_map = {"产品介绍": 55, "客户案例": 70, "产品展示": 45, "功能展示": 50,
                    "装修方案": 55, "知识分享": 50, "品牌展示": 35, "其他": 10}
        base = base_map.get(content_type, 30)
        reasons.append(f"内容类型基准: {content_type} ({base})")
        if not has_product and content_type in ("产品介绍", "产品展示", "功能展示"):
            base -= 8
            reasons.append("无产品主体识别，基准 -8")

        # --- 五维微调（各维 ±20，总和围绕基准） ---
        dims = {"真实性": 12, "产品价值": 12, "用户价值": 10,
                "内容传播": 10, "成交价值": 10}

        # 真实性：真实客户/空间证据
        real_ev = ["完工", "交付", "实景", "入户", "客户家", "家里", "安装完成",
                   "入住", "新家", "真实", "实拍", "客户", "先生", "女士", "小姐",
                   "委托", "定制"]
        if any(k in t for k in real_ev):
            dims["真实性"] = 18
            reasons.append("真实性: 有真实客户/空间证据 → 18")
        elif "工厂工艺" in elem:
            dims["真实性"] = 6
            reasons.append("真实性: 纯工厂无实景 → 6")
        else:
            dims["真实性"] = 10

        # 产品价值：产品 + 卖点词
        sell = ["尺寸", "材质", "功能", "台面", "岩板", "木纹", "抽屉", "颜色",
                "收纳", "设计", "工艺", "厚度", "细节", "收纳"]
        sell_hits = [k for k in sell if k in t]
        if has_product:
            dims["产品价值"] = 16 + min(4, 2 * len(set(sell_hits)))
            dims["产品价值"] = min(20, dims["产品价值"])
            reasons.append(f"产品价值: 产品+卖点词 {sell_hits[:3]} → {dims['产品价值']}")
        else:
            dims["产品价值"] = 5
            reasons.append("产品价值: 无产品识别 → 5")

        # 用户价值：解决装修问题
        solve = ["收纳", "动线", "小户型", "空间", "避坑", "省空间", "开门",
                 "轨道", "隐藏", "升降", "插座", "水吧", "方案", "规划", "布局"]
        solve_hits = [k for k in solve if k in t]
        if solve_hits:
            dims["用户价值"] = 14 + min(6, 2 * len(solve_hits))
            dims["用户价值"] = min(20, dims["用户价值"])
            reasons.append(f"用户价值: {solve_hits[:4]} → {dims['用户价值']}")

        # 内容传播：讲解/钩子
        hooks = ["对比", "前后", "效果", "震撼", "惊艳", "绝了", "高级",
                 "颜值", "直接冲", "注意", "千万别", "后悔", "干货"]
        hook_hits = [k for k in hooks if k in t]
        if hook_hits or has_talk:
            dims["内容传播"] = 14 + min(6, 2 * len(hook_hits))
            reasons.append(f"内容传播: 讲解/钩子 {hook_hits[:3]} → {dims['内容传播']}")
        else:
            dims["内容传播"] = 4
            reasons.append("内容传播: 纯空镜无讲解 → 4")

        # 成交价值：CTA / 客户背景
        cta = ["定制", "报价", "咨询", "联系", "私信", "优惠", "找我", "订购",
               "想要", "可以定制", "工厂直供", "评论区", "链接", "委托"]
        cta_hits = [k for k in cta if k in t]
        if cta_hits or "客户案例背景" in elem or content_type == "客户案例":
            dims["成交价值"] = 16
            reasons.append("成交价值: CTA/案例背书 → 16")
        else:
            dims["成交价值"] = 8

        # 五维合计作为最终分（基准不再叠加，五维已涵盖）
        total = sum(dims.values())
        reasons.append(f"五维: {dims} = {total}")

        # --- 账号 DNA 调节（坤宝岛台） ---
        if account:
            # 纯空镜无产品无讲解：工厂流水线对账号无价值
            if not has_product and not has_talk and "工厂工艺" in elem:
                total = int(total * 0.35)
                reasons.append("账号DNA: 纯工厂空镜 → 总分×0.35")
            elif not has_product and not has_talk:
                total = int(total * 0.5)
                reasons.append("账号DNA: 空镜无产品 → 总分×0.5")
        return max(0, min(100, total)), reasons

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
