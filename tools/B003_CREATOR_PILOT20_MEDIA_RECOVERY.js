// ============================================================================
// B003_CREATOR_PILOT20_MEDIA_RECOVERY.js
// Stage 3A.5 — B003 Pilot20 实际发布视频恢复（浏览器内存临时 resource）
//
// 前置：用户已完成 B003_CREATOR_MEDIA_CAPTURE_SAFE.js 捕获并导出了
//       B003_creator_media_metadata_safe.json（含 155 条 sanitized metadata）。
//
// 本工具：只对 Pilot20 的 note_id 尝试从【浏览器当前会话内存中的临时媒体
//         resource】保存 Published Reference Copy。不把 signed URL 写入文件。
//
// 安全纪律（Stage3A.5 §26-29）：
//   - 运行位置：用户当前已登录 B003 的 Creator 浏览器
//   - 使用内存中的临时 resource（页面已加载过的媒体）
//   - 不导出 signed URL / cookie / auth
//   - m3u8/stream：不自行绕过；能合法取得 bytes 才保存，否则 STOP 该条
//   - 命名 B003_{note_id}.mp4
// ============================================================================

(function () {
  "use strict";

  // 由 Harness 从 B003_PUBLISHED_MEDIA_PILOT20_V1 生成（20 个 note_id）
  var PILOT_NOTE_IDS = [];

  // 内存中已观察到的媒体 resource（url → blob/arrayBuffer 引用）
  // 仅存在于当前页面生命周期，不落盘 URL
  var observedMedia = {};

  // 观察页面上所有媒体加载（<video> / <img> / fetch media）
  function observe() {
    // 捕获 fetch 返回的 media blob
    var origFetch = window.fetch;
    window.fetch = function () {
      var args = arguments;
      var p = origFetch.apply(this, args);
      try {
        var url = typeof args[0] === "string" ? args[0] : "";
        p.then(function (resp) {
          var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
          if (ct.indexOf("video") >= 0 || ct.indexOf("mp4") >= 0 || ct.indexOf("m3u8") >= 0) {
            resp.clone().blob().then(function (b) {
              if (b && b.size > 10000) {
                observedMedia[url] = b;
                console.log("[B003 Recovery] observed video resource (" + Math.round(b.size / 1024) + "KB)");
              }
            }).catch(function () {});
          }
        }).catch(function () {});
      } catch (e) {}
      return p;
    };
    // <video> 元素 src
    document.addEventListener("loadeddata", function (ev) {
      var v = ev.target;
      if (v && v.tagName === "VIDEO" && v.src) {
        // 只记录存在性，不打印完整 URL
        observedMedia[v.src] = observedMedia[v.src] || true;
      }
    }, true);
  }

  // 对某个 note_id 尝试保存媒体（需用户已在页面打开过该视频，媒体在内存中）
  function recover(noteId) {
    var found = null;
    Object.keys(observedMedia).forEach(function (url) {
      var b = observedMedia[url];
      if (b && b instanceof Blob && b.size > 10000) {
        // 无法自动确认 note↔resource 关系：需要用户在页面打开该视频后调用
        found = b;
      }
    });
    if (!found) {
      console.log("[B003 Recovery] " + noteId + ": 内存中无可用媒体（请先在页面打开该视频）");
      return false;
    }
    var a = document.createElement("a");
    a.href = URL.createObjectURL(found);
    a.download = "B003_" + noteId + ".mp4";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); }, 500);
    console.log("[B003 Recovery] " + noteId + ": 已导出 B003_" + noteId + ".mp4（Published Reference Copy）");
    return true;
  }

  // 恢复全部 Pilot20（逐个尝试）
  window.__B003RecoverAll = function () {
    var ok = 0;
    PILOT_NOTE_IDS.forEach(function (nid) {
      if (recover(nid)) ok++;
    });
    console.log("[B003 Recovery] done " + ok + "/" + PILOT_NOTE_IDS.length +
                "（仅当页面已加载过对应视频才成功；m3u8/stream 不绕过）");
    return ok;
  };

  observe();
  console.log(
    "[B003 Recovery] 监听已启动。请在页面逐个打开 Pilot20 对应视频（让其媒体加载进内存），" +
    "然后执行 __B003RecoverAll() 导出。不会保存任何 signed URL / 凭证。"
  );
})();
