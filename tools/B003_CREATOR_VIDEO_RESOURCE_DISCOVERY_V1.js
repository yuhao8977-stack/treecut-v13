// ============================================================================
// B003_CREATOR_VIDEO_RESOURCE_DISCOVERY_V1.js
// Stage 3A.6 — Pilot1 技术侦察：Creator note-detail 页面视频资源来源判断
//
// 用途：用户打开 1 条 B003 Pilot 的 Creator note-detail 页面后，观察页面【自身】
//       加载视频时产生的网络资源，判断实际发布视频 bytes 能否合法取得。
//
// 只记录（§20）：resource type / host / path pattern / mime / content length /
//               是否 blob / 是否 mp4 / 是否 stream（HLS/DASH）
// 不记录：signed URL 完整 query / token / signature / credential
//
// 判定结果：__B003VideoResult() 返回分类
//   DIRECT_VIDEO_BYTES_AVAILABLE / BROWSER_AUTHENTICATED_VIDEO_BYTES_AVAILABLE
//   / STREAM_ONLY / METADATA_ONLY / BLOCKED
// ============================================================================

(function () {
  "use strict";

  var seen = {};   // 去重：host+path
  var videoResources = [];

  function sanitizeUrl(url) {
    try {
      var u = new URL(url);
      return {
        host: u.host,
        path: u.pathname,
        isBlob: url.indexOf("blob:") === 0,
        isMp4: u.pathname.toLowerCase().endsWith(".mp4") ||
               u.pathname.toLowerCase().endsWith(".webm"),
        isStream: u.pathname.indexOf(".m3u8") >= 0 || u.pathname.indexOf("dash") >= 0,
        // 不保存 query / token / signature
      };
    } catch (e) {
      return { host: "", path: url.slice(0, 60), isBlob: url.indexOf("blob:") === 0,
               isMp4: false, isStream: false };
    }
  }

  function record(url, mime, length) {
    if (!url) return;
    var s = sanitizeUrl(url);
    var key = s.host + s.path;
    if (seen[key]) return;
    seen[key] = true;
    var isVideo = mime && (mime.indexOf("video") >= 0 || mime.indexOf("mp4") >= 0 ||
                           mime.indexOf("m3u8") >= 0);
    if (isVideo || s.isMp4 || s.isStream || s.isBlob) {
      videoResources.push({ host: s.host, path: s.path, mime: mime || "",
                            contentLength: length || null,
                            isBlob: s.isBlob, isMp4: s.isMp4, isStream: s.isStream });
      console.log("[B003 VideoDiscovery] observed: " +
                  (s.isMp4 ? "mp4" : s.isStream ? "stream" : s.isBlob ? "blob" : "video") +
                  " host=" + s.host + " path=" + (s.path.slice(0, 50)));
    }
  }

  // 拦截 fetch
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        var len = resp.headers.get && resp.headers.get("content-length");
        record(url, ct, len ? parseInt(len, 10) : null);
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // 拦截 XHR
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, url) {
    this.__u = url;
    return origOpen.apply(this, arguments);
  };
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    var self = this;
    this.addEventListener("load", function () {
      try {
        var ct = self.getResponseHeader("Content-Type") || "";
        var len = self.getResponseHeader("Content-Length");
        record(self.__u, ct, len ? parseInt(len, 10) : null);
      } catch (e) {}
    });
    return origSend.apply(this, arguments);
  };

  // 观察 video 元素
  document.addEventListener("loadedmetadata", function (ev) {
    var v = ev.target;
    if (v && v.tagName === "VIDEO" && v.currentSrc) {
      record(v.currentSrc, "video", null);
    }
  }, true);

  window.__B003VideoResult = function () {
    var anyMp4 = videoResources.some(function (r) { return r.isMp4; });
    var anyBlob = videoResources.some(function (r) { return r.isBlob; });
    var anyStream = videoResources.some(function (r) { return r.isStream; });
    var classification;
    if (anyMp4) classification = "DIRECT_VIDEO_BYTES_AVAILABLE";
    else if (anyBlob) classification = "BROWSER_AUTHENTICATED_VIDEO_BYTES_AVAILABLE";
    else if (anyStream) classification = "STREAM_ONLY";
    else if (videoResources.length > 0) classification = "METADATA_ONLY";
    else classification = "BLOCKED";
    console.log("[B003 VideoDiscovery] resources=" + videoResources.length +
                " classification=" + classification);
    return { classification: classification, count: videoResources.length,
             resources: videoResources.map(function (r) {
               return { host: r.host, path: r.path.slice(0, 60), mime: r.mime,
                        isMp4: r.isMp4, isBlob: r.isBlob, isStream: r.isStream };
             }) };
  };

  console.log("[B003 VideoDiscovery] 监听已启动。请打开 1 条 B003 Pilot 的 Creator note-detail，" +
              "等待视频加载后执行 __B003VideoResult() 获取分类。不保存 signed URL / 凭证。");
})();
