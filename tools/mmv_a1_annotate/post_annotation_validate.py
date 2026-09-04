# -*- coding: utf-8 -*-
"""MMVV A1 标后校验 + 重建（架构师批准后执行；不自动进入 A2）。

用法: python tools/mmv_a1_annotate/post_annotation_validate.py
覆盖（架构师 10 点）:
1. 校验全部帧 sha256（manifest vs 磁盘）
2. 校验每条 HUMAN ROI 坐标边界
3. 确认 roi_source 仅 L3_HUMAN_ROI（无 qwen/heuristic）
4. 重建 GEOMETRY_TRAJECTORY / ANNOTATION_STATE / REVIEW.html
5. 报告按案例/帧缺失的必需 ROI
6-8. 不使用 qwen/heuristic；不调阈值
9. 不运行 A2
10. 输出报告 → STOP 等人工审核
"""
import hashlib, json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "mmv_a1_annotate"))
import server as a1  # noqa: E402

OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json"
ROI_FILE = OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json"
REPORT = OUT / "TREECUT_MMVV_A1_POST_VALIDATION.json"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    doc = json.loads(ROI_FILE.read_text(encoding="utf-8"))
    anns = doc["annotations"]
    issues = []

    # 1. frame hashes
    frames = [f for c in man["cases"] for f in c["frames"] if "error" not in f]
    for f in frames:
        lp = f.get("local_path")
        if not lp or not Path(lp).exists():
            issues.append({"kind": "FRAME_MISSING", "frame": f.get("frame")})
        elif sha(lp) != f["sha256"]:
            issues.append({"kind": "FRAME_HASH_MISMATCH", "frame": f.get("frame")})
    print(f"[1] frames={len(frames)}")

    # 2. ROI bounds + 3. source purity
    bad_src = [a for a in anns if a.get("annotation_source") != "L3_HUMAN_ROI"]
    if bad_src:
        issues.append({"kind": "NON_HUMAN_SOURCE", "count": len(bad_src)})
    for a in anns:
        bb = a["bbox_pixel"]
        fr = next((f for c in man["cases"] for f in c["frames"]
                   if c["media_id"] == a["media_id"] and f["t_s"] == a["frame_timestamp"]), None)
        if fr is None:
            issues.append({"kind": "ROI_ORPHAN_FRAME", "media": a["media_id"], "t": a["frame_timestamp"]})
            continue
        if not a1.bbox_ok(bb, fr["width"], fr["height"]):
            issues.append({"kind": "ROI_OUT_OF_BOUNDS", "media": a["media_id"],
                           "frame": fr["frame"], "bbox": bb})
    print(f"[2/3] annotations={len(anns)} non_human={len(bad_src)}")

    # 4. rebuild
    st = a1.refresh_state()
    import build_geometry  # noqa
    import importlib
    importlib.reload(build_geometry)
    build_geometry.main()
    import gen_review  # noqa
    importlib.reload(gen_review)
    gen_review.main()
    print("[4] geometry/state/review rebuilt")

    # 5. missing required ROI by case/frame
    missing = []
    for c in man["cases"]:
        req = a1.REQUIRED_OBJECTS.get(c["requested"], ())
        per_case_objs = {a["object_name"] for a in anns if a["media_id"] == c["media_id"]}
        for fr in c["frames"]:
            if "error" in fr:
                continue
            n = sum(1 for a in anns if a["media_id"] == c["media_id"] and a["frame_timestamp"] == fr["t_s"])
            if n == 0:
                missing.append({"media": c["media_id"], "frame": fr["frame"], "issue": "NO_BOXES"})
        absent = [r for r in req if r not in per_case_objs]
        if absent:
            missing.append({"media": c["media_id"], "issue": "REQUIRED_OBJECT_ABSENT",
                            "required": list(req), "present": sorted(per_case_objs)})
    print(f"[5] missing issues={len(missing)}")

    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "frames_total": len(frames), "frames_ok": len(frames) - len([i for i in issues if i["kind"].startswith("FRAME")]),
              "annotations": len(anns), "issues": issues, "missing_required": missing,
              "cases": st["cases"], "a1_ready": not issues and not missing,
              "a2_not_run": True}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("issues:", len(issues), "missing:", len(missing), "A1_READY:", report["a1_ready"])
    print("report ->", REPORT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
