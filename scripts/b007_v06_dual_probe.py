# -*- coding: utf-8 -*-
"""V0.6 — 双验证：A) feed 滚动→视频自动播放→媒体捕获；B) 样本标题搜索结果卡片 dump。"""
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

SAMPLE = "69f9a0ac000000003701d937"


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
            import io
            import unicodedata as _ud
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
            # A) feed 滚动
            ftab.goto("https://www.xiaohongshu.com/explore", timeout=60000)
            time.sleep(10)
            vids_seen = 0
            for _ in range(10):
                ftab.evaluate("() => window.scrollBy(0, 900)")
                time.sleep(2)
                vids_seen = ftab.evaluate("() => document.querySelectorAll('video').length") or 0
                if vids_seen > 0:
                    break
            print("A_VIDEOS_IN_DOM =", vids_seen)
            # 触发所有可见 video 播放
            ftab.evaluate("""() => { document.querySelectorAll('video').forEach(v => { v.muted = true; v.play().catch(()=>{}); }); }""")
            time.sleep(15)
            ftab.remove_listener("response", on_media)
            print("A_MEDIA =", json.dumps(media[:8], ensure_ascii=True))

            # B) 样本标题搜索 → 结果卡片
            manifest = json.load(io.open(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SAMPLE20_V1.json", encoding="utf-8"))
            title = next(s["title"] for s in manifest["samples"] if s["note_id"] == SAMPLE) or ""
            core = "".join(c for c in _ud.normalize("NFKC", title) if c.isalnum() or "\u4e00" <= c <= "\u9fff")
            ftab.goto("https://www.xiaohongshu.com/search_result?keyword=" + quote(core[:24]), timeout=60000)
            time.sleep(10)
            res = ftab.evaluate(
                """() => {
                  const out = [];
                  for (const a of document.querySelectorAll('a[href*="/explore/"], a[href*="/discovery/item/"]')) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/([0-9a-fA-F]{24})/);
                    if (m) out.push({id: m[1], href: href.slice(0,120)});
                  }
                  const seen=new Set(); const uniq=[];
                  for (const x of out) { if (!seen.has(x.id)) { seen.add(x.id); uniq.push(x); } }
                  return {count: uniq.length, ids: uniq.slice(0,15).map(x => x.id)};
                }""")
            print("B_RESULT_IDS =", json.dumps(res, ensure_ascii=True))
            print("B_TARGET_IN_RESULTS =", SAMPLE in (res or {}).get("ids", []))
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("DUAL_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
