"""P2.7: 抽检机制 — 随机 + 分类覆盖采样。

第一次抽检：100 个素材，覆盖 5 类：
  客户案例 30 / 工厂 20 / 产品细节 20 / 安装 10 / 其他 20
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

# 分类关键词（基于素材路径/文件名判断业务场景）
CATEGORY_KEYWORDS = {
    "客户案例": ["客户", "女士", "先生", "小姐", "美女", "入户", "实景", "安装完", "完工", "交付", "现场"],
    "工厂": ["工厂", "车间", "生产", "加工", "开料", "封边", "打孔", "打磨"],
    "产品细节": ["细节", "特写", "台面", "纹理", "拉手", "五金", "水波纹", "岩板", "收纳"],
    "安装": ["安装", "施工", "组装", "师傅", "搬运", "吊装"],
    "其他": [],
}


def classify_asset_path(relative_path: str) -> str:
    """按路径关键词分类素材所属业务场景。"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "其他":
            continue
        if any(k in relative_path for k in keywords):
            return category
    return "其他"


class Sampler:
    """素材抽检器：按分类配额随机抽取未审核素材。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def build_sample(self, quotas: dict[str, int] | None = None,
                     exclude_reviewed: bool = True) -> list[dict]:
        """按配额抽取素材。返回 [{asset_id, media_id, relative_path, category}]。

        quotas 默认：客户案例 30 / 工厂 20 / 产品细节 20 / 安装 10 / 其他 20。
        若某类素材不足配额，从"其他/客户案例"池补足（保证总数达标）。
        """
        quotas = quotas or {"客户案例": 30, "工厂": 20, "产品细节": 20, "安装": 10, "其他": 20}
        result = []
        seen = set()
        pool_fallback: list[dict] = []

        def _query(category: str, limit: int, exclude: set) -> list[dict]:
            with closing(self._connect()) as connection:
                reviewed_sub = ""
                if exclude_reviewed:
                    reviewed_sub = ("AND a.asset_id NOT IN "
                                    "(SELECT asset_id FROM asset_quality) ")
                if category == "其他":
                    all_kws = sum((v for k, v in CATEGORY_KEYWORDS.items() if k != "其他"), [])
                    cond = " AND ".join(
                        f"m.relative_path NOT LIKE '%{kw}%'" for kw in all_kws)
                    where = f"WHERE m.media_type='video' AND m.available=1 {reviewed_sub} AND {cond}"
                else:
                    kws = CATEGORY_KEYWORDS[category]
                    like = " OR ".join(f"m.relative_path LIKE '%{kw}%'" for kw in kws)
                    where = f"WHERE m.media_type='video' AND m.available=1 {reviewed_sub} AND ({like})"
                rows = connection.execute(
                    f"SELECT a.asset_id, m.id AS media_id, m.relative_path "
                    f"FROM assets a JOIN media_files m ON m.id=a.media_id {where} "
                    f"ORDER BY RANDOM() LIMIT ?", (limit,)).fetchall()
                return [{"asset_id": r["asset_id"], "media_id": r["media_id"],
                         "relative_path": r["relative_path"], "category": category}
                        for r in rows]

        # 按配额逐类抽取
        for category, quota in quotas.items():
            if quota <= 0:
                continue
            items = _query(category, quota * 3, seen)  # 多取一些备用
            picked = 0
            for item in items:
                if item["asset_id"] in seen:
                    continue
                seen.add(item["asset_id"])
                result.append(item)
                picked += 1
                if picked >= quota:
                    break
            if picked < quota:
                # 该类不足，记录差额待补足
                pool_fallback.extend([{"category": category}] * (quota - picked))

        # 补足差额（从客户案例/其他池随机补）
        if pool_fallback:
            fallback_items = _query("客户案例", len(pool_fallback) * 3, seen)
            for item in fallback_items:
                if item["asset_id"] in seen:
                    continue
                if not pool_fallback:
                    break
                seen.add(item["asset_id"])
                item["category"] = pool_fallback.pop(0)["category"]
                result.append(item)
        return result

    def sample_status(self, sample: list[dict]) -> dict:
        """汇总抽样构成。"""
        from collections import Counter
        cats = Counter(s["category"] for s in sample)
        return {"total": len(sample), "by_category": dict(cats)}
