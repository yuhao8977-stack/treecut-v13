# -*- coding: utf-8 -*-
"""V0.3.1 — 日期选择器深度校准：找触发元素 → 打开面板 → dump preset/控件。

流程：campaign 页 → 遍历可点击元素找日期展示区（含 2026-08-31 或 今日 字样）
→ 点击打开 → dump 面板内所有文本/控件（preset 按钮、日历、确定/取消）。
禁固定坐标，只用语义文本 + 稳定 class。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

CAMP_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"

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
            tab.goto(CAMP_PAGE, timeout=60000)
            time.sleep(8)
            tab.reload(timeout=60000)
            time.sleep(8)
            # 1) 找日期展示元素（含日期字符串或 今日/近 字样）
            try:
                cand = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('*'));
                      const dateRe = /2026-\\d{2}-\\d{2}|今日|昨天|近\\d+天|近\\d+日|全部时间|自定义/;
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (dateRe.test(t) && t.length <= 40) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            out.push({text: t.slice(0,30), tag: e.tagName,
                                      cls: (e.className||'').toString().slice(0,70)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,25);
                    }""")
                print("DATE_CANDIDATES =", json.dumps(cand, ensure_ascii=True))
            except Exception as e:
                print("cand fail", str(e)[:80])

            # 2) 点击第一个可见日期候选（优先含 ~ 或日期范围的）
            clicked = tab.evaluate(
                """() => {
                  const els = Array.from(document.querySelectorAll('*'));
                  const dateRe = /2026-\\d{2}-\\d{2}/;
                  for (const e of els) {
                    const t = (e.textContent||'').trim();
                    if (dateRe.test(t) && t.length <= 40) {
                      const r = e.getBoundingClientRect();
                      if (r.width > 0 && r.height > 0 && r.width < 400) {
                        e.click(); return {text: t.slice(0,30), cls: (e.className||'').toString().slice(0,60)};
                      }
                    }
                  }
                  return null;
                }""")
            print("CLICKED_DATE_ELEM =", json.dumps(clicked, ensure_ascii=True))
            time.sleep(3)

            # 3) 打开后 dump 面板内容
            try:
                panel = tab.evaluate(
                    """() => {
                      const out = [];
                      const els = Array.from(document.querySelectorAll('*'));
                      const re = /今日|昨天|近7天|近7日|近30天|近30日|近90天|近90日|自定义|确定|取消|重置|清空|开始日期|结束日期|全部时间|近14天|近15天|近3个月|近半年|近1年|今年|本月|上周|上个月/;
                      for (const e of els) {
                        const t = (e.textContent||'').trim();
                        if (re.test(t) && t.length <= 20) {
                          const r = e.getBoundingClientRect();
                          if (r.width > 0 && r.height > 0) {
                            out.push({text: t, tag: e.tagName, cls: (e.className||'').toString().slice(0,60)});
                          }
                        }
                      }
                      const uniq=[]; const seen=new Set();
                      for (const x of out){ const k=x.text+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                      return uniq.slice(0,40);
                    }""")
                print("PANEL_ITEMS =", json.dumps(panel, ensure_ascii=True))
            except Exception as e:
                print("panel fail", str(e)[:80])
        runtime._in_browser(probe, timeout=400)
        return 0
    finally:
        runtime.close()
        print("DATE_CAL_DONE")


if __name__ == "__main__":
    sys.exit(main())
