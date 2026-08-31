# -*- coding: utf-8 -*-
"""V0.3 — 验证 unit/search 各页响应（pageNum + 首个 unitId）。"""
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
            resp_by_req = {}
            req_page = {}

            def on_request(request):
                try:
                    if "unit/search" not in (request.url or ""):
                        return
                    import json as _j
                    try:
                        pd = _j.loads(request.post_data or "{}")
                    except Exception:
                        return
                    req_page[id(request)] = pd.get("pageNum")
                except Exception:
                    pass

            def on_response(response):
                try:
                    if "unit/search" not in (response.url or ""):
                        return
                    body = response.json()
                    pn = (body.get('data') or {}).get('pageNum')
                    lst = (body.get('data') or {}).get('list') or []
                    key = id(response.request)
                    resp_by_req[key] = (pn, len(lst), lst[0].get('unitId') if lst else None,
                                        lst[0].get('unitName', '')[:16] if lst else '')
                except Exception:
                    pass

            tab.on("request", on_request)
            tab.on("response", on_response)
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            resp_by_req.clear()
            req_page.clear()
            for pnum in (2, 3):
                try:
                    tab.locator(".d-pagination-page").filter(has_text=str(pnum)).first.click(timeout=8000, force=True)
                    time.sleep(5)
                except Exception as e:
                    print(f"click {pnum} fail", str(e)[:60])
            tab.remove_listener("request", on_request)
            tab.remove_listener("response", on_response)
            for rid, pn in req_page.items():
                r = resp_by_req.get(rid)
                print(f"request pageNum={pn} -> response: {r}")
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("RESP_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
