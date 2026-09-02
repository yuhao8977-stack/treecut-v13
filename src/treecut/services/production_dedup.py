"""STAGE8 — Production Dedup：时间线重复镜头拦截。

§44-§49。级别: EXACT_SEGMENT_DUPLICATE / SOURCE_TIME_OVERLAP / SAME_ASSET_NEAR_DUPLICATE /
VISUAL_NEAR_DUPLICATE(pHash) / NARRATIVE_NEAR_DUPLICATE(同演示者/同岛台/同构图/同角色)。
pHash ≤6 强候选; 7-12 需复核; 阈值可配置并记录校准, 不全局拍脑袋。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Shot:
    media_id: int
    subclip_start_s: float = 0.0
    subclip_end_s: float = 0.0
    asset_id: str | None = None
    folder_hint: str | None = None
    case_id: str | None = None      # 从文件名提取(女士/先生/城市…)
    shot_role: str | None = None    # hook/feature/cta
    actions: list = field(default_factory=list)
    phash: int | None = None


def extract_case_hint(name: str) -> str | None:
    m = re.search(r"【(\d+)】?([^【】]*(?:女士|先生|小姐|陈|王|刘|朱|陶|吴|高|于|殷|郑|周|李|邵|肖|田|山西|江苏|广州|上海|深圳|长沙|台州)[^【】]*)", name or "")
    return m.group(0)[:30] if m else None


_SURNAMES = "赖王李刘陈朱陶吴高于殷郑周邵肖田张赵黄杨徐孙马林何郭罗梁宋谢韩唐冯程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯孟龙万段雷钱汤尹黎易常武乔贺龚文"


def extract_presenter(name: str) -> str | None:
    m = re.search(rf"([{_SURNAMES}])(?:女士|先生|小姐)", name or "")
    return m.group(0) if m else None


def dct_phash_rgb_path(path, size=32) -> int | None:
    """DCT-based perceptual hash (灰度). 供视觉近重复; 失败返回 None。"""
    import cv2
    import numpy as np
    try:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        img = cv2.resize(img, (size, size))
        imgf = np.float32(img)
        dct = cv2.dct(imgf)
        low = dct[:8, :8]
        med = np.median(low)
        bits = (low > med).astype(np.uint8).flatten()
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h
    except Exception:
        return None


def phash_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def detect_duplicates(shots: list[Shot], phash_threshold_strong: int = 6,
                      phash_threshold_verify: int = 12) -> list[dict]:
    """两两检测, 返回命中 {pair, level, reason, strength}。"""
    hits = []
    n = len(shots)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = shots[i], shots[j]
            reasons = []
            # EXACT_SEGMENT / SAME_ASSET
            if a.media_id == b.media_id:
                if a.subclip_start_s == b.subclip_start_s and a.subclip_end_s == b.subclip_end_s:
                    hits.append({"pair": (i, j), "level": "EXACT_SEGMENT_DUPLICATE",
                                 "reason": "same asset & same window", "strength": "HIGH"})
                    continue
                hits.append({"pair": (i, j), "level": "SAME_ASSET_NEAR_DUPLICATE",
                             "reason": "same source asset different window", "strength": "HIGH"})
                continue
            # VISUAL_NEAR_DUPLICATE
            if a.phash is not None and b.phash is not None:
                d = phash_distance(a.phash, b.phash)
                if d <= phash_threshold_strong:
                    hits.append({"pair": (i, j), "level": "VISUAL_NEAR_DUPLICATE",
                                 "reason": f"pHash dist {d}", "strength": "HIGH"})
                    continue
                if d <= phash_threshold_verify:
                    reasons.append(f"pHash {d}(需复核)")
            # NARRATIVE_NEAR_DUPLICATE: 同演示者/同案例提示/同功能文件夹/同角色
            score = 0
            if a.case_id and b.case_id and a.case_id == b.case_id:
                score += 2
            if extract_presenter_from_case(a.case_id) and extract_presenter_from_case(b.case_id) and \
                    extract_presenter_from_case(a.case_id) == extract_presenter_from_case(b.case_id):
                score += 2
            if a.folder_hint and b.folder_hint and a.folder_hint == b.folder_hint:
                score += 1
            if a.shot_role and b.shot_role and a.shot_role == b.shot_role:
                score += 1
            if score >= 3:
                hits.append({"pair": (i, j), "level": "NARRATIVE_NEAR_DUPLICATE",
                             "reason": f"narrative overlap score {score}: {reasons[:2]}", "strength": "WARNING"})
    return hits


def extract_presenter_from_case(case: str | None) -> str | None:
    return extract_presenter(case)


def narrative_score(a: Shot, b: Shot) -> int:
    score = 0
    pa, pb = extract_presenter_from_case(a.case_id), extract_presenter_from_case(b.case_id)
    if pa and pb and pa == pb:
        score += 2
    if a.case_id and b.case_id and a.case_id == b.case_id:
        score += 2
    if a.folder_hint and b.folder_hint and a.folder_hint == b.folder_hint:
        score += 1
    if a.shot_role and b.shot_role and a.shot_role == b.shot_role:
        score += 1
    return score
