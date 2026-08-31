# -*- coding: utf-8 -*-
"""V0.3 — 分页点击精确验证：点页码2 → 观察 unit/search pageNum。"""
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
                    hits.append((pn, u.split('?')[1][:120] if '?' in u else ''))
                except Exception:
                    pass

            tab.on("response", on_response)
            tab.goto(UNIT_PAGE, timeout=60000)
            time.sleep(8)
            hits.clear()
            # 点页码 2
            clicked = tab.evaluate(
                """() => {
                  const pages = Array.from(document.querySelectorAll('.d-pagination-page, [class*=pagination-page]'));
                  for (const p of pages) {
                    const sp = p.querySelector('span');
                    const raw = sp ? (sp.textContent||'').trim() : (p.textContent||'').trim();
                    if (raw.trim() === '2' || raw.trim() === '02') { p.click(); return true; }
                  }
                  return false;
                }""")
            print("CLICK_PAGE2 =", clicked)
            time.sleep(5)
            print("HITS after click =", hits)
            # 当前 active 页码
            try:
                act = tab.evaluate(
                    """() => {
                      const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                      for (const p of pages) {
                        if (/bg-prima|active|current/i.test(p.className||'')) {
                          const sp = p.querySelector('span');
                          return sp ? (sp.textContent||'').trim() : (p.textContent||'').trim();
                        }
                      }
                      return 'none';
                    }""")
                print("ACTIVE_PAGE =", act)
            except Exception as e:
                print("act fail", str(e)[:60])
            tab.remove_listener("response", on_response)
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
