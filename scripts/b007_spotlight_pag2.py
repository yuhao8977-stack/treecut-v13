# -*- coding: utf-8 -*-
"""V0.3 — 点击页码2时触发的全部端点（找主表格数据端点）。"""
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
            fired = []

            def on_response(response):
                try:
                    u = response.url or ""
                    ctype = response.headers.get("content-type") or ""
                    if "json" not in ctype:
                        return
                    fired.append(u)
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            fired.clear()
            # 点页码 2
            tab.evaluate(
                """() => {
                  const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                  for (const p of pages) {
                    const sp = p.querySelector('span');
                    const raw = sp ? (sp.textContent||'').trim() : '';
                    if (raw === '2') { p.click(); return true; }
                  }
                  return false;
                }""")
            time.sleep(6)
            # 点页码 3
            tab.evaluate(
                """() => {
                  const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                  for (const p of pages) {
                    const sp = p.querySelector('span');
                    const raw = sp ? (sp.textContent||'').trim() : '';
                    if (raw === '3') { p.click(); return true; }
                  }
                  return false;
                }""")
            time.sleep(6)
            tab.remove_listener("response", on_response)
            uniq = list(dict.fromkeys(fired))
            print("FIRED_AFTER_PAGECLICKS:")
            for u in uniq:
                print("  ", u[:180])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG2_DONE")


if __name__ == "__main__":
    sys.exit(main())
