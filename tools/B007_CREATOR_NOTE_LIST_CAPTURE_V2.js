// ============================================================================
// B007_CREATOR_NOTE_LIST_CAPTURE_V2.js（自动运行版）
// V0.2 — B007 Creator 笔记列表捕获（B003 已验证模式：用户正常浏览器执行）
//
// 与 V1 区别：粘贴后【自动运行】并自动复制 JSON——无需再敲函数名，减少复制损坏机会。
//
// 用法：
//   1. 正常浏览器登录小红书 → 打开 https://creator.xiaohongshu.com/new/note-manager
//      （确认页面显示笔记列表）
//   2. F12 → Console → 粘贴本脚本 → 回车（立即运行）
//   3. 控制台输出 B007_CREATOR_NOTE_CAPTURE count=N 并自动复制 JSON
//   4. 把复制的内容粘贴给 Harness
//
// 安全纪律：只输出 note_id/title/publish_time/media_type/duration/cover(origin+path)；
//           不含 xsec_token/cookie/Authorization/signed query。不触发任何请求。
// ============================================================================
(function () {
  "use strict";
  var MAX = 500;
  var out = [], seen = {}, seenObjs = new Set();
  function san(u) { try { var a = new URL(u); return a.origin + a.pathname; } catch (e) { return ""; } }
  function norm(t) { return (t || "").replace(/\s+/g, " ").trim(); }
  function grab(rec, node) {
    var fs = ["title", "display_title", "displayTitle", "type", "media_type", "time", "publish_time", "lastUpdateTime"];
    for (var i = 0; i < fs.length; i++) { if (node[fs[i]] !== undefined && node[fs[i]] !== null && rec[fs[i]] === undefined) rec[fs[i]] = node[fs[i]]; }
    var nc = node.noteCard || node.noteDetail;
    if (nc && typeof nc === "object") grab(rec, nc);
    var vi = node.video;
    if (vi && typeof vi === "object" && vi.duration !== undefined) rec.duration = vi.duration;
    var im = node.image_list || node.cover || node.imageInfo || (node.coverList && node.coverList[0]);
    var cu = null;
    if (Array.isArray(im) && im[0] && im[0].url) cu = im[0].url;
    else if (im && typeof im === "object" && im.url) cu = im.url;
    else if (typeof im === "string") cu = im;
    if (cu) rec.cover_safe = san(cu);
  }
  function isId(v) { return typeof v === "string" && /^[0-9a-f]{24}$/i.test(v); }
  function walk(node) {
    if (!node || typeof node !== "object" || seenObjs.has(node) || out.length >= MAX) return;
    seenObjs.add(node);
    if (Array.isArray(node)) { for (var i = 0; i < node.length; i++) walk(node[i]); return; }
    var ks = Object.keys(node);
    for (var j = 0; j < ks.length; j++) {
      var k = ks[j], v = node[k];
      if (isId(k) && v && typeof v === "object" && !seen[k]) {
        seen[k] = 1; var r = { note_id: k }; grab(r, v); out.push(r); walk(v); continue;
      }
      if (isId(v) && (k === "note_id" || k === "id" || k === "noteId") && !seen[v]) {
        seen[v] = 1; var r2 = { note_id: v }; grab(r2, node); out.push(r2);
      }
      if (v && typeof v === "object") walk(v);
    }
  }
  walk(window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || null);
  // DOM 兜底：explore 链接 + 卡片标题
  var els = document.querySelectorAll('a[href*="/explore/"]');
  var dseen = {};
  for (var i2 = 0; i2 < els.length && out.length < MAX; i2++) {
    var m = (els[i2].getAttribute("href") || "").match(/\/explore\/([0-9a-f]{24})/i);
    if (!m || dseen[m[1]] || seen[m[1]]) continue;
    dseen[m[1]] = 1; seen[m[1]] = 1;
    var card = els[i2].closest("[class]");
    var title = "";
    if (card) { var t = card.querySelector('[class*="title"], [class*="desc"]'); if (t) title = (t.textContent || "").trim(); }
    if (!title) title = (els[i2].textContent || "").trim().slice(0, 60);
    out.push({ note_id: m[1], title: norm(title) });
  }
  // 合并去重
  var merged = {};
  for (var i3 = 0; i3 < out.length; i3++) {
    var n = out[i3]; if (!n.note_id) continue;
    var rec = merged[n.note_id] || (merged[n.note_id] = { note_id: n.note_id });
    if (n.title) rec.title = norm(rec.title || n.title);
    if (n.cover_safe) rec.cover_safe = rec.cover_safe || n.cover_safe;
    if (n.duration !== undefined && rec.duration === undefined) rec.duration = n.duration;
    if (n.type || n.media_type) rec.media_type = rec.media_type || (n.media_type || n.type);
    if (n.publish_time || n.time || n.lastUpdateTime) rec.publish_time = rec.publish_time || (n.publish_time || n.time || n.lastUpdateTime);
  }
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
})();
