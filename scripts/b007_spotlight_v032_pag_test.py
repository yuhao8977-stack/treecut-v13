# -*- coding: utf-8 -*-
"""V0.3.2 — 测试：页大小选项 + 下一页按钮 + 跳至页。"""
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
            tab.goto(NOTE_REPORT, timeout=60000)
            time.sleep(9)
            # 1) 打开页大小选择器看选项
            try:
                loc = tab.locator(".d-select-wrapper").first
                loc.click(timeout=8000, force=True)
                time.sleep(2)
                opts = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('.d-select-option, [class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
                      const out=[];
                      for (const e of els) {
                        const t=(e.textContent||'').trim();
                        if (/条|页/.test(t) && t.length<=12) {
                          const r=e.getBoundingClientRect();
                          if (r.width>0 && r.height>0) out.push({t:t, cls:(e.className||'').toString().slice(0,50)});
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.t+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,12);
                    }""")
                print("PAGE_SIZE_OPTIONS =", json.dumps(opts, ensure_ascii=True))
                # 选 100 条/页（若存在）
                sel = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('[class*=select-option], [class*=dropdown] li, [class*=dropdown] div'));
                      const t = els.find(e => (e.textContent||'').trim() === '100 条/页');
                      if (t) { t.click(); return true; }
                      return false;
                    }""")
                print("SELECT_100 =", sel)
                if sel:
                    time.sleep(6)
                    cur = tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? (p.textContent||'').trim().slice(0,60) : 'none'; }")
                    print("AFTER_100_PAG =", cur)
            except Exception as e:
                print("size test fail", str(e)[:100])
            # 2) 下一页按钮测试（icon 按钮，非数字）
            try:
                nxt = tab.evaluate(
                    """() => {
                      const pages = Array.from(document.querySelectorAll('.d-pagination-page'));
                      for (const p of pages) {
                        const t=(p.textContent||'').trim();
                        const disabled = p.hasAttribute('disabled') || /disabled/.test(p.className||'');
                        if (!t && !disabled && p.querySelector('svg, .d-icon')) {
                          p.click(); return true;
                        }
                      }
                      return false;
                    }""")
                print("CLICK_NEXT_ICON =", nxt)
                time.sleep(5)
                cur = tab.evaluate("() => { const p=document.querySelector('.d-pagination'); return p ? (p.textContent||'').trim().slice(0,60) : 'none'; }")
                print("AFTER_NEXT_PAG =", cur)
            except Exception as e:
                print("next fail", str(e)[:80])
            # 3) 跳至页测试
            try:
                j = tab.evaluate(
                    """() => {
                      const input = Array.from(document.querySelectorAll('input')).find(i => /跳/.test(i.closest('div') ? (i.closest('div').textContent||'') : ''));
                      return !!input;
                    }""")
                print("JUMP_INPUT_EXISTS =", j)
            except Exception:
                print("JUMP_INPUT_EXISTS = unknown")
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG_FIX_TEST_DONE")


if __name__ == "__main__":
    sys.exit(main())
