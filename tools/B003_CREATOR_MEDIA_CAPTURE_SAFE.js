// ============================================================================
// B003_CREATOR_MEDIA_CAPTURE_SAFE.js
// Stage 3A.5 — B003 Creator 媒体元数据安全监听捕获
//
// 用途：在【已登录 B003 账号的小红书 Creator 后台】页面 Console 中执行，
//       监听页面【自身正常发出】的 XHR/fetch 响应，只处理 /note/user/posted，
//       提取每条 note 的媒体元数据（images_list / video_info）。
//
// 安全纪律（Stage3A.5 §4-9）：
//   - 不独立构造 fetch（Creator 有请求签名，独立调用会 406）
//   - 不读取/导出/保存 cookie / authorization / xsec_token / session / sign / signature / ticket / credential
//   - 敏感字段递归 DROP（不是 mask，是完全不写入导出文件）
//   - signed / ephemeral URL：不写完整 URL，只记录 url_origin + url_path + resource_type + signed_present
//   - Console 不打印 raw note / video_info 完整对象 / 完整 URL
//
// 使用方式：浏览器 Console 粘贴本脚本 → 在「笔记管理 → 已发布」正常滚动页面
//           （页面自身会发出 posted?page=N 请求）→ 监听器自动收集 → 导出。
// ============================================================================

(function () {
  "use strict";

  // ---------- 敏感字段名（递归 DROP） ----------
  var SENSITIVE_KEYS = [
    "token", "cookie", "authorization", "auth", "secret", "session",
    "sign", "signature", "ticket", "credential", "xsec", "password",
  ];

  // ---------- 已知 B003 note_id 集合（由 Harness 生成，用户粘贴） ----------
  // 占位：实际由 Harness 从 published_content_v1 生成 155 个 note_id 填入
  var KNOWN_NOTE_IDS = null; // 若为 null 则不按 note_id 过滤（收集全部后按交集）

  // ---------- 收集状态 ----------
  var records = {};   // key = note_id
  var stats = { captured: 0, with_images: 0, with_video_info: 0, with_cover: 0, with_signed: 0 };

  // ---------- 工具 ----------
  function isSensitiveKey(key) {
    var k = String(key).toLowerCase();
    for (var i = 0; i < SENSITIVE_KEYS.length; i++) {
      if (k.indexOf(SENSITIVE_KEYS[i]) >= 0) return true;
    }
    return false;
  }

  // 递归净化：敏感字段 DROP；signed URL 只留 origin/path；普通 URL 保留
  function sanitizeValue(value, key) {
    if (value === null || value === undefined) return value;
    // 敏感字段名 → DROP
    if (isSensitiveKey(key)) return undefined;
    if (typeof value === "string") {
      // URL 处理
      if (/^https?:\/\//.test(value)) {
        try {
          var u = new URL(value);
          var q = u.searchParams;
          var signed = false;
          q.forEach(function (v, k) {
            if (isSensitiveKey(k)) signed = true;
          });
          if (signed) {
            // EPHEMERAL_SIGNED_URL：不写完整 URL
            return { url_origin: u.origin, url_path: u.pathname,
                     resource_type: "signed_media", signed_url_present: true };
          }
          return value; // SAFE_REFERENCE_URL
        } catch (e) {
          return value;
        }
      }
      return value;
    }
    if (Array.isArray(value)) {
      return value.map(function (v) { return sanitizeValue(v, key); })
                  .filter(function (v) { return v !== undefined; });
    }
    if (typeof value === "object") {
      var out = {};
      Object.keys(value).forEach(function (k) {
        var v = sanitizeValue(value[k], k);
        if (v !== undefined) out[k] = v;
      });
      return out;
    }
    return value;
  }

  function extractRecord(raw) {
    var rec = sanitizeValue(raw, "");
    var noteId = rec.id || rec.note_id || rec.noteId || null;
    if (!noteId) return null;
    // 只保留媒体相关字段
    return {
      note_id: String(noteId),
      display_title: rec.display_title || rec.title || "",
      publish_time: rec.time || rec.publish_time || "",
      media_type: rec.type || "",
      images_list: rec.images_list || [],
      video_info: rec.video_info || null,
    };
  }

  function handleResponse(url, data) {
    if (!url || url.indexOf("/note/user/posted") < 0) return;
    var list = null;
    if (data && data.records && Array.isArray(data.records)) list = data.records;
    else if (data && Array.isArray(data)) list = data;
    else if (data && data.data && data.data.records) list = data.data.records;
    if (!list) return;
    list.forEach(function (raw) {
      var rec = extractRecord(raw);
      if (!rec) return;
      if (KNOWN_NOTE_IDS && KNOWN_NOTE_IDS.indexOf(rec.note_id) < 0) return; // 只留已知
      if (records[rec.note_id]) return; // 去重
      records[rec.note_id] = rec;
      stats.captured++;
      if (rec.images_list && rec.images_list.length) {
        stats.with_images++;
        var anyCover = rec.images_list.some(function (im) {
          return im && (im.url || im.cover || im.thumb);
        });
        if (anyCover) stats.with_cover++;
      }
      if (rec.video_info) {
        stats.with_video_info++;
        var vi = JSON.stringify(rec.video_info);
        if (vi.indexOf("signed") >= 0 || vi.indexOf("token") >= 0) stats.with_signed++;
      }
    });
    logStats();
  }

  function logStats() {
    var matched = KNOWN_NOTE_IDS ? (KNOWN_NOTE_IDS.length || "?") : "?";
    console.log(
      "[B003 Capture] captured=" + stats.captured +
      " (known=" + matched + ") images=" + stats.with_images +
      " video_info=" + stats.with_video_info +
      " cover=" + stats.with_cover +
      " signed_resources=" + stats.with_signed
    );
  }

  // ---------- 拦截 fetch ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        try {
          resp.clone().json().then(function (data) { handleResponse(url, data); }).catch(function () {});
        } catch (e) {}
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // ---------- 拦截 XHR ----------
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__url = url;
    return origOpen.apply(this, arguments);
  };
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    var self = this;
    this.addEventListener("load", function () {
      try {
        if (self.__url && String(self.__url).indexOf("/note/user/posted") >= 0) {
          var data = JSON.parse(self.responseText);
          handleResponse(self.__url, data);
        }
      } catch (e) {}
    });
    return origSend.apply(this, arguments);
  };

  // ---------- 导出（安全） ----------
  window.__B003Export = function () {
    var safe = {};
    Object.keys(records).forEach(function (k) {
      safe[k] = sanitizeValue(records[k], ""); // 再次净化
    });
    var blob = new Blob([JSON.stringify(safe, null, 1)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "B003_creator_media_metadata_safe.json";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); }, 500);
    console.log("[B003 Capture] exported " + Object.keys(safe).length + " records (sanitized)");
    return Object.keys(safe).length;
  };

  console.log(
    "[B003 Capture] 监听已启动。请在「笔记管理 → 已发布」正常滚动页面，" +
    "页面自身请求 posted?page=N 会被自动收集。完成后执行 __B003Export() 导出。"
  );
})();
