// ============================================================================
// B003_PILOT1_PUBLISHED_VIDEO_RECOVERY_V1.js
// Stage 3A.6 — Pilot1 实际发布视频 bytes 恢复（浏览器内存临时 resource）
//
// 目标：在【已打开并正常播放该 Published Note 的浏览器页面】中，
//       将该 note 实际加载的 MP4 媒体 bytes 保存为：
//       B003_6a8d75aa000000002503e3e2.mp4
//
// 安全纪律：
//   - 只使用当前浏览器内存中页面自己已加载的 media resource
//   - 不持久保存 xsec_token / cookie / authorization / session / signed query / 完整临时 URL
//   - 若 MP4 resource 带 query：仅在浏览器内存中使用，绝不写入文件
//   - Console 不打印完整媒体 URL
//   - 最终只保存：video bytes + note_id + 媒体技术 metadata
// ============================================================================

(function () {
  "use strict";

  var NOTE_ID = "6a8d75aa000000002503e3e2";   // Pilot1
  var FILE_NAME = "B003_" + NOTE_ID + ".mp4";

  // 观察到的 media resource（URL → Blob），仅内存
  var mediaMap = {};

  // ---------- 拦截 fetch（媒体 resource） ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        if (ct.indexOf("video") >= 0 || ct.indexOf("mp4") >= 0 || url.toLowerCase().indexOf(".mp4") >= 0) {
          resp.clone().blob().then(function (b) {
            if (b && b.size > 50000) {
              mediaMap[url] = b;
              console.log("[B003 Recovery] observed video blob: " + Math.round(b.size / 1024) + "KB (URL not printed)");
            }
          }).catch(function () {});
        }
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // ---------- <video> 元素 src ----------
  document.addEventListener("loadeddata", function (ev) {
    var v = ev.target;
    if (v && v.tagName === "VIDEO" && v.currentSrc) {
      // 记录存在性（不打印 URL）；尝试经 fetch 或 video 本身取 bytes
      console.log("[B003 Recovery] video element loaded (currentSrc host not printed)");
      tryRecoverFromVideo(v);
    }
  }, true);

  // ---------- 从 video 元素直接取 bytes ----------
  function tryRecoverFromVideo(v) {
    try {
      if (v.src && v.src.indexOf("blob:") === 0) {
        // blob URL：尝试经 fetch 取 bytes
        fetch(v.src).then(function (r) { return r.blob(); }).then(function (b) {
          if (b && b.size > 50000) {
            mediaMap["blob:" + NOTE_ID] = b;
            console.log("[B003 Recovery] blob bytes captured: " + Math.round(b.size / 1024) + "KB");
          }
        }).catch(function () {});
      }
    } catch (e) {}
  }

  // ---------- 恢复并保存 ----------
  window.__B003RecoverPilot1 = function () {
    var urls = Object.keys(mediaMap);
    if (urls.length === 0) {
      console.log("[B003 Recovery] 内存中无媒体 blob。请确保视频已实际播放（loadeddata 触发），再重试。");
      return { ok: false, reason: "NO_MEDIA_IN_MEMORY" };
    }
    // 取最大的 blob（通常是完整视频）
    var best = null, bestUrl = null;
    urls.forEach(function (u) {
      var b = mediaMap[u];
      if (b && b instanceof Blob && (!best || b.size > best.size)) {
        best = b;
        bestUrl = u;
      }
    });
    if (!best) {
      console.log("[B003 Recovery] 无可用媒体 bytes。");
      return { ok: false, reason: "NO_VALID_BLOB" };
    }
    // 保存（浏览器下载）；URL 仅用于本次下载，不写入文件/log
    var a = document.createElement("a");
    a.href = URL.createObjectURL(best);
    a.download = FILE_NAME;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); }, 500);

    // 技术 metadata（不含 URL）
    var meta = {
      note_id: NOTE_ID,
      filename: FILE_NAME,
      size_bytes: best.size,
      mime_type: best.type || "video/mp4",
      captured_at: new Date().toISOString(),
      source: "BROWSER_MEMORY_FROM_PUBLISHED_PLAYBACK",
      url_origin_only: bestUrl ? (bestUrl.split("/")[2] || "unknown") : "unknown", // 仅 host
    };
    console.log("[B003 Recovery] 已触发下载 " + FILE_NAME + " (" + Math.round(best.size / 1024) + "KB)");
    console.log("[B003 Recovery] metadata=" + JSON.stringify(meta));
    return { ok: true, size: best.size, meta: meta };
  };

  console.log("[B003 Recovery] 监听已启动。请确保 Pilot1 视频已在页面播放，" +
              "然后执行 __B003RecoverPilot1() 保存 B003_" + NOTE_ID + ".mp4。不保存 signed URL / 凭证。");
})();
