# -*- coding: utf-8 -*-
"""V0.3.2 — 跳至页精确验证：找分页内输入 → 填3+Enter → 验证响应 pageIndex。"""
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
            resps = []

            def on_resp(r):
                try:
                    if "rtb/common/data/report" in (r.url or ""):
                        d = (r.json().get("data") or {})
                        resps.append((d.get("page") or {}).get("pageIndex"))
                except Exception:
                    pass

            tab.on("response", on_resp)
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            # 设 100/页（减少页数）
            try:
                tab.locator(".d-select-wrapper").first.click(timeout=8000, force=True)
                time.sleep(2)
                tab.evaluate("""() => { const els = Array.from(document.querySelectorAll('[class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
                  const t = els.find(e => (e.textContent||'').trim() === '100 条/页'); if (t) { t.click(); return true; } return false; }""")
                time.sleep(4)
                tab.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass
            # 分页内跳至页输入
            jump = tab.evaluate(
                """() => {
                  const pag = document.querySelector('.d-pagination');
                  if (!pag) return null;
                  const div = Array.from(pag.querySelectorAll('div')).find(d => /跳至页/.test(d.textContent||''));
                  if (!div) return null;
                  const input = div.querySelector('input');
                  return input ? {found: true} : null;
                }""")
            print("JUMP_IN_PAG =", jump)
            if jump:
                resps.clear()
                r = tab.evaluate(
                    """() => {
                      const pag = document.querySelector('.d-pagination');
                      const div = Array.from(pag.querySelectorAll('div')).find(d => /跳至页/.test(d.textContent||''));
                      const input = div.querySelector('input');
                      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                      setter.call(input, '3');
                      input.dispatchEvent(new Event('input', {bubbles:true}));
                      input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                      input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true, cancelable:true}));
                      input.dispatchEvent(new Event('change', {bubbles:true}));
                      return true;
                    }""")
                print("JUMP3 =", r)
                time.sleep(6)
                print("resps:", resps)
                act = tab.evaluate(
                    """() => {
                      const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                      for (const p of pages) {
                        const sp = p.querySelector('span');
                        const raw = sp ? (sp.textContent||'').trim() : '';
                        const m = raw.match(/\\d+/);
                        if (m && /bg-prima|active|current/i.test(p.className||'')) return m[0];
                      }
                      return 'none';
                    }""")
                print("active:", act)
            tab.remove_listener("response", on_resp)
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("JUMP2_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
