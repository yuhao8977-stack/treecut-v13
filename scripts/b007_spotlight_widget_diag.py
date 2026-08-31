# -*- coding: utf-8 -*-
"""V0.3.1 — dump 笔记报表日期控件（class/input/aria）。"""
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
            try:
                info = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('input, [class*=date], [class*=time], [class*=range], [class*=picker], [class*=calendar], [role=combobox], [class*=select]'));
                      for (const e of els) {
                        const r = e.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                          const t = (e.textContent||'').trim().slice(0,30);
                          const ph = e.getAttribute && e.getAttribute('placeholder');
                          out.push({tag: e.tagName, cls: (e.className||'').toString().slice(0,80),
                                    text: t, ph: ph || '', val: (e.value || e.getAttribute('value') || '').toString().slice(0,30)});
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.tag+'|'+x.cls+'|'+x.val; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,25);
                    }""")
                print("DATE_WIDGETS =", json.dumps(info, ensure_ascii=True))
            except Exception as e:
                print("fail", str(e)[:80])
            # 也 dump 所有含“至”附近的文本元素
            try:
                around = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('*'));
                      const hits = [];
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (t === '至' && e.children.length <= 1) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0) {
                            const parent = e.parentElement;
                            hits.push({parent_cls: parent ? (parent.className||'').toString().slice(0,80) : '',
                                       parent_text: parent ? (parent.textContent||'').trim().slice(0,50) : ''});
                          }
                        }
                      }
                      return hits.slice(0,8);
                    }""")
                print("AROUND_ZHI =", json.dumps(around, ensure_ascii=True))
            except Exception as e:
                print("zhi fail", str(e)[:60])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("WIDGET_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
