# -*- coding: utf-8 -*-
"""V0.6 — 两条关键链路验证：
A) feed 视频卡片点击 → 视频媒体响应（观察链路可用性）
B) 搜索账号 → 用户卡点击 → 带 xsec 的个人主页 → 笔记卡片渲染
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime


def _safe(url):
    try:
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


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
            ftab = runtime.ensure_tabs().get("FRONTEND")
            media = []

            def on_media(response):
                try:
                    u = response.url or ""
                    ctype = (response.headers.get("content-type") or "").lower()
                    s = _safe(u)
                    if "video" in ctype or ".mp4" in u.lower() or ".m3u8" in u.lower() or "sns-video" in s:
                        media.append({"safe": s, "ctype": ctype[:40], "len": response.headers.get("content-length")})
                except Exception:
                    pass

            ftab.on("response", on_media)
            # A) feed 点击：找视频卡片（含 video 元素的卡片）
            ftab.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            time.sleep(10)
            vid_card = ftab.evaluate(
                """() => {
                  const cards = Array.from(document.querySelectorAll('section.note-item, [class*=note-item]'));
                  for (const c of cards) {
                    const r = c.getBoundingClientRect();
                    if (r.width > 100 && r.height > 100) { c.click(); return true; }
                  }
                  const a = Array.from(document.querySelectorAll('a[href*="/explore/"]')).find(x => x.getBoundingClientRect().width > 100);
                  if (a) { a.click(); return true; }
                  return false;
                }""")
            print("A_CLICKED =", vid_card)
            time.sleep(12)
            has_video = ftab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return true; } return false; }")
            print("A_HAS_VIDEO =", has_video)
            time.sleep(10)
            print("A_MEDIA =", json.dumps(media[:6], ensure_ascii=True))

            # B) 搜索账号 → 用户卡
            media.clear()
            ftab.goto("https://www.xiaohongshu.com/search_result?keyword=" + quote("KUBON坤宝高端岛台工厂"), timeout=60000)
            time.sleep(10)
            user_click = ftab.evaluate(
                """() => {
                  for (const a of document.querySelectorAll('a[href*="/user/profile/"]')) {
                    const r = a.getBoundingClientRect();
                    if (r.width > 100 && r.height > 50) { a.click(); return a.getAttribute('href'); }
                  }
                  return null;
                }""")
            print("B_USER_CLICK =", user_click)
            time.sleep(10)
            print("B_URL =", ftab.url[:160])
            # 个人主页笔记卡片
            notes = ftab.evaluate(
                """() => {
                  const links = Array.from(document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]'));
                  const out = [];
                  for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/([0-9a-fA-F]{24})/);
                    if (m && href.includes('xsec')) out.push({id: m[1], href: href.slice(0,150)});
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of out) { if (!seen.has(x.id)) { seen.add(x.id); uniq.push(x); } }
                  return {count: uniq.length, sample: uniq.slice(0,6)};
                }""")
            print("B_PROFILE_NOTES =", json.dumps(notes, ensure_ascii=True))
            ftab.remove_listener("response", on_media)
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("LINKS_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
