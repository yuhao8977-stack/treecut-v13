# -*- coding: utf-8 -*-
"""Stage 3A.4 — STAGE3A3_HUMAN_CORRECTION_V2 + Z_LEGACY_MEDIA_POOL_REGISTRY_V1。

Z 盘认知修正：
  不是 B003 成片库（SUPERSEDED 旧假设）
  不是一律排除（单文件可经 PublishedTruth→ReverseMatch 确认）
  = LEGACY_MIXED_MEDIA_POOL
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"


def main():
    # ---- STAGE3A3_HUMAN_CORRECTION_V2 ----
    corr = {
        "manifest": "STAGE3A3_HUMAN_CORRECTION_V2",
        "generated_at": "2026-08-30",
        "human_confirmed": {
            "z_drive_is_b003_published_library": False,
            "z_drive_nature": "LEGACY_MIXED_MEDIA_POOL — 历史遗留混合媒体盘：旧剪辑/所谓成片/杂乱素材/来源不明/多账号多阶段/可能重复",
            "b003_files_may_exist_sparsely": "TRUE / POSSIBLE（1-2 条或少量）",
            "b003_prior_probability": "LOW_BUT_NONZERO",
        },
        "superseded": [
            {"id": "STAGE3A3_ASSUMPTION-1",
             "old": "Z:\\B组更新视频 整体视为 B003 候选池",
             "new": "Z_GROUP_AS_B003_CANDIDATE_POOL = SUPERSEDED；仅 LEGACY_MIXED_MEDIA_POOL 子池"},
            {"id": "STAGE3A3_ASSUMPTION-2",
             "old": "duration(±1.5s) 匹配可建立候选",
             "new": "仅 Metadata_HINT；不能作为账号身份 Truth（128/136 多候选）"},
            {"id": "STAGE3A3_ASSUMPTION-3",
             "old": "Z 盘 360 文件可作 B003 正向候选",
             "new": "默认不参与正向候选；仅 PublishedTruth→ReverseMatch 允许"},
        ],
        "kept": {
            "B003_Z_GROUP_ASSETS_V1": "保留（360 file inventory，ffprobe 只读）",
            "single_file_reverse_match_possible": True,
            "search_direction": "B003 note_id → Platform Published Media → fingerprint → Local/Z reverse search",
        },
        "guard": "账号归属是证据关系，不是文件夹属性；目录名（B组/成片/已发）只作 METADATA_HINT",
    }
    json.dump(corr, open(os.path.join(DATA_ROOT, "STAGE3A3_HUMAN_CORRECTION_V2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Z_LEGACY_MEDIA_POOL_REGISTRY ----
    reg = {
        "manifest": "Z_LEGACY_MEDIA_POOL_REGISTRY_V1",
        "generated_at": "2026-08-30",
        "source_type": "LEGACY_MIXED_MEDIA_POOL",
        "account_scope": "MULTI_ACCOUNT_OR_UNKNOWN",
        "media_scope": "MIXED_RAW_EDITED_FINISHED_UNKNOWN",
        "quality_status": "MIXED_UNVERIFIED",
        "b003_prior_probability": "LOW_BUT_NONZERO",
        "identity_status": "UNVERIFIED",
        "sub_pools": [
            {"path": "Z:\\B组更新视频\\已发视频一", "files": 209, "note": "历史子池，非 B003 库"},
            {"path": "Z:\\B组更新视频\\已发视频二", "files": 118},
            {"path": "Z:\\B组更新视频\\已发视频.1", "files": 8},
            {"path": "Z:\\B组更新视频\\已发视频.2", "files": 12},
            {"path": "Z:\\B组更新视频\\已发视频三（洗稿）", "files": 13},
        ],
        "usage_policy": {
            "forward_candidate_search": "DISABLED（默认不参与 B003 正向候选）",
            "reverse_lookup": "ENABLED（仅对已确认 PlatformReferenceAsset 执行 hash/指纹/帧匹配）",
            "negative_quality_set": "NOT_IN_USE（本 Stage 不利用 Z 盘做 Negative Set）",
            "directory_as_identity": "FORBIDDEN（目录名仅 METADATA_HINT）",
        },
        "single_file_confirmation_levels": {
            "EXACT_HASH": "允许 LOCAL_COPY_OF_B003_PUBLISHED_MEDIA",
            "PERCEPTUAL_EXACT + AUDIO_MATCH": "允许",
            "HIGH_CONFIDENCE_MULTIMODAL": "允许",
            "else": "UNKNOWN",
        },
        "light_index": {"allowed": True, "fields": ["path", "size", "mtime", "hash", "duration", "media_type", "basic_fingerprint"]},
        "guard": "不整体归属任何账号；单文件未来可经真实发布视频反向证明",
    }
    json.dump(reg, open(os.path.join(DATA_ROOT, "Z_LEGACY_MEDIA_POOL_REGISTRY_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("-> STAGE3A3_HUMAN_CORRECTION_V2.json")
    print("-> Z_LEGACY_MEDIA_POOL_REGISTRY_V1.json")


if __name__ == "__main__":
    main()
