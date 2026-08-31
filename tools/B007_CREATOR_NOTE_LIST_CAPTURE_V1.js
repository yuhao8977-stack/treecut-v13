// ============================================================================
// B007_CREATOR_NOTE_LIST_CAPTURE_V1.js
// V0.2 — B007 Creator 笔记列表捕获工具（B003 已验证模式：用户在正常浏览器执行）
//
// 背景：XHS 对自动化(Playwright)会话软阻断笔记列表 API（data=null）。
//       在你自己的人工浏览器（正常登录、无自动化检测）里打开笔记管理页，
//       页面用有效会话渲染出列表 → 本工具从 __INITIAL_STATE__ / DOM 提取安全字段。
//
// 用法：
//   1. 正常浏览器登录小红书 → 打开 https://creator.xiaohongshu.com/new/note-manager
//   2. 确认页面显示笔记列表 → 按 F12 打开控制台 → 粘贴本脚本 → 回车
//   3. 运行 __B007CaptureCreatorNotes()
//   4. 把控制台输出的 JSON 数组复制给 Harness（或截图/复制 textarea 内容）
//
// 安全纪律：只输出 note_id/title/publish_time/media_type/duration/cover(origin+path)；
//           不含 xsec_token/cookie/Authorization/signed query。不触发任何请求。
// ============================================================================

(function () {
  "use strict";

  var MAX = 500;

  function sanitizeUrl(u) {
    try {
      var a = new URL(u);
      return a.origin + a.pathname;
    } catch (e) { return ""; }
  }

  function normTitle(t) {
    return (t || "").replace(/\s+/g, " ").trim();
  }

  function grab(rec, node) {
    var fields = ["title", "display_title", "displayTitle", "type", "media_type",
                  "time", "publish_time", "lastUpdateTime"];
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      if (node[f] !== undefined && node[f] !== null && rec[f] === undefined) rec[f] = node[f];
    }
    var nc = node.noteCard || node.noteDetail;
    if (nc && typeof nc === "object") grab(rec, nc);
    var vi = node.video;
    if (vi && typeof vi === "object" && vi.duration !== undefined) rec.duration = vi.duration;
    var im = node.image_list || node.cover || node.imageInfo ||
             (node.coverList && node.coverList[0]);
    var coverUrl = null;
    if (Array.isArray(im) && im[0] && im[0].url) coverUrl = im[0].url;
    else if (im && typeof im === "object" && im.url) coverUrl = im.url;
    else if (typeof im === "string") coverUrl = im;
    if (coverUrl) rec.cover_safe = sanitizeUrl(coverUrl);
  }

  // 从 __INITIAL_STATE__ 提取（key 与值两种 id 形态）
  function extractState() {
    var out = [], seen = {}, seenObjs = new Set();
    var isId = function (v) { return typeof v === "string" && /^[0-9a-f]{24}$/i.test(v); };
    var walk = function (node) {
      if (!node || typeof node !== "object" || seenObjs.has(node) || out.length >= MAX) return;
      seenObjs.add(node);
      if (Array.isArray(node)) { for (var i = 0; i < node.length; i++) walk(node[i]); return; }
      var keys = Object.keys(node);
      for (var j = 0; j < keys.length; j++) {
        var k = keys[j], v = node[k];
        if (isId(k) && v && typeof v === "object" && !seen[k]) {
          seen[k] = 1; var r = { note_id: k }; grab(r, v); out.push(r);
          walk(v); continue;
        }
        if (isId(v) && (k === "note_id" || k === "id" || k === "noteId") && !seen[v]) {
          seen[v] = 1; var r2 = { note_id: v }; grab(r2, node); out.push(r2);
        }
        if (v && typeof v === "object") walk(v);
      }
    };
    walk(window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || null);
    return out;
  }

  // 从已渲染 DOM 提取（explore 链接 + 卡片标题）
  function extractDom() {
    var out = [], seen = {};
    var els = document.querySelectorAll('a[href*="/explore/"]');
    for (var i = 0; i < els.length && out.length < MAX; i++) {
      var m = (els[i].getAttribute("href") || "").match(/\/explore\/([0-9a-f]{24})/i);
      if (!m || seen[m[1]]) continue;
      seen[m[1]] = 1;
      var card = els[i].closest("[class]");
      var title = "";
      if (card) {
        var t = card.querySelector('[class*="title"], [class*="desc"]');
        if (t) title = (t.textContent || "").trim();
      }
      if (!title) title = (els[i].textContent || "").trim().slice(0, 60);
      out.push({ note_id: m[1], title: normTitle(title) });
    }
    return out;
  }

  window.__B007CaptureCreatorNotes = function () {
    var merged = {};
    var push = function (list) {
      for (var i = 0; i < list.length; i++) {
        var n = list[i];
        if (!n.note_id) continue;
        var rec = merged[n.note_id] || (merged[n.note_id] = { note_id: n.note_id });
        if (n.title) rec.title = normTitle(rec.title || n.title);
        if (n.cover_safe) rec.cover_safe = rec.cover_safe || n.cover_safe;
        if (n.duration !== undefined && rec.duration === undefined) rec.duration = n.duration;
        if (n.type || n.media_type) rec.media_type = rec.media_type || (n.media_type || n.type);
        if (n.publish_time || n.time || n.lastUpdateTime) {
          rec.publish_time = rec.publish_time || (n.publish_time || n.time || n.lastUpdateTime);
        }
      }
    };
    push(extractState());
    push(extractDom());
    var ids = Object.keys(merged).sort();
    var result = [];
    for (var i = 0; i < ids.length; i++) result.push(merged[ids[i]]);
    console.log("B007_CREATOR_NOTE_CAPTURE count=" + result.length);
    console.log(JSON.stringify(result, null, 1));
    try {
      var ta = document.createElement("textarea");
      ta.value = JSON.stringify(result);
      document.body.appendChild(ta); ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      console.log("已复制到剪贴板（请粘贴给 Harness）");
    } catch (e) { /* 复制失败则手动复制上方 JSON */ }
    return result;
  };

  console.log("[B007] 捕获工具就绪：在笔记管理页执行 __B007CaptureCreatorNotes()");
})();
