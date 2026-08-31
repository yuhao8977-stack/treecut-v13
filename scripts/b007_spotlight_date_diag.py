# -*- coding: utf-8 -*-
"""V0.3 — 日期范围选择器 DOM 探测（campaign 页）。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

SPOTLIGHT = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"

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
            tab.goto(SPOTLIGHT, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 找日期选择器相关元素
            try:
                info = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('*'));
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (/近7天|近30天|今天|昨天|自定义|全部时间|近90天|近14天|日期/.test(t) && t.length <= 12) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            out.push({text: t, cls: (e.className||'').toString().slice(0,60), tag: e.tagName});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,30);
                    }""")
                print("DATE_UI =", json.dumps(info, ensure_ascii=True))
            except Exception as e:
                print("date ui fail", str(e)[:80])
            # 页面顶部横幅文本（含时间范围）
            try:
                head = tab.evaluate("() => (document.body.innerText||'').slice(0, 800)")
                print("HEAD_TEXT =", json.dumps(head, ensure_ascii=True)[:800])
            except Exception as e:
                pass
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("DATE_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
