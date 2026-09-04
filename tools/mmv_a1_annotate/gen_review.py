# -*- coding: utf-8 -*-
"""MMVV A1 — 人工最终核验 HTML 生成（§19：人工先看框，再决定 A2）。
用法: python tools/mmv_a1_annotate/gen_review.py
"""
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json"
ROI_FILE = OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json"
FRAMES_DIR = json.loads(MANIFEST.read_text(encoding="utf-8")).get("frames_dir")

# 显示层中文映射（内部值不变）
LABEL_CN = {"TABLETOP": "桌板/台面", "EXTENSION_TABLETOP": "伸缩桌板", "DRAWER": "抽屉",
            "UPPER_THIN_DRAWER": "上层薄抽", "TRACK_SOCKET": "轨道插座", "SOCKET_MODULE": "插座模块",
            "PERSON": "人", "HAND": "手", "ISLAND_BODY": "岛台主体", "OTHER_MOVING_PART": "其他运动部件"}
REQ_CN = {"EXTEND": "拉出/伸出", "RETRACT": "收回", "DRAWER_OPEN": "抽屉打开",
          "SOCKET_INSERT": "插入插座", "SOCKET_ADJUST": "调整插座"}


def main():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rois = json.loads(ROI_FILE.read_text(encoding="utf-8"))["annotations"]
    blocks = []
    total_boxes = 0
    for c in man["cases"]:
        frames_html = []
        for f in c["frames"]:
            if "error" in f:
                continue
            rs = [a for a in rois if a["media_id"] == c["media_id"] and a["frame_timestamp"] == f["t_s"]]
            total_boxes += len(rs)
            svg_boxes = "".join(
                f'<rect x="{a["bbox_pixel"][0]}" y="{a["bbox_pixel"][1]}" '
                f'width="{a["bbox_pixel"][2]-a["bbox_pixel"][0]}" '
                f'height="{a["bbox_pixel"][3]-a["bbox_pixel"][1]}" fill="none" stroke="#ff3b30" stroke-width="3"/>'
                f'<text x="{a["bbox_pixel"][0]+6}" y="{a["bbox_pixel"][1]+24}" fill="#ff3b30" font-size="24" '
                f'style="font-family:\'Microsoft YaHei\',sans-serif">{LABEL_CN.get(a["object_name"], a["object_name"])}</text>'
                for a in rs)
            img = (Path(FRAMES_DIR) / f["frame"]).as_uri() if FRAMES_DIR else ""
            frames_html.append(f"""
            <div style="display:inline-block;margin:6px;vertical-align:top">
              <div>{f['frame'].replace('.jpg','')} @ {f['t_s']}s · {len(rs)}框</div>
              <div style="position:relative;display:inline-block">
                <img src="{img}" style="width:360px"/>
                <svg style="position:absolute;left:0;top:0;width:360px;height:{round(360*f['height']/f['width'])}px" viewBox="0 0 {f['width']} {f['height']}">{svg_boxes}</svg>
              </div>
            </div>""")
        facts = c.get("human_facts") or {}
        blocks.append(f"""
        <h2 style="border-bottom:2px solid #333;padding-bottom:4px">测试视频 {c['media_id']} · 要验证：{REQ_CN.get(c['requested'], c['requested'])} · 窗口[{c['frozen_window_s'][0]},{c['frozen_window_s'][1]}]秒</h2>
        <p style="font-size:13px">已知人工结论(独立字段): {json.dumps(facts, ensure_ascii=False)}</p>
        <div>{''.join(frames_html) or '<p>无帧</p>'}</div>""")
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>MMVV A1 Human GT ROI Review</title></head>
<body style="font-family:'Microsoft YaHei',sans-serif;max-width:1400px;margin:20px auto;padding:0 16px">
<h1>MMVV A1 Human GT ROI — 人工核验（§19）</h1>
<p>生成 {time.strftime('%Y-%m-%d %H:%M:%S')} · 总框数 {total_boxes} · <b>请人工逐帧确认框位置与标签后再批准 A2。</b></p>
{''.join(blocks)}
</body></html>"""
    (OUT / "TREECUT_MMVV_A1_HUMAN_GT_ROI_REVIEW.html").write_text(html, encoding="utf-8")
    print("review html OK, boxes =", total_boxes)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
