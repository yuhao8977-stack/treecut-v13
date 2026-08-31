# -*- coding: utf-8 -*-
"""V0.3.1 — 笔记报表请求体（时间范围参数）+ 工具栏 dump。"""
from __future__ import annotations

import json
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

        def probe():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            reqs = []

            def on_request(request):
                try:
                    if "rtb/common/data/report" in (request.url or ""):
                        reqs.append(request.post_data or "")
                except Exception:
                    pass

            tab.on("request", on_request)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            tab.remove_listener("request", on_request)
            print("REQ_BODIES:")
            for r in reqs:
                print("  ", r[:600])
            # 工具栏文本（前 600 字符）
            try:
                head = tab.evaluate("() => (document.body.innerText||'').slice(0, 900)")
                print("HEAD =", json.dumps(head, ensure_ascii=True)[:900])
            except Exception:
                pass
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("REQ_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
