# -*- coding: utf-8 -*-
"""V0.3.1 — Spotlight 历史窗口回填（bounded）：LAST_7D / LAST_14D / LAST_30D。

每窗口：
  笔记报表 (datareports-basic/note): leona/rtb/common/data/report 全分页（note 级指标）
  计划页: light/campaign/data/list 全分页 + leona/rtb/unit/search 全分页 + overall
窗口设置：d-daterangepicker → preset 按钮（最近7天/最近14天/最近30天）
证据：spotlight_raw_v031/<window>/ 下逐端点 json（redacted，xsec_token 剥离）
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.browser.config import load_config
from treecut.browser.main import BrowserRuntime

NOTE_REPORT = "https://ad.xiaohongshu.com/aurora/ad/datareports-basic/note"
CAMP_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"
WINDOWS = [("LAST_7D", "最近7天"), ("LAST_14D", "最近14天"), ("LAST_30D", "最近30天")]
SENSITIVE = re.compile(r"(token|sign|cookie|authorization|x-s|x-t|credential)", re.I)


def redact(node):
    if isinstance(node, dict):
        return {k: redact(v) for k, v in node.items() if not SENSITIVE.search(k)}
    if isinstance(node, list):
        return [redact(x) for x in node]
    if isinstance(node, str):
        # 剥离 URL 中的 xsec_token / signed 参数
        return re.sub(r"([?&](xsec_token|xsec_source|x-s|x-t|sign)=)[^&\s]+", r"\1REDACTED", node)
    return node


def set_window(tab, preset: str) -> bool:
    try:
        tab.locator(".d-daterangepicker-content, .report-date-range-picker").first.click(timeout=8000, force=True)
        time.sleep(2.5)
        loc = tab.locator("button").filter(has_text=preset).first
        if loc.count() > 0:
            loc.click(timeout=8000, force=True)
            time.sleep(6)
            return True
    except Exception as e:
        print(f"  set_window {preset} fail: {str(e)[:80]}")
    return False


def click_page(tab, target: int) -> bool:
    try:
        loc = tab.locator(".d-pagination-page, [class*=pagination-page]").filter(has_text=str(target)).first
        if loc.count() > 0:
            loc.click(timeout=8000, force=True)
            return True
    except Exception:
        pass
    return False


def capture_until(tab, want: tuple, out_dir: Path, max_rounds=120) -> dict:
    """捕获 want 端点全分页（按响应内 page 去重），翻页点击 target=max+1。"""
    bodies = {}
    max_page = {}

    def on_response(response):
        try:
            u = response.url or ""
            ctype = response.headers.get("content-type") or ""
            if "json" not in ctype:
                return
            body = response.json()
        except Exception:
            return
        s = _safe(u)
        if not any(w in s for w in want):
            return
        data = body.get("data")
        pn = None
        if isinstance(data, dict):
            pn = data.get("pageNum") or (data.get("page") or {}).get("pageIndex")
        key = s
        if pn is not None:
            if f"{s}#{pn}" in bodies:
                return
            key = f"{s}#p{pn}"
            max_page[s] = max(max_page.get(s, 0), pn)
        else:
            n = 1
            while key in bodies:
                key = f"{s}#{n}"
                n += 1
        bodies[key] = redact(body)

    tab.on("response", on_response)
    no_new = 0
    for it in range(max_rounds):
        before = len(bodies)
        try:
            tab.evaluate("() => { const els = Array.from(document.querySelectorAll('*'));"
                         " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                         "   && getComputedStyle(e).overflowY !== 'visible');"
                         " for (const e of sc) e.scrollTop = e.scrollHeight;"
                         " window.scrollTo(0, document.body.scrollHeight); }")
        except Exception:
            pass
        time.sleep(1.8)
        if len(bodies) == before:
            target = (max(max_page.values()) + 1) if max_page else 2
            if click_page(tab, target):
                for _w in range(12):
                    time.sleep(1.0)
                    if len(bodies) > before:
                        break
        if len(bodies) > before:
            no_new = 0
        else:
            no_new += 1
            if no_new >= 3:
                print(f"  exhausted after {it + 1} rounds")
                break
    tab.remove_listener("response", on_response)
    for key, body in bodies.items():
        safe = re.sub(r"[^a-z0-9]+", "_", key.replace("ad.xiaohongshu.com/api/", "")) + ".json"
        f = out_dir / safe
        f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / (safe + ".sha256")).write_text(hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
    return {"endpoints": len(bodies), "max_pages": max_page}


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
        base = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                    r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_raw_v031")
        results = {}

        def run_all():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            for wkey, preset in WINDOWS:
                out_dir = base / time.strftime("%Y%m%d_%H%M%S") / wkey
                out_dir.mkdir(parents=True, exist_ok=True)
                print(f"=== WINDOW {wkey} ({preset}) ===")
                # 笔记报表
                tab.goto(NOTE_REPORT, timeout=60000)
                time.sleep(7)
                if not set_window(tab, preset):
                    print(f"  {wkey}: window set FAILED, continuing with current")
                r1 = capture_until(tab, ("rtb/common/data/report", "ad/report/data/overall",
                                         "rtb/data/overall", "ad/report/data/distribution"), out_dir)
                print(f"  note_report: {r1}")
                # 计划页（campaign + unit）
                tab.goto(CAMP_PAGE, timeout=60000)
                time.sleep(7)
                if not set_window(tab, preset):
                    print(f"  {wkey}: campaign window set FAILED, continuing")
                r2 = capture_until(tab, ("light/campaign/data/list", "leona/rtb/unit/search",
                                         "rtb/unit/extra/list", "ad/manage/data/overall",
                                         "campaigngroup/data/list"), out_dir)
                print(f"  campaign+unit: {r2}")
                results[wkey] = {"note_report": r1, "campaign_unit": r2, "dir": str(out_dir)}
            return results

        results = runtime._in_browser(run_all, timeout=2400)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.close()
        print("V031_BACKFILL_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
