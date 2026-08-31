// ============================================================================
// B007_CREATOR_NOTE_LIST_CAPTURE_V3.js（网络挂钩版，自动运行）
// V0.2 — B007 Creator 笔记列表捕获（B003 已验证：页面自有响应观察）
//
// note-manager 的列表不在 __INITIAL_STATE__、卡片也不用 /explore/ 链接；
// 列表由页面自己的网络请求加载 → 本工具挂钩 fetch/XHR，在窗口期内
// 捕获页面自发请求中的 note 数据（不构造任何请求，合规）。
//
// 用法：
//   1. 正常浏览器登录小红书 → 打开 https://creator.xiaohongshu.com/new/note-manager
//      （确认页面显示笔记列表）
//   2. F12 → Console → 粘贴本脚本 → 回车（自动开始挂钩 + 6 秒捕获窗口）
//   3. 窗口期内：上下滚动几次 / 点"下一页""上一页"（触发列表重新请求）
//   4. 结束后自动输出并复制 JSON → 粘贴给 Harness
//
// 安全纪律：只输出 note_id/title/publish_time/media_type/duration/cover(origin+path)；
//           不含 xsec_token/cookie/Authorization/signed query。
// ============================================================================
(function () {
  "use strict";
  var MAX = 500;
  var merged = {};
  var seen = {};
  var WINDOW_MS = 6000;

  function san(u) { try { var a = new URL(u); return a.origin + a.pathname; } catch (e) { return ""; } }
  function norm(t) { return (t || "").replace(/\s+/g, " ").trim(); }
  function isId(v) { return typeof v === "string" && /^[0-9a-f]{24}$/i.test(v); }

  function addNote(nid, node) {
    if (!nid || seen[nid]) return;
    seen[nid] = 1;
    var rec = { note_id: nid };
    var fs = ["title", "display_title", "displayTitle", "type", "media_type", "time", "publish_time", "lastUpdateTime"];
    for (var i = 0; i < fs.length; i++) {
      if (node[fs[i]] !== undefined && node[fs[i]] !== null) rec[fs[i]] = node[fs[i]];
    }
    var nc = node.noteCard || node.noteDetail;
    if (nc && typeof nc === "object") {
      for (var i2 = 0; i2 < fs.length; i2++) {
        if (nc[fs[i2]] !== undefined && nc[fs[i2]] !== null && rec[fs[i2]] === undefined) rec[fs[i2]] = nc[fs[i2]];
      }
      if (nc.video && nc.video.duration !== undefined && rec.duration === undefined) rec.duration = nc.video.duration;
      var nci = nc.image_list || nc.cover;
      if (Array.isArray(nci) && nci[0] && nci[0].url) rec.cover_safe = san(nci[0].url);
      else if (nci && typeof nci === "object" && nci.url) rec.cover_safe = san(nci.url);
    }
    var vi = node.video;
    if (vi && typeof vi === "object" && vi.duration !== undefined && rec.duration === undefined) rec.duration = vi.duration;
    var im = node.image_list || node.cover || node.imageInfo || (node.coverList && node.coverList[0]);
    var cu = null;
    if (Array.isArray(im) && im[0] && im[0].url) cu = im[0].url;
    else if (im && typeof im === "object" && im.url) cu = im.url;
    else if (typeof im === "string") cu = im;
    if (cu && !rec.cover_safe) rec.cover_safe = san(cu);
    merged[nid] = rec;
  }

  // 遍历任意 JSON，提取含 24-hex note_id 的对象（key 与值两种形态）
  function scan(node) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { for (var i = 0; i < node.length; i++) scan(node[i]); return; }
    var ks = Object.keys(node);
    for (var j = 0; j < ks.length; j++) {
      var k = ks[j], v = node[k];
      if (isId(k) && v && typeof v === "object") { addNote(k, v); scan(v); continue; }
      if (isId(v) && (k === "note_id" || k === "id" || k === "noteId")) addNote(v, node);
      if (v && typeof v === "object") scan(v);
    }
  }

  // ---- 挂钩 fetch ----
  var of = window.fetch;
  if (of && !window.__b007hooked) {
    window.fetch = function () {
      var args = arguments;
      var p = of.apply(this, args);
      try {
        p.then(function (resp) {
          try { resp.clone().json().then(scan).catch(function () {}); } catch (e) {}
        }).catch(function () {});
      } catch (e) {}
      return p;
    };
  }
  // ---- 挂钩 XHR ----
  var oo = XMLHttpRequest.prototype.open;
  var os = XMLHttpRequest.prototype.send;
  if (!window.__b007hooked) {
    XMLHttpRequest.prototype.open = function (m, u) { this.__b007u = u; return oo.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function () {
      var xhr = this;
      this.addEventListener("load", function () {
        try {
          var j = JSON.parse(xhr.responseText || "");
          scan(j);
        } catch (e) {}
      });
      return os.apply(this, arguments);
    };
  }
  window.__b007hooked = true;

  // 已加载页面的 __INITIAL_STATE__ / DOM 也扫一遍
  try { scan(window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || null); } catch (e) {}
  var els = document.querySelectorAll('a[href*="/explore/"]');
  for (var i3 = 0; i3 < els.length; i3++) {
    var m = (els[i3].getAttribute("href") || "").match(/\/explore\/([0-9a-f]{24})/i);
    if (m && !seen[m[1]]) {
      seen[m[1]] = 1;
      var card = els[i3].closest("[class]");
      var ttl = "";
      if (card) { var t = card.querySelector('[class*="title"], [class*="desc"]'); if (t) ttl = (t.textContent || "").trim(); }
      merged[m[1]] = { note_id: m[1], title: norm(ttl || els[i3].textContent || "") };
    }
  }

  console.log("[B007] 挂钩已启动，捕获窗口 " + (WINDOW_MS / 1000) + " 秒——请滚动 / 点下一页 / 上一页触发列表请求…");
  var start = Date.now();
  function tick() {
    try { window.scrollBy(0, document.body.scrollHeight); } catch (e) {}
    if (Date.now() - start < WINDOW_MS) {
      setTimeout(tick, 700);
    } else {
      var ids = Object.keys(merged).sort();
      var result = [];
      for (var i4 = 0; i4 < ids.length; i4++) result.push(merged[ids[i4]]);
      console.log("B007_CREATOR_NOTE_CAPTURE count=" + result.length);
      console.log(JSON.stringify(result, null, 1));
      try {
        var ta = document.createElement("textarea");
        ta.value = JSON.stringify(result);
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        console.log("已复制到剪贴板（请粘贴给 Harness）");
      } catch (e) { console.log("请手动复制上方 JSON"); }
    }
  }
  tick();
})();
