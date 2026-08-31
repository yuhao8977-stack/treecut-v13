// ============================================================================
// B007_CREATOR_NOTE_LIST_DIAG_V4.js（诊断版，自动运行）
// V0.2 — 笔记管理页真实 DOM 结构诊断：定位笔记卡片/链接/data 属性
//
// 背景：V2(SSR/DOM) 与 V3(网络挂钩) 均返回空，但页面确实显示列表 →
//       需要看卡片真实结构才能精确定位。本工具只读 DOM，输出诊断信息。
//
// 用法：
//   1. 正常浏览器 → 打开 https://creator.xiaohongshu.com/new/note-manager
//      （确认列表可见）
//   2. F12 → Console → 粘贴 → 回车（自动运行并复制诊断 JSON）
//   3. 把输出粘贴给 Harness
// ============================================================================
(function () {
  "use strict";
  var out = {};
  try { out.title = document.title; } catch (e) { out.title = "?"; }
  try { out.url = location.origin + location.pathname; } catch (e) { out.url = "?"; }

  // 1) 所有含 24-hex id 的链接 href（任意路径）
  var hrefs = [];
  var ah = document.querySelectorAll("a[href]");
  for (var i = 0; i < ah.length && hrefs.length < 30; i++) {
    var h = ah[i].getAttribute("href") || "";
    var m = h.match(/([0-9a-f]{24})/i);
    if (m) hrefs.push(h.slice(0, 120));
  }
  out.hrefs_with_24hex = hrefs;

  // 2) 含 24-hex 值的 data-* 属性
  var dataHits = [];
  var all = document.querySelectorAll("[data-note-id], [data-id], [data-noteid], [data-note_id], [data-note], [data-xsec-app-id]");
  for (var i2 = 0; i2 < all.length && dataHits.length < 30; i2++) {
    var el = all[i2];
    var attrs = {};
    for (var j = 0; j < el.attributes.length; j++) {
      var an = el.attributes[j].name;
      var av = el.attributes[j].value || "";
      if (/^data-/i.test(an) && /[0-9a-f]{24}/i.test(av)) attrs[an] = av.slice(0, 60);
    }
    if (Object.keys(attrs).length) dataHits.push(attrs);
  }
  out.data_attr_hits = dataHits;

  // 3) 含 note/card/item/note-card 的 class 样本
  var classes = new Set();
  var all2 = document.querySelectorAll("[class]");
  for (var i3 = 0; i3 < all2.length && classes.size < 40; i3++) {
    var cls = all2[i3].getAttribute("class") || "";
    if (/note|card|item|video|note-card|grid/i.test(cls)) {
      cls.split(/\s+/).forEach(function (c) { if (/note|card|item|video/i.test(c) && c.length < 60) classes.add(c); });
    }
  }
  out.note_like_classes = Array.from(classes).slice(0, 40);

  // 4) 页面文本里的 24-hex id 数量（粗略判断数据是否在 DOM）
  try {
    var txt = document.body.innerText || "";
    out.body_text_chars = txt.length;
    var idMatches = txt.match(/[0-9a-f]{24}/gi);
    out.body_text_24hex_count = idMatches ? idMatches.length : 0;
  } catch (e) { out.body_text_chars = "?"; }

  // 5) __INITIAL_STATE__ 顶层键
  try {
    var s = window.__INITIAL_STATE__ || window.__INITIAL_SSR_STATE__ || {};
    out.initial_state_keys = Object.keys(s).slice(0, 30);
  } catch (e) { out.initial_state_keys = []; }

  console.log("B007_DIAG:" + JSON.stringify(out));
  try {
    var ta = document.createElement("textarea");
    ta.value = JSON.stringify(out);
    document.body.appendChild(ta); ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    console.log("已复制诊断 JSON，请粘贴给 Harness");
  } catch (e) { console.log("请手动复制上方 JSON"); }
  return out;
})();
