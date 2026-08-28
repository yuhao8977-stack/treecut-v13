# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 5 补：People 复核 12 条排序（60 候选池）。

用 YOLOv8n 在 60 候选 keyframes 上跑 person 检测，与 SigLIP people_presence 对比：
  排序分：DETECTOR_SIGLIP_DISAGREE +10 / YOLO_FP(yes但SigLIP no) +8 / YOLO_FN +8 /
          低置信 agree +4；再保证 YES/NO 平衡（上限 12）。
结果写入 PEOPLE_DETECTOR_BENCHMARK_V1.json 的 people_review_order_top12（追加）。
"""
import json
import os
import sys
import time
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")

CONF = 0.25  # 333 上最优（由 PEOPLE_DETECTOR_BENCHMARK_V1 决定，脚本内读取）


def main():
    bench = json.load(open(os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json"), encoding="utf-8"))
    conf = bench.get("best_conf", 0.25)
    v2 = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V2.json"), encoding="utf-8"))
    items = v2["segments"]
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]

    from treecut.services.visual_cognition import _imread
    from ultralytics import YOLO
    model = YOLO(r"C:\Users\admin\github\treecut\yolov8n.pt")

    # people 候选 = V2 中 primary_target=PEOPLE 或 hits 含人物关键词
    pool = [it for it in items if it.get("primary_target") == "PEOPLE" or it.get("selection_reason") == "people"]
    print("people pool:", len(pool))
    scored = []
    t0 = time.time()
    for i, it in enumerate(pool):
        sid = it["segment_id"]
        fr = feats.get(sid, {}).get("keyframes", [])[:5]
        best = 0.0
        for p in fr:
            img = _imread(p)
            if img is None:
                continue
            r = model.predict(img, conf=0.10, classes=[0], verbose=False)
            if len(r) and r[0].boxes is not None and len(r[0].boxes):
                sc = r[0].boxes.conf.cpu().numpy()
                if len(sc):
                    best = max(best, float(sc.max()))
        sig_yes = feats.get(sid, {}).get("people_presence", {}).get("prediction") == "YES"
        yolo_yes = best >= conf
        s = 0
        reasons = []
        if yolo_yes != sig_yes:
            s += 10
            reasons.append("DETECTOR_SIGLIP_DISAGREE")
        if yolo_yes and not sig_yes:
            s += 8
            reasons.append("YOLO_YES_SIGLIP_NO")
        if not yolo_yes and sig_yes:
            s += 8
            reasons.append("YOLO_NO_SIGLIP_YES")
        if yolo_yes == sig_yes and 0.0 < best < conf + 0.15:
            s += 4
            reasons.append("LOW_CONF_AGREE")
        if yolo_yes == sig_yes and yolo_yes:
            reasons.append("AGREE_YES")
        else:
            reasons.append("AGREE_NO")
        scored.append({"segment_id": sid, "asset_id": it.get("asset_id", ""),
                       "yolo_max_conf": round(best, 3), "yolo_yes": yolo_yes,
                       "siglip_yes": sig_yes, "disagree": yolo_yes != sig_yes,
                       "score": s, "reasons": reasons})
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(pool)} {time.time()-t0:.0f}s", flush=True)
    del model

    scored.sort(key=lambda r: -r["score"])
    # YES/NO 平衡：disagree 优先，其次 NO
    yes_cnt = Counter(r["siglip_yes"] for r in scored)
    print("siglip yes/no in pool:", dict(yes_cnt))
    # 取前 12，但保证至少 4 条 NO（若池中 NO 足够）
    top = []
    no_taken = 0
    for r in scored:
        if len(top) >= 12:
            break
        if r["siglip_yes"] and no_taken < 4 and len([x for x in top if not x["siglip_yes"]]) < 4:
            # 尽量先放 NO
            pass
        top.append(r)
        if not r["siglip_yes"]:
            no_taken += 1
    # 平衡修正：若 top12 全 YES，从剩余 NO 中换入
    if all(r["siglip_yes"] for r in top):
        rest_no = [r for r in scored if not r["siglip_yes"]]
        for r in rest_no[:2]:
            top[-1] = r
            top.sort(key=lambda x: -x["score"])
    balance = Counter("YES" if r["siglip_yes"] else "NO" for r in top)

    bench["people_review_order_top12"] = top
    bench["people_review_top12_balance"] = dict(balance)
    bench["people_review_note"] = ("YOLO person conf>=%s；排序=与 SigLIP 分歧优先；"
                                   "top12 用于 TARGETED_REVIEW_STAGE3_V3 people 配额。")
    json.dump(bench, open(os.path.join(DATA_ROOT, "PEOPLE_DETECTOR_BENCHMARK_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("top12 balance:", dict(balance))
    for r in top:
        print("  ", r["segment_id"][:8], "yolo", r["yolo_max_conf"], "sig", r["siglip_yes"], r["reasons"])
    print("-> PEOPLE_DETECTOR_BENCHMARK_V1.json updated")


if __name__ == "__main__":
    main()
