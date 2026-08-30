# -*- coding: utf-8 -*-
"""Stage 3A.4 — PlatformReferenceAssetV1 模型 + Pilot20 + Media Recovery 输出集。

诚实状态：
  已有数据仅含 duration（155 条，METADATA_ONLY）
  cover / actual Published Video 未保存 → 需用户 Creator 后台补充
  Z 盘不做正向候选，仅未来 Reverse Match
"""
import io
import json
import os
import random
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"

inv = json.load(open(os.path.join(DATA_ROOT, "B003_PUBLISHED_CONTENT_INVENTORY_V3.json"), encoding="utf-8"))
notes = [r for r in inv["records"] if r["note_id"]]
perf = json.load(open(os.path.join(DATA_ROOT, "B003_PERFORMANCE_SNAPSHOTS_V3.json"), encoding="utf-8"))
perf_by_note = {s["note_id"]: s for s in perf["snapshots"]}


def main():
    # ---- Platform Reference Assets（基于现有数据：duration 为唯一媒体元数据）----
    refs = []
    for n in notes:
        p = perf_by_note.get(n["note_id"], {})
        refs.append({
            "platform_reference_asset_id": f"PRA-B003-{n['note_id'][:16]}",
            "platform": "XIAOHONGSHU", "account_id": "B003",
            "published_content_id": n["published_content_id"], "note_id": n["note_id"],
            "media_type": n.get("content_type") or "video",
            "published_duration": float(n["duration"]) if n.get("duration") else None,
            "cover_url": None, "thumbnail_url": None, "platform_media_id": None,
            "reference_local_path": None,
            "exact_media_hash": None, "perceptual_video_hash": None, "audio_fingerprint": None,
            "source_refs": n["source_refs"],
            "retrieved_at": None, "retrieval_method": "METADATA_ONLY",
            "identity_confidence": n["identity_confidence"],
            "recovery_status": "METADATA_ONLY",  # 仅有 duration
        })
    json.dump({"manifest": "B003_PLATFORM_REFERENCE_ASSETS_V1", "count": len(refs), "assets": refs},
              open(os.path.join(DATA_ROOT, "B003_PLATFORM_REFERENCE_ASSETS_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Media Recovery Inventory ----
    rec = {
        "manifest": "B003_PLATFORM_MEDIA_RECOVERY_INVENTORY_V1",
        "generated_at": "2026-08-30",
        "existing_media_metadata": {
            "duration_available": 155, "cover_available": 0, "video_available": 0,
            "thumbnail_available": 0, "video_info_available": 0,
        },
        "recovery_status_distribution": {
            "EXACT_PUBLISHED_MEDIA": 0, "METADATA_ONLY": 155, "COVER_ONLY": 0, "UNAVAILABLE": 0,
        },
        "needs_creator_backend_supplement": {
            "cover": True, "thumbnail": True, "actual_published_video": True,
            "note": "不重抓 Performance；只补媒体元数据（§10）",
        },
        "credential_security": "不持久保存 cookie/auth/xsec_token；仅临时合法恢复媒体 resource",
    }
    json.dump(rec, open(os.path.join(DATA_ROOT, "B003_PLATFORM_MEDIA_RECOVERY_INVENTORY_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Media Metadata（duration 为当前全部）----
    meta = {"manifest": "B003_PUBLISHED_MEDIA_METADATA_V1", "generated_at": "2026-08-30",
            "notes_with_duration": 155, "notes_with_cover": 0, "notes_with_video": 0,
            "duration_source": "API 身份表（note_id 身份表 duration 列）",
            "records": [{"note_id": n["note_id"], "title": n["title"],
                         "duration": n.get("duration"), "media_type": n.get("content_type"),
                         "cover_url": None, "video_info": None} for n in notes]}
    json.dump(meta, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_MEDIA_METADATA_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Cover Registry（空——无 cover 数据）----
    json.dump({"manifest": "B003_PUBLISHED_COVER_REGISTRY_V1", "generated_at": "2026-08-30",
               "total": 0, "note": "无 cover URL 可保存（API 身份源未含 cover 字段）；"
                                   "需 Creator 后台补充或临时 URL 下载 Reference Cover",
               "records": []},
              open(os.path.join(DATA_ROOT, "B003_PUBLISHED_COVER_REGISTRY_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Pilot20（分层：高/中/低表现 × duration/时间/类型，非按恢复难度）----
    # 按表现分层：用 views 排序（proxy），取高/中/低各一段
    notes_sorted = sorted(notes, key=lambda n: int(perf_by_note.get(n["note_id"], {}).get("views") or 0), reverse=True)
    n = len(notes_sorted)
    high = notes_sorted[: n // 3]
    mid = notes_sorted[n // 3: 2 * n // 3]
    low = notes_sorted[2 * n // 3:]
    rng = random.Random(20260830)
    pilot = []
    for pool, take in ((high, 7), (mid, 7), (low, 6)):
        picked = rng.sample(pool, min(take, len(pool)))
        pilot.extend(picked)
    pilot_out = {"manifest": "B003_PUBLISHED_MEDIA_PILOT20_V1", "generated_at": "2026-08-30",
                 "selection_basis": "数据分层（views 高/中/低）+ 多样性；非按恢复难度",
                 "count": len(pilot),
                 "records": [{"note_id": n_["note_id"], "title": n_["title"],
                              "publish_time": n_["publish_time"], "duration": n_["duration"],
                              "views": perf_by_note.get(n_["note_id"], {}).get("views"),
                              "recovery_status": "METADATA_ONLY"} for n_ in pilot]}
    json.dump(pilot_out, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_MEDIA_PILOT20_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Local Reverse Match（空——无 Platform Published Video 可反查）----
    json.dump({"manifest": "B003_LOCAL_ASSET_REVERSE_MATCH_V1", "generated_at": "2026-08-30",
               "total": 0, "note": "无 EXACT_PUBLISHED_MEDIA → 无法执行 Reverse Match；"
                                   "取得真实发布视频后启用（Asset DB → Local → Z 盘）",
               "records": []},
              open(os.path.join(DATA_ROOT, "B003_LOCAL_ASSET_REVERSE_MATCH_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Repost Clusters V2（空——无 video fingerprint）----
    json.dump({"manifest": "B003_REPOST_CLUSTERS_V2", "generated_at": "2026-08-30",
               "clusters": [], "note": "需 Platform Video fingerprint 才能检测同视频重发；"
                                       "当前无 Published Video"},
              open(os.path.join(DATA_ROOT, "B003_REPOST_CLUSTERS_V2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- Join Coverage ----
    cov = {"manifest": "B003_PUBLISHED_MEDIA_JOIN_COVERAGE_V1", "generated_at": "2026-08-30",
           "coverage": {"published_to_platform_media_metadata": 155 / 155,
                        "published_to_cover": 0.0, "published_to_actual_video": 0.0,
                        "published_to_local_asset": 0.0, "published_to_segment": 0.0,
                        "published_to_cognition": 0.0},
           "status": "STAGE3A4_PUBLISHED_MEDIA_ROUTE_METADATA_ONLY（缺 cover/实际视频）"}
    json.dump(cov, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_MEDIA_JOIN_COVERAGE_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("-> 8 个输出已生成")
    print(f"Pilot20: {len(pilot)} 条（METADATA_ONLY）")
    print("当前状态: METADATA_ONLY（155 duration）；cover/实际视频需 Creator 后台补充")


if __name__ == "__main__":
    main()
