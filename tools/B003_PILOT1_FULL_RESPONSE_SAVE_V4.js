// ============================================================================
// B003_PILOT1_FULL_RESPONSE_SAVE_V4.js
// Stage 3A.6 — Pilot1 完整响应保存 V4（Container 最终验证交给 ffprobe）
//
// 依据：V3 Full GET 已确认
//   status = 200, content_type = video/mp4, expected_length = actual_length = 7579070
//   browser_gate: ftyp TRUE / moov TRUE / mdat_or_moof FALSE（JS 简易扫描局限）
// → Browser mdat 扫描失败【不再阻止文件落盘】；最终 Container Truth 由 ffprobe 判定。
//
// 保存前只验证：
//   status == 200
//   content-type 含 video/mp4
//   actual_byte_length == 7579070（或严格合理一致）
//   ftyp == TRUE
//
// 落盘身份：FULL_RESPONSE_BYTES_UNVERIFIED_CONTAINER（非 EXACT_PUBLISHED_MEDIA）
// 输出：B003_6a8d75aa000000002503e3e2_FULL_V4.mp4（不覆盖 V1/V2/V3）
//
// 安全纪律：完整 media URL 仅浏览器运行时内存；Console 只输出
//           HTTP status / content type / expected length / actual length / ftyp / save success；
//           不打印 URL 全文 / query / 凭证。
// ============================================================================

(function () {
  "use strict";

  var NOTE_ID = "6a8d75aa000000002503e3e2";
  var OUT_NAME = "B003_" + NOTE_ID + "_FULL_V4.mp4";
  var EXPECTED_LENGTH = 7579070;

  var observed = { url: null };

  // ---------- 观察 fetch：捕获与 Probe/V3 相同的 video/mp4 resource ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        if (ct.indexOf("video") >= 0 || ct.indexOf("mp4") >= 0 || url.toLowerCase().indexOf(".mp4") >= 0) {
          if (!observed.url) {
            observed.url = url;
            console.log("[B003 V4] resource_selected = TRUE (content-type " + ct + ")");
          }
        }
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  function hasFtyp(buf) {
    if (!buf || buf.length < 16) return false;
    for (var i = 4; i < Math.min(64, buf.length - 4); i++) {
      if (String.fromCharCode(buf[i], buf[i + 1], buf[i + 2], buf[i + 3]) === "ftyp") return true;
    }
    return false;
  }

  // ---------- 保存：普通 GET（不带 Range）→ 验证 → 落盘 ----------
  window.__B003SaveFullV4 = function () {
    if (!observed.url) {
      return Promise.resolve({ ok: false, reason: "NO_MEDIA_URL_IN_MEMORY",
                               hint: "请确保视频已实际播放后重试" });
    }
    return fetch(observed.url).then(function (resp) {
      var ct = resp.headers.get("content-type") || "";
      var info = { status: resp.status, content_type: ct,
                   expected_length: EXPECTED_LENGTH };
      if (resp.status !== 200) {
        return { ok: false, reason: "NOT_200", ...info };
      }
      if (ct.indexOf("video/mp4") < 0 && ct.indexOf("mp4") < 0) {
        return { ok: false, reason: "NOT_VIDEO_MP4", ...info };
      }
      return resp.arrayBuffer().then(function (buf) {
        var actual = buf.byteLength;
        var lenOk = actual === EXPECTED_LENGTH ||
                    Math.abs(actual - EXPECTED_LENGTH) <= Math.max(1024, EXPECTED_LENGTH * 0.01);
        if (!lenOk) {
          return { ok: false, reason: "LENGTH_MISMATCH", ...info, actual_length: actual };
        }
        var u8 = new Uint8Array(buf);
        var ftyp = hasFtyp(u8);
        if (!ftyp) {
          return { ok: false, reason: "NO_FTYP", ...info, actual_length: actual };
        }
        // 通过：保存（不因 mdat/moof 简易扫描失败阻止；Container Truth 交 ffprobe）
        var blob = new Blob([buf], { type: "video/mp4" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = OUT_NAME;
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { document.body.removeChild(a); }, 500);
        return {
          ok: true, save_status: "SAVED",
          status: 200, content_type: ct,
          expected_length: EXPECTED_LENGTH, actual_length: actual,
          ftyp: ftyp,
          identity: "FULL_RESPONSE_BYTES_UNVERIFIED_CONTAINER",
          filename: OUT_NAME,
          next: "交 Harness 本地 ffprobe/decode/duration 验证",
        };
      });
    }).catch(function (e) {
      return { ok: false, reason: "FETCH_ERROR", error: String(e).slice(0, 80) };
    });
  };

  console.log("[B003 V4] 监听已启动。请确保 Pilot1 视频已实际播放。" +
              "执行 __B003SaveFullV4() 保存 B003_" + NOTE_ID + "_FULL_V4.mp4。");
})();
