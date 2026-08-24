"""AI Business Cognitive System — Layer 5 账号 DNA 适配度引擎。

根据素材特征（产品/材料/功能/内容类型/场景）与账号 DNA 的高/中/低价值特征，
计算素材对该账号的适配度评分 account_fit（0-100）。

评分逻辑：
  high_value 命中：+ 权重（高价值特征，如客户案例/尺寸/功能/收纳/真实空间）
  mid_value  命中：+ 中等权重（材质介绍/工厂展示）
  low_value  命中：- 惩罚（纯生产过程/无产品说明/空镜）
  归一化到 0-100，并给出原因（命中的特征列表）。
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from treecut.cognitive.store import CognitiveStore


@dataclass
class AccountFitResult:
    asset_id: str
    account_id: str
    account_name: str
    fit_score: float          # 0-100
    high_hits: list[str] = field(default_factory=list)
    mid_hits: list[str] = field(default_factory=list)
    low_hits: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "fit_score": round(self.fit_score, 1),
            "high_hits": self.high_hits,
            "mid_hits": self.mid_hits,
            "low_hits": self.low_hits,
            "reasons": self.reasons,
        }


class AccountEngine:
    """账号适配度引擎。"""

    def __init__(self, db_path: str | Path | None = None):
        self.store = CognitiveStore(db_path)
        self.store.ensure_schema()

    # ------------------------------------------------------------------

    def _load_accounts(self) -> list[dict]:
        return self.store.list_accounts()

    def _feature_text(self, asset_id: str) -> str:
        """构建素材特征文本（ASR + OCR + 内容类型 + 产品/材料/功能）。"""
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
        # 内容分类 reasons（含产品/材料/功能命中）
        cls = conn.execute(
            "SELECT content_type, reasons FROM content_classification WHERE asset_id=?",
            (asset_id,)).fetchone()
        if cls:
            parts.append(cls["content_type"])
            try:
                reasons = json.loads(cls["reasons"])
                for key in ("products", "materials", "functions"):
                    parts.extend(reasons.get(key, []))
            except Exception:
                pass
        conn.close()
        return " ".join(parts)

    def _match_features(self, text: str, features: list[str]) -> list[str]:
        """素材特征文本 vs 账号特征（运营术语）的语义匹配。

        账号特征如"尺寸展示/功能展示/收纳展示/真实空间"是运营术语，
        素材文本是内容词（伸缩/抽屉/岛台）。做双向模糊匹配：
          - 直接包含：'抽屉' in '抽屉' ✓
          - 账号术语包含素材词：'收纳展示' 包含 '收纳' ✓
          - 内容类型直接匹配：'客户案例' == content_type ✓
        """
        hits = []
        for feature in features:
            if not feature:
                continue
            # 1) 素材文本包含账号特征词
            if feature in text:
                hits.append(feature)
                continue
            # 2) 账号特征的核心词（去掉 展示/案例/介绍 等后缀）出现在素材文本
            core = (feature.replace("展示", "").replace("案例", "")
                    .replace("介绍", "").replace("空间", "").replace("真实", "")
                    .strip())
            if core and len(core) >= 2 and core in text:
                hits.append(feature)
        return hits

    # ------------------------------------------------------------------

    def compute_fit(self, asset_id: str, account_id: str | None = None) -> AccountFitResult:
        """计算素材对账号（默认第一个/坤宝岛台）的适配度。

        评分：内容类型基础分 + 高/中/低价值特征命中。
        """
        accounts = self._load_accounts()
        if not accounts:
            return AccountFitResult(asset_id, "", "", 0.0, reasons=["无账号 DNA 配置"])
        account = accounts[0] if not account_id else next(
            (a for a in accounts if a["account_id"] == account_id), accounts[0])

        high = json.loads(account.get("high_value") or "[]")
        mid = json.loads(account.get("mid_value") or "[]")
        low = json.loads(account.get("low_value") or "[]")

        text = self._feature_text(asset_id)
        high_hits = self._match_features(text, high)
        mid_hits = self._match_features(text, mid)
        low_hits = self._match_features(text, low)

        # 内容类型基础分（客户案例/产品介绍是获客核心）
        content_type = self._get_content_type(asset_id)
        type_base = {"客户案例": 45, "产品介绍": 40, "装修方案": 35,
                     "避坑知识": 35, "工厂实力": 20}.get(content_type, 10)

        # 评分：内容类型基础分 + 高价值 +12/个 + 中价值 +6/个 - 低价值 -15/个
        score = type_base
        score += sum(12.0 for _ in high_hits)
        score += sum(6.0 for _ in mid_hits)
        score -= sum(15.0 for _ in low_hits)
        score = max(0.0, min(100.0, score))

        reasons = [f"内容类型: {content_type} (+{type_base})"]
        for h in high_hits[:5]:
            reasons.append(f"高价值特征: {h} (+12)")
        for m in mid_hits[:3]:
            reasons.append(f"中等特征: {m} (+6)")
        for l in low_hits[:3]:
            reasons.append(f"低价值特征: {l} (-15)")

        return AccountFitResult(
            asset_id=asset_id,
            account_id=account["account_id"],
            account_name=account.get("account_name", ""),
            fit_score=score,
            high_hits=high_hits, mid_hits=mid_hits, low_hits=low_hits,
            reasons=reasons,
        )

    def _get_content_type(self, asset_id: str) -> str:
        conn = sqlite3.connect("file:" + str(self.store.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        row = conn.execute(
            "SELECT content_type FROM content_classification WHERE asset_id=?",
            (asset_id,)).fetchone()
        conn.close()
        return row[0] if row else ""

    def batch_fit(self, asset_ids: list[str]) -> dict:
        """批量计算适配度。"""
        results = []
        for aid in asset_ids:
            results.append(self.compute_fit(aid))
        scores = [r.fit_score for r in results]
        high = sum(1 for s in scores if s >= 70)
        mid = sum(1 for s in scores if 40 <= s < 70)
        low = sum(1 for s in scores if s < 40)
        return {
            "processed": len(results),
            "avg_fit": round(sum(scores) / len(scores), 1) if scores else 0,
            "high(>=70)": high,
            "mid(40-69)": mid,
            "low(<40)": low,
            "results": [r.to_dict() for r in results],
        }
