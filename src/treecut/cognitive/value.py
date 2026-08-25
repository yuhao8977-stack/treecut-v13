"""TreeCut Phase 6 — 内容价值评估系统（Content Value Engine V2）。

目标：让 AI 判断"这个素材值不值得进入生产池"。
评分 100 分（用户指定）：
  用户价值 25  — 是否解决装修问题（动线/小户型/避坑/方案）
  产品卖点 25  — 是否有明确卖点（伸缩/收纳/轨道插座/尺寸/材质）
  信任价值 20  — 是否建立信任（客户家/真实案例/工厂实力/安装过程）
  传播价值 20  — 是否有爆款可能（冲突/数字/反常识/对比）
  转化价值 10  — 是否容易产生咨询（CTA/定制/报价/联系）

V2 校准（基于 100 条人工审核）：
  以内容类型为基准分（人工评分均值：客户案例≈75/产品介绍≈63/功能展示≈50/
  产品展示≈45/其他≈10），再用认知特征（元素/证据/ASR/OCR）上下微调，
  使评分贴近人工判断。

素材池分类（ABCD）：
  A 直接可生产  — 评分 ≥70 且内容完整（有讲解/案例）
  B 需要组合    — 评分 55-69，需与其他素材组合成片
  C 备用素材    — 评分 40-54，保留备用
  D 低价值      — 评分 <40，不推荐使用
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from treecut.cognitive.store import CognitiveStore

# 内容类型基准分（来自 100 条人工审核均值）
TYPE_BASE = {
    "客户案例": 75, "产品介绍": 63, "功能展示": 50, "产品展示": 45,
    "装修方案": 60, "知识分享": 55, "品牌展示": 40, "其他": 10, "": 30,
}

# 内容元素 → 维度加分（元素来自认知引擎）
ELEMENT_BONUS = {
    # 用户价值（25）
    "user_value": {
        "空间展示": 4, "尺寸展示": 5, "功能展示": 4, "产品展示": 2,
    },
    # 产品卖点（25）
    "product_merit": {
        "尺寸展示": 6, "材质展示": 6, "功能展示": 5, "产品展示": 3,
    },
    # 信任价值（20）
    "trust_value": {
        "客户案例背景": 5, "安装过程": 4, "客户反馈": 5, "前后对比": 4,
        "工厂工艺": 2,
    },
    # 传播价值（20）
    "comm_value": {
        "前后对比": 4, "客户反馈": 2, "真人讲解": 3,
    },
    # 转化价值（10）
    "deal_value": {
        "客户案例背景": 3, "真人讲解": 2,
    },
}

# ASR/OCR 关键词（各维度微调）
KEYWORD_HINTS = {
    "user_value": ["动线", "小户型", "空间", "避坑", "收纳", "省空间", "方案",
                   "规划", "布局", "开门", "高度", "升降", "轨道", "户型"],
    "product_merit": ["伸缩", "收纳", "轨道插座", "插座", "尺寸", "材质", "岩板",
                      "奢石", "抽屉", "隐藏", "升降", "厚度", "工艺", "细节", "薄抽"],
    "trust_value": ["客户", "完工", "实景", "交付", "安装", "工厂", "案例",
                    "师傅", "十年", "质保", "定制", "委托"],
    "comm_value": ["不要", "千万别", "后悔", "避坑", "注意", "对比", "前后",
                   "效果", "震撼", "惊艳", "小户型", "80平", "90平", "怎么做",
                   "超作业", "不翻车", "好看", "高级", "绝了"],
    "deal_value": ["定制", "报价", "咨询", "联系", "私信", "评论区", "直播",
                   "优惠", "找我", "订购", "链接", "工厂直供", "扣1", "扣2", "扣3"],
}


class ContentValueEngine:
    """内容价值评分引擎（Phase 6 V2，人工校准版）。"""

    DIM_WEIGHTS = {
        "user_value": 25, "product_merit": 25,
        "trust_value": 20, "comm_value": 20, "deal_value": 10,
    }

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_value (
                asset_id   TEXT PRIMARY KEY,
                user_value   REAL NOT NULL DEFAULT 0,
                product_merit REAL NOT NULL DEFAULT 0,
                trust_value  REAL NOT NULL DEFAULT 0,
                comm_value   REAL NOT NULL DEFAULT 0,
                deal_value   REAL NOT NULL DEFAULT 0,
                total_score  REAL NOT NULL DEFAULT 0,
                pool_class   TEXT NOT NULL DEFAULT 'C',
                pool_reason  TEXT NOT NULL DEFAULT '',
                computed_at  REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # 素材特征读取（复用认知结果）
    # ------------------------------------------------------------------

    def _get_features(self, asset_id: str) -> dict:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cls = conn.execute(
            "SELECT content_type, content_elements, reasons FROM content_classification "
            "WHERE asset_id=?", (asset_id,)).fetchone()
        asr_parts = [r["text_raw"] for r in conn.execute(
            "SELECT text_raw FROM transcripts WHERE asset_id=? AND text_raw!=''",
            (asset_id,))]
        ocr_parts = [r["text"] for r in conn.execute(
            "SELECT text FROM ocr_text WHERE asset_id=? AND text!=''", (asset_id,))]
        scenes = [r["semantic"] for r in conn.execute(
            "SELECT semantic FROM scene_semantics WHERE asset_id=?", (asset_id,))]
        conn.close()

        elements, evidence, content_type = [], {}, ""
        if cls:
            content_type = cls["content_type"] or ""
            try:
                elements = json.loads(cls["content_elements"] or "[]")
            except Exception:
                elements = []
            try:
                rr = json.loads(cls["reasons"] or "{}")
                evidence = rr.get("evidence", {}) if isinstance(rr, dict) else {}
            except Exception:
                evidence = {}

        return {
            "asset_id": asset_id,
            "content_type": content_type,
            "elements": elements or [],
            "evidence": evidence or {},
            "asr": " ".join(asr_parts)[:2000],
            "ocr": " ".join(ocr_parts)[:2000],
            "scenes": scenes or [],
            "has_talk": len(" ".join(asr_parts).strip()) >= 12,
        }

    # ------------------------------------------------------------------
    # 五维评分（V2：类型基准 + 特征微调 + 低价值惩罚）
    # ------------------------------------------------------------------

    # 空洞话术（有讲解但无干货 → 重扣）
    EMPTY_TALK = ["没问题", "直接冲", "不翻车", "很高级", "很好看", "很漂亮",
                  "超好看", "颜值", "哇塞", "绝了", "喜欢", "满意", "好看"]

    # 真实信息词（ASR 含这些才证明有内容密度）
    REAL_INFO = ["尺寸", "高度", "厚度", "公分", "厘米", "收纳", "抽屉", "伸缩",
                 "插座", "岩板", "材质", "颜色", "设计", "功能", "工艺", "动线",
                 "规划", "布局", "方案", "小户型", "空间", "轨道", "隐藏",
                 "搭配", "配色", "台面", "岛台", "细节", "颜色搭配"]

    def _score_dims(self, f: dict) -> tuple[dict, dict]:
        """基于内容类型基准分 + 元素/关键词微调 + 低价值惩罚。"""
        base = TYPE_BASE.get(f["content_type"], 30)
        t = f["asr"] + " " + f["ocr"]
        # 繁简归一化（行业词多为简体）
        try:
            from treecut.cognitive.industry import simplify_traditional
            t = simplify_traditional(t)
        except Exception:
            pass
        # 去除品牌水印（OCR 常含"XX宝岛台/品控"等，不算真实信息）
        import re
        t = re.sub(r"[\u4e00-\u9fff]宝岛台", " ", t)
        for watermark in ("坤宝", "品控", "成就非凡", "绅宝", "峰宝"):
            t = t.replace(watermark, " ")
        elem = set(f["elements"])

        # 各维起始 = 类型基准按权重比例拆分
        total_w = sum(self.DIM_WEIGHTS.values())
        dims = {k: base * (w / total_w) for k, w in self.DIM_WEIGHTS.items()}
        reasons = {k: [f"类型基准: {f['content_type']} ({base}分)"] for k in dims}

        # --- 低价值惩罚（先扣） ---
        # 1) 空镜无讲解 → 按类型区分（人工对功能/产品展示空镜给 65-75，认可产品价值）
        if not f["has_talk"]:
            if f["content_type"] in ("功能展示", "产品展示", "客户案例"):
                # 有产品/功能主体的空镜：产品价值/信任保留，用户/传播小扣
                dims["user_value"] *= 0.75
                dims["comm_value"] *= 0.75
                reasons["user_value"].append("空镜(有产品主体) ×0.75")
                reasons["comm_value"].append("空镜(有产品主体) ×0.75")
            else:
                # 产品介绍类空镜：重扣
                dims["user_value"] *= 0.45
                dims["comm_value"] *= 0.5
                reasons["user_value"].append("空镜无讲解 ×0.45")
                reasons["comm_value"].append("空镜无讲解 ×0.5")
        # 2) 有讲解但无真实信息（空洞话术）→ 用户价值/传播价值重扣 + 总分封顶
        no_real = not any(k in t for k in self.REAL_INFO)
        has_product_signal = any(k in t for k in ("岛台", "台面", "导台", "中岛",
                                                  "柜", "抽屉", "岩板", "桌"))
        # 承诺句式（"保证你…没问题/十年…"）视为空洞
        promise = any(p in t for p in ("没问题", "保证", "十年之后", "直接用"))
        empty_talk = (no_real and not has_product_signal) \
                     or (promise and not any(k in t for k in ("尺寸", "收纳", "材质", "功能", "设计")))
        if f["has_talk"] and empty_talk:
            dims["user_value"] *= 0.4
            dims["comm_value"] *= 0.5
            reasons["user_value"].append("讲解但无真实信息/承诺话术 ×0.4")
            reasons["comm_value"].append("讲解但无真实信息 ×0.5")
            # 空洞承诺：无论类型基准多高，总分封顶 40（人工对空洞素材打 10-40 分）
            self._cap_total = 40.0
        else:
            self._cap_total = 100.0
        # 3) 空洞话术命中 → 传播价值扣
        empty_hits = [k for k in self.EMPTY_TALK if k in t]
        if empty_hits and no_real:
            dims["comm_value"] = max(2, dims["comm_value"] - 6)
            reasons["comm_value"].append(f"空洞话术 {empty_hits[:3]} -6")
        # --- 元素加分（封顶） ---
        for dim, bonuses in ELEMENT_BONUS.items():
            for el, bonus in bonuses.items():
                if el in elem and dims[dim] < self.DIM_WEIGHTS[dim]:
                    dims[dim] = min(self.DIM_WEIGHTS[dim], dims[dim] + bonus)
                    reasons[dim].append(f"元素[{el}] +{bonus}")

        # --- 关键词加分 ---
        for dim, kws in KEYWORD_HINTS.items():
            hits = [k for k in kws if k in t]
            if hits:
                bonus = min(6, 1.5 * len(hits))
                dims[dim] = min(self.DIM_WEIGHTS[dim], dims[dim] + bonus)
                reasons[dim].append(f"关键词 {hits[:4]} +{bonus}")

        # 有实质讲解且含真实信息 → 用户价值+传播价值加成
        if f["has_talk"] and any(k in t for k in self.REAL_INFO):
            dims["user_value"] = min(25, dims["user_value"] + 2)
            dims["comm_value"] = min(20, dims["comm_value"] + 2)
            reasons["user_value"].append("有实质讲解+真实信息 +2")
            reasons["comm_value"].append("有实质讲解+真实信息 +2")

        dims = {k: round(max(0, v), 1) for k, v in dims.items()}
        return dims, reasons

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def score_asset(self, asset_id: str, persist: bool = True) -> dict:
        f = self._get_features(asset_id)
        self._cap_total = 100.0
        dims, reasons = self._score_dims(f)
        total = round(sum(dims.values()), 1)
        total = min(total, self._cap_total)  # 空洞素材封顶
        pool_class, pool_reason = self._classify_pool(total, f)
        result = {
            "asset_id": asset_id,
            "dims": dims,
            "total": total,
            "pool_class": pool_class,
            "pool_reason": pool_reason,
            "reasons": reasons,
            "content_type": f["content_type"],
        }
        if persist:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
            conn.execute(
                "INSERT OR REPLACE INTO content_value(asset_id,user_value,product_merit,"
                "trust_value,comm_value,deal_value,total_score,pool_class,pool_reason,computed_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (asset_id, dims["user_value"], dims["product_merit"],
                 dims["trust_value"], dims["comm_value"], dims["deal_value"],
                 total, pool_class, pool_reason, time.time()))
            conn.commit()
            conn.close()
        return result

    def _classify_pool(self, total: float, f: dict) -> tuple[str, str]:
        if total >= 70 and (f["has_talk"] or f["content_type"] in ("客户案例", "产品介绍")):
            return "A", "直接可生产：高价值且内容完整"
        if total >= 55:
            return "B", "需要组合：中价值，需与其他素材组合成片"
        if total >= 40:
            return "C", "备用素材：保留备用"
        return "D", "低价值：不推荐使用"

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------

    def batch_score(self, asset_ids: list[str], progress=None) -> dict:
        by_class = {"A": 0, "B": 0, "C": 0, "D": 0}
        scores = []
        for i, aid in enumerate(asset_ids):
            try:
                r = self.score_asset(aid)
                by_class[r["pool_class"]] = by_class.get(r["pool_class"], 0) + 1
                scores.append(r["total"])
            except Exception as e:
                print(f"  [value fail] {aid[:12]}: {e}")
            if progress and (i + 1) % 500 == 0:
                progress(f"价值评分 {i + 1}/{len(asset_ids)}")
        return {
            "processed": len(asset_ids),
            "by_class": by_class,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        }

    def pool_status(self) -> dict:
        conn = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT pool_class, COUNT(*), AVG(total_score) FROM content_value "
            "GROUP BY pool_class").fetchall()
        conn.close()
        return {r[0]: {"count": r[1], "avg": round(r[2], 1) if r[2] else 0} for r in rows}

    def reset(self) -> None:
        """清空评分结果（重算时用）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute("DELETE FROM content_value")
        conn.commit()
        conn.close()
