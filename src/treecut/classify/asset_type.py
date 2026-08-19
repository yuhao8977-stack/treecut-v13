"""P3: 成片/原片/半成品分类器（规则特征组合，不单独依赖 VLM）。

综合特征：硬字幕比例、切镜频率、BGM、口播完整度、时长、片头尾、画面文本。
输出：RAW / FINISHED / SEMI_FINISHED / UNKNOWN + confidence + reason_codes
"""
from __future__ import annotations


def classify_asset_type(
    *,
    duration_sec: float,
    scene_count: int,
    hard_subtitle_ratio: float,   # 有硬字幕关键帧占比 0-1
    has_speech: bool,
    has_music: bool,
    text_items: int,              # OCR 文字条数
    cut_rate: float | None = None,  # 每秒切镜数（缺省按 scene_count/duration）
) -> tuple[str, float, str]:
    """规则打分返回 (asset_type, confidence, reason_codes)。"""
    reasons: list[str] = []
    score_raw = 0.0
    score_finished = 0.0

    if cut_rate is None:
        cut_rate = scene_count / max(1.0, duration_sec)

    # 硬字幕是成片强信号
    if hard_subtitle_ratio >= 0.5:
        score_finished += 0.35
        reasons.append("hard_subtitle")
    elif hard_subtitle_ratio >= 0.2:
        score_finished += 0.15
        reasons.append("some_subtitle")

    # 切镜频率：成片通常切镜较多
    if cut_rate >= 0.3:
        score_finished += 0.2
        reasons.append("high_cut_rate")
    elif cut_rate >= 0.1:
        score_finished += 0.1
        reasons.append("mid_cut_rate")

    # 口播 + 音乐：成片常见
    if has_speech:
        score_finished += 0.2
        reasons.append("speech")
    if has_music:
        score_finished += 0.1
        reasons.append("music")

    # 画面文字多（字幕/花字）是成片信号
    if text_items >= 10:
        score_finished += 0.15
        reasons.append("rich_text")

    # 时长信号：>60s 更可能原片（长原片），<90s 成片常见
    if duration_sec > 180:
        score_raw += 0.3
        reasons.append("long_raw")
    elif duration_sec > 60:
        score_raw += 0.15
        reasons.append("mid_length")

    if score_finished >= 0.6:
        return "FINISHED", min(0.99, score_finished + 0.1), ",".join(reasons)
    if score_raw >= 0.3 and score_finished < 0.3:
        return "RAW", min(0.9, score_raw + 0.1), ",".join(reasons)
    if score_finished >= 0.3:
        return "SEMI_FINISHED", score_finished + 0.05, ",".join(reasons)
    return "UNKNOWN", max(score_raw, score_finished), ",".join(reasons or ["insufficient_features"])
