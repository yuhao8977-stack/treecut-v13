# -*- coding: utf-8 -*-
"""V0.6 — 标题搜索路径：搜索样本标题 → 找到卡片 → 点击（SPA 注入 xsec）→ 验证 note_id + 观察视频。

样本：69f9a0ac000000003701d937（C 组 2026-05）。
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
            import json as _j
            manifest = _j.load(io.open(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SAMPLE20_V1.json", encoding="utf-8"))
            title = next(s["title"] for s in manifest["samples"] if s["note_id"] == SAMPLE) or ""
            print("TITLE_LEN =", len(title))
            # 标题中取中文核心词（去 emoji/标点）用于搜索
            import unicodedata as _ud
            core = "".join(c for c in _ud.normalize("NFKC", title) if c.isalnum() or "\u4e00" <= c <= "\u9fff")
            print("CORE_LEN =", len(core))
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
            # 搜索
            kw = quote(core[:20])
            try:
                ftab.goto(f"https://www.xiaohongshu.com/search_result?keyword={kw}", timeout=60000)
                time.sleep(10)
            except Exception as e:
                print("search fail", str(e)[:80])
            print("SEARCH_URL =", ftab.url[:140])
            # 找目标 note 卡片（href 含样本 id）
            found = ftab.evaluate(
                """(nid) => {
                  const links = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
                  for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    if (href.includes(nid)) { a.click(); return href.slice(0, 160); }
                  }
                  return null;
                }""", SAMPLE)
            print("FOUND_AND_CLICKED =", found)
            time.sleep(12)
            print("URL =", ftab.url[:200])
            m = re.search(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})", ftab.url or "")
            print("NOTE_ID =", m.group(1) if m else None)
            # 触发播放
            try:
                ftab.evaluate("() => { const v=document.querySelector('video'); if (v) { v.muted=true; v.play().catch(()=>{}); return true; } return false; }")
                time.sleep(12)
            except Exception:
                pass
            ftab.remove_listener("response", on_media)
            print("MEDIA =", json.dumps(media[:10], ensure_ascii=True))
        runtime._in_browser(probe, timeout=500)
        return 0
    finally:
        runtime.close()
        print("SEARCH_PROBE_DONE")


if __name__ == "__main__":
    sys.exit(main())
