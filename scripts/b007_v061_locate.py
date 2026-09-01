# -*- coding: utf-8 -*-
"""V0.6.1 — 定位辅助：探测 note-manager 搜索/筛选 UI + 目标笔记位置。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
TARGET = "69f9a0ac000000003701d937"


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
            tab = runtime.ensure_tabs().get("CREATOR")
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            # 找输入框（搜索）
            inputs = tab.evaluate(
                """() => {
                  const out = [];
                  for (const i of document.querySelectorAll('input')) {
                    const r = i.getBoundingClientRect();
                    if (r.width > 50 && r.height > 15) {
                      out.push({placeholder: i.getAttribute('placeholder') || '',
                                type: i.type, cls: (i.className||'').toString().slice(0,50)});
                    }
                  }
                  return out.slice(0, 10);
                }""")
            print("INPUTS =", json.dumps(inputs, ensure_ascii=True))
            # 找筛选按钮（标题/关键词/时间）
            filters = tab.evaluate(
                """() => {
                  const out = [];
                  const els = Array.from(document.querySelectorAll('button, [class*=filter], [class*=search], [class*=select]'));
                  for (const e of els) {
                    const t = (e.textContent||'').trim();
                    if (/搜索|筛选|关键词|标题|时间|状态|全部/.test(t) && t.length <= 12) {
                      const r = e.getBoundingClientRect();
                      if (r.width > 0) out.push({t: t, cls: (e.className||'').toString().slice(0,50)});
                    }
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of out) { const k=x.t+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                  return uniq.slice(0, 15);
                }""")
            print("FILTERS =", json.dumps(filters, ensure_ascii=True))
            # 当前页卡片数 + 是否有日期
            info = tab.evaluate(
                """() => {
                  const cards = document.querySelectorAll('[class*=note-card], [class*=card]');
                  const text = (document.body.innerText||'');
                  const m = text.match(/共\\s*(\\d+)\\s*条|全部\\s*(\\d+)/);
                  return {cards: cards.length, total_hint: m ? m[0] : null,
                          head: text.slice(0, 200)};
                }""")
            print("PAGE =", json.dumps(info, ensure_ascii=True))
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("LOCATE_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
