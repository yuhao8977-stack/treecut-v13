# -*- coding: utf-8 -*-
"""V0.3.1 — 笔记报表页日期选择器校准：preset/当前窗口/控件结构。"""
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
            time.sleep(8)
            # dump 日期控件候选（含日期文本 或 近N天 或 更新时间旁）
            try:
                cand = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('*'));
                      const re = /近\\d+天|近\\d+日|今日|昨天|全部时间|自定义|2026-\\d{2}-\\d{2} ~ 2026-\\d{2}-\\d{2}|2026-\\d{2}-\\d{2}~2026-\\d{2}-\\d{2}/;
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (re.test(t) && t.length <= 45) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0 && r.width < 600) {
                            out.push({text: t.slice(0,40), tag: e.tagName, cls: (e.className||'').toString().slice(0,70)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,25);
                    }""")
                print("DATE_UI =", json.dumps(cand, ensure_ascii=True))
            except Exception as e:
                print("date ui fail", str(e)[:80])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("REPORT_DATE_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
