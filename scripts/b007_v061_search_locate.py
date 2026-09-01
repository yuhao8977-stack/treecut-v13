# -*- coding: utf-8 -*-
"""V0.6.1 — 搜索定位测试：输入关键词 → 结果卡片标题 → 确认目标可定位。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
KEYWORD = "通透又显大的开放式厨房标配岛台"


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
            # 输入关键词到搜索框
            typed = tab.evaluate(
                """(kw) => {
                  const i = document.querySelector('input[placeholder*="搜索已发布"], input[placeholder*="搜索"]');
                  if (!i) return false;
                  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                  setter.call(i, kw);
                  i.dispatchEvent(new Event('input', {bubbles:true}));
                  i.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                  i.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true, cancelable:true}));
                  return true;
                }""", KEYWORD)
            print("TYPED =", typed)
            time.sleep(6)
            # dump 结果卡片标题
            cards = tab.evaluate(
                """() => {
                  const els = Array.from(document.querySelectorAll('[class*=note-card], [class*=card], [class*=item]'));
                  const titles = [];
                  for (const e of els) {
                    const t = (e.textContent||'').trim();
                    if (t && t.length > 8 && t.length < 200) {
                      const r = e.getBoundingClientRect();
                      if (r.width > 200) titles.push(t.slice(0, 60));
                    }
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of titles) { if (!seen.has(x)) { seen.add(x); uniq.push(x); } }
                  return uniq.slice(0, 10);
                }""")
            print("RESULT_CARDS =", json.dumps(cards, ensure_ascii=True))
            print("URL =", tab.url[:100])
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("SEARCH_LOCATE_DONE")


if __name__ == "__main__":
    sys.exit(main())
