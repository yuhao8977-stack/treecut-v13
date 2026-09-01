# -*- coding: utf-8 -*-
"""V0.3.2 — 笔记报表分页根因诊断：分页组件全结构（按钮/省略号/next/prev/page-size/跳转）。"""
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
            # 分页组件结构
            info = tab.evaluate(
                """() => {
                  const out = [];
                  const pag = document.querySelector('.d-pagination');
                  if (!pag) return {found: false};
                  const els = Array.from(pag.querySelectorAll('*'));
                  for (const e of els) {
                    const t = (e.textContent||'').trim();
                    const r = e.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                      out.push({tag: e.tagName, t: t.slice(0,12), cls: (e.className||'').toString().slice(0,70),
                                disabled: e.hasAttribute('disabled') || /disabled/.test(e.className||''),
                                aria: e.getAttribute('aria-label')||''});
                    }
                  }
                  const uniq=[]; const seen=new Set();
                  for (const x of out){ const k=x.t+'|'+x.cls+'|'+x.disabled; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                  return {found: true, items: uniq.slice(0,35)};
                }""")
            print("PAG_STRUCTURE =", json.dumps(info, ensure_ascii=True))
            # 页面大小选择器
            try:
                size = tab.evaluate(
                    """() => {
                      const els = Array.from(document.querySelectorAll('[class*=page-size],[class*=pagesize],.d-select'));
                      const out=[];
                      for (const e of els) {
                        const t=(e.textContent||'').trim();
                        if (/条|页/.test(t) && t.length<=15) {
                          const r=e.getBoundingClientRect();
                          if (r.width>0) out.push({t:t, cls:(e.className||'').toString().slice(0,60)});
                        }
                      }
                      return out.slice(0,8);
                    }""")
                print("PAGE_SIZE_UI =", json.dumps(size, ensure_ascii=True))
            except Exception as e:
                print("size fail", str(e)[:60])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PAG_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
