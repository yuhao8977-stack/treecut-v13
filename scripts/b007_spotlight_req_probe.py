# -*- coding: utf-8 -*-
"""V0.3 — 抓 unit/search 请求体（POST body）跨页码点击。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

UNIT_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/unit"

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
                    if "unit/search" in (request.url or ""):
                        pd = request.post_data or ""
                        reqs.append(pd[:400])
                except Exception:
                    pass

            tab.on("request", on_request)
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            reqs.clear()
            # 点页码 2（真实点击）
            try:
                tab.locator(".d-pagination-page").filter(has_text="2").first.click(timeout=8000, force=True)
            except Exception as e:
                print("click2 fail", str(e)[:80])
            time.sleep(5)
            print("REQS after page2 click:")
            for r in reqs:
                print("  ", r)
            # 点页码 3
            try:
                tab.locator(".d-pagination-page").filter(has_text="3").first.click(timeout=8000, force=True)
            except Exception as e:
                print("click3 fail", str(e)[:80])
            time.sleep(5)
            print("REQS after page3 click:")
            for r in reqs:
                print("  ", r)
            tab.remove_listener("request", on_request)
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("REQ_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
