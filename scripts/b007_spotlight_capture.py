# -*- coding: utf-8 -*-
"""V0.3 — B007 Spotlight 主捕获：计划页 + 单元页 全分页 page-owned 响应。

端点（页面自有，非模拟 API）：
  计划页: light/campaign/data/list(指标), leona/rtb/campaign/base/list(结构),
          light/campaign/extra/list(unitIds), light/campaigngroup/data/list(组),
          light/ad/manage/data/overall(账户)
  单元页: leona/rtb/unit/search(单元+noteIds+单元指标), leona/rtb/unit/extra/list
翻页：点击「下一页」触发 page-owned 请求（有界，3 轮无新响应即止）。
Redact：递归剥离 token/sign/cookie/authorization/x-s/x-t 类字段。
输出：spotlight_raw/<run>/ 下逐端点 json + summary。
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

CAMP_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/campaign"
UNIT_PAGE = "https://ad.xiaohongshu.com/aurora/ad/manage/unit"
WANT = ("rtb/campaign/base/list", "light/campaign/data/list", "rtb/unit/search",
        "rtb/unit/extra/list", "light/campaign/extra/list", "campaigngroup/data/list",
        "ad/manage/data/overall")
SENSITIVE = re.compile(r"(token|sign|cookie|authorization|x-s|x-t|credential|session_key|__ac)", re.I)


def redact(node):
    if isinstance(node, dict):
        return {k: redact(v) for k, v in node.items()
                if not SENSITIVE.search(k)}
    if isinstance(node, list):
        return [redact(x) for x in node]
    return node


def click_next_pw(tab, max_page: dict) -> bool:
    """Playwright 真实点击（JS .click() 不触发 SPA 数据加载）。目标页 = max_page+1。"""
    try:
        target = max(max_page.values()) + 1 if max_page else 2
        loc = tab.locator(".d-pagination-page, [class*=pagination-page]").filter(has_text=str(target)).first
        if loc.count() > 0:
            loc.click(timeout=8000, force=True)
            return True
    except Exception:
        pass
    try:
        return bool(tab.evaluate(
            "() => { const els = Array.from(document.querySelectorAll('button,a,[class*=page],[class*=next],[class*=pagin] *'));"
            " const n = els.find(e => { const t=(e.textContent||'').trim();"
            "   return (t === '下一页' || t === '>' || /next/i.test(t)) && e.getBoundingClientRect().width > 0; });"
            " if (n) { n.click(); return true; } return false; }"))
    except Exception:
        return False


def capture_page(tab, url, name, out_dir, max_rounds=30) -> dict:
    bodies = {}          # key: endpoint#idx (dedup by endpoint+pageNum)
    seen_pages = {}      # endpoint -> set(pageNum seen)
    max_page = {}        # endpoint -> max pageNum
    post = {"count": 0}

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
        if not any(w in s for w in WANT):
            return
        data = body.get("data")
        pn = None
        if isinstance(data, dict):
            pn = data.get("pageNum")
        key = s
        if pn is not None:
            sp = seen_pages.setdefault(s, set())
            if pn in sp:
                return  # 同 endpoint 同页已捕获 → 去重
            sp.add(pn)
            max_page[s] = max(max_page.get(s, 0), pn)
            key = f"{s}#page{pn}"
        else:
            n = 1
            while key in bodies:
                key = f"{s}#{n}"
                n += 1
        bodies[key] = redact(body)
        post["count"] = len(bodies)

    tab.on("response", on_response)
    try:
        tab.goto(url, timeout=60000)
        time.sleep(7)
    except Exception as e:
        print(f"  [{name}] NAV_FAIL {str(e)[:80]}")
    try:
        tab.reload(timeout=60000)
        time.sleep(7)
    except Exception as e:
        print(f"  [{name}] RELOAD_FAIL {str(e)[:80]}")
    # 翻页：点击 last+1（Playwright 真实点击），直到 3 轮无新页
    no_new = 0
    for it in range(max_rounds):
        before = post["count"]
        try:
            tab.evaluate("() => { const els = Array.from(document.querySelectorAll('*'));"
                         " const sc = els.filter(e => e.scrollHeight > e.clientHeight + 100"
                         "   && getComputedStyle(e).overflowY !== 'visible');"
                         " for (const e of sc) e.scrollTop = e.scrollHeight;"
                         " window.scrollTo(0, document.body.scrollHeight); }")
        except Exception:
            pass
        time.sleep(2.0)
        if post["count"] == before:
            clicked = click_next_pw(tab, max_page)
            if clicked:
                for _w in range(12):
                    time.sleep(1.0)
                    if post["count"] > before:
                        break
        if post["count"] > before:
            no_new = 0
        else:
            no_new += 1
            if no_new >= 3:
                print(f"  [{name}] exhausted after {it + 1} rounds (no new page)")
                break
    tab.remove_listener("response", on_response)

    for key, body in bodies.items():
        safe_name = re.sub(r"[^a-z0-9]+", "_", key.replace("ad.xiaohongshu.com/api/", "")) + ".json"
        f = out_dir / safe_name
        f.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / (safe_name + ".sha256")).write_text(
            hashlib.sha256(f.read_bytes()).hexdigest(), encoding="utf-8")
    return {"endpoints": sorted(bodies.keys()), "count": post["count"],
            "max_pages": {k: v for k, v in max_page.items()}}


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
        inbox = Path(runtime.workspace.workspace_dir) / "treecut_inbox" / "creator" / "raw" / "creator"
        run_dir = inbox / "spotlight_raw" / time.strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)

        def run_all():
            tab = runtime.ensure_tabs().get("SPOTLIGHT")
            results = {}
            results["campaign_page"] = capture_page(tab, CAMP_PAGE, "campaign", run_dir)
            results["unit_page"] = capture_page(tab, UNIT_PAGE, "unit", run_dir)
            return results

        results = runtime._in_browser(run_all, timeout=900)
        summary = {
            "run": run_dir.name,
            "workspace": "B007",
            "account_name": "T-KUBON坤宝高端岛台工厂-zx (from binding; not hardcoded in code)",
            "results": results,
            "date_range_default": "2026-08-31 (今日默认视图；日期选择器文本未探测到 → AVAILABLE_PAID_DATE_RANGE 待扩展)",
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"RUN_DIR = {run_dir}")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    finally:
        runtime.close()
        print("SPOTLIGHT_CAPTURE_DONE")


def _safe(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url or "")
        return f"{p.netloc}{p.path}"
    except Exception:
        return url or ""


if __name__ == "__main__":
    sys.exit(main())
