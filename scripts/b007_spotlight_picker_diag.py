# -*- coding: utf-8 -*-
"""V0.3.1 — 打开 daterangepicker 面板 → dump presets（今日/昨天/近7天/近30天/自定义...）。"""
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
            # Playwright 真实点击 daterangepicker 打开面板
            try:
                loc = tab.locator(".d-daterangepicker-content, .report-date-range-picker").first
                print("PICKER_COUNT =", loc.count())
                loc.click(timeout=8000, force=True)
                time.sleep(3)
                print("PICKER_CLICKED")
            except Exception as e:
                print("picker click fail", str(e)[:120])
            # dump 打开后的面板内容（preset 按钮 + 日历）
            try:
                panel = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('*'));
                      const re = /今日|昨天|昨日|近7天|近7日|近30天|近30日|近90天|近90日|自定义|确定|取消|重置|清空|本月|上月|今年|全部时间|近14天|近60天|近180天|近1年|开始|结束/;
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (re.test(t) && t.length <= 15) {
                          const r = e.getBoundingClientRect();
                          const cs = getComputedStyle(e);
                          if (r.width > 0 && r.height > 0 && cs.visibility !== 'hidden') {
                            out.push({text: t, tag: e.tagName, cls: (e.className||'').toString().slice(0,60)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,40);
                    }""")
                print("PICKER_PANEL =", json.dumps(panel, ensure_ascii=True))
            except Exception as e:
                print("panel fail", str(e)[:80])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("PICKER_DIAG_DONE")


if __name__ == "__main__":
    sys.exit(main())
