# -*- coding: utf-8 -*-
"""V0.3 — Playwright 真实点击页码2 → 观察 unit/search pageNum。"""
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
            hits = []

            def on_response(response):
                try:
                    u = response.url or ""
                    if "unit/search" not in u:
                        return
                    body = response.json()
                    pn = (body.get('data') or {}).get('pageNum')
                    lst = (body.get('data') or {}).get('list') or []
                    hits.append((pn, len(lst), lst[0].get('unitId') if lst else None))
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            hits.clear()
            # Playwright 真实点击页码 2
            try:
                loc = tab.locator(".d-pagination-page").filter(has_text="2").first
                print("LOC_COUNT =", loc.count())
                loc.click(timeout=8000, force=True)
                print("PW_CLICK_OK")
            except Exception as e:
                print("PW_CLICK_FAIL:", str(e)[:150])
                # 兜底：dispatch mousedown/mouseup/click
                try:
                    tab.evaluate(
                        """() => {
                          const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                          for (const p of pages) {
                            const sp = p.querySelector('span');
                            if (sp && (sp.textContent||'').trim() === '2') {
                              ['mousedown','mouseup','click'].forEach(t =>
                                p.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window})));
                              return true;
                            }
                          }
                          return false;
                        }""")
                    print("DISPATCH_FALLBACK_OK")
                except Exception as e2:
                    print("DISPATCH_FAIL:", str(e2)[:100])
            time.sleep(6)
            print("HITS =", hits)
            tab.remove_listener("response", on_response)
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PW_PAG_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
