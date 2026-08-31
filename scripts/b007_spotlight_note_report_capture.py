# -*- coding: utf-8 -*-
"""V0.3.1 — 分析 leona/rtb/common/data/report 完整字段（note 级指标判断）。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_REPORT = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/note"

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    config = load_config()
    config.workspace_id = "B007"
    config.validate()
    runtime = BrowserRuntime(config)
    try:
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2
    try:
        runtime.start_browser(headless=False)
        out_dir = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                       r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_note_report")
        out_dir.mkdir(parents=True, exist_ok=True)

        def probe():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            bodies = {}

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    body = response.json()
                except Exception:
                    return
                s = _safe(u)
                if any(k in s for k in ("rtb/common/data/report", "ad/report/data", "rtb/data/overall",
                                        "data/choose/tree", "rtb/data/custom")):
                    bodies.setdefault(s, body)

            tab.on("response", on_response)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(8)
            # 滚动触发更多（分页/懒加载）
            for _ in range(4):
                try:
                    tab.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                except Exception:
                    pass
            tab.remove_listener("response", on_response)
            for ep, body in bodies.items():
                name = re.sub(r"[^a-z0-9]+", "_", ep.replace("ad.xiaohongshu.com/api/", "")) + ".json"
                (out_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"SAVED {name} ({len(json.dumps(body))} chars)")
            print(f"OUT_DIR = {out_dir}")
            return sorted(bodies.keys())
        eps = runtime._in_browser(probe, timeout=400)
        print("EPS =", eps)
        return 0
    finally:
        runtime.close()
        print("NOTE_REPORT_CAPTURE_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
