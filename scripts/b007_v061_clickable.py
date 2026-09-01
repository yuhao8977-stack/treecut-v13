# -*- coding: utf-8 -*-
"""V0.6.1 — 接管：自动定位目标卡片 → dump 卡片内可点击元素 → 找详情/预览入口。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
CORE = "通透又显大的开放式厨房标配岛台"


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
        runtime.reconcile_tabs()

        def probe():
            tab = runtime.ensure_tabs().get("CREATOR")
            tab.goto(NOTE_MANAGER, timeout=60000)
            time.sleep(10)
            # 搜索
            tab.evaluate(
                """(kw) => {
                  const i = document.querySelector('input[placeholder*="搜索已发布"], input[placeholder*="搜索"]');
                  if (!i) return false;
                  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                  setter.call(i, kw);
                  i.dispatchEvent(new Event('input', {bubbles:true}));
                  i.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                  i.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', bubbles:true, cancelable:true}));
                  return true;
                }""", CORE)
            time.sleep(6)
            # 找目标卡片 + dump 其内部可点击元素（含 href/class/text）
            dump = tab.evaluate(
                """(core) => {
                  const els = Array.from(document.querySelectorAll('[class*=note-card], [class*=card], [class*=item]'));
                  const coreN = (t) => (t||'').replace(/[\\s\\u0000-\\u001f]/g, '');
                  let card = null;
                  for (const e of els) {
                    const t = (e.textContent||'');
                    if (t.length > 8 && t.length < 400 && coreN(t).includes(core.slice(0,8))) {
                      const r = e.getBoundingClientRect();
                      if (r.width > 200) { card = e; break; }
                    }
                  }
                  if (!card) return {found: false};
                  card.scrollIntoView({block: 'center'});
                  const clickables = [];
                  for (const el of card.querySelectorAll('button, a, [class*=btn], [class*=preview], [class*=view], [class*=detail], [class*=op], [class*=action]')) {
                    const r = el.getBoundingClientRect();
                    const t = (el.textContent||'').trim().slice(0, 12);
                    if (r.width > 0 && r.height > 0) {
                      clickables.push({tag: el.tagName, t: t, href: (el.getAttribute && el.getAttribute('href') || '').slice(0,80),
                                       cls: (el.className||'').toString().slice(0,60)});
                    }
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of clickables) { const k=x.tag+'|'+x.t+'|'+x.href+'|'+x.cls; if(!seen.has(k)){seen.add(k);uniq.push(x);} }
                  return {found: true, card_text: (card.textContent||'').slice(0,120), clickables: uniq.slice(0, 20)};
                }""", CORE)
            print("DUMP =", json.dumps(dump, ensure_ascii=True))
        runtime._in_browser(probe, timeout=300)
        return 0
    finally:
        runtime.close()
        print("CLICKABLE_DUMP_DONE")


if __name__ == "__main__":
    sys.exit(main())
