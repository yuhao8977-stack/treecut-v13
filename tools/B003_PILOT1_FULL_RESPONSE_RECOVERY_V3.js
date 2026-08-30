// ============================================================================
// B003_PILOT1_FULL_RESPONSE_RECOVERY_V3.js
// Stage 3A.6 — Pilot1 完整视频 Full Response 恢复（普通 GET，不带 Range）
//
// 依据：__B003RangeProbe() 已确认
//   status = 200, content_type = video/mp4, content_length = 7579070（约 7.58MB）
//   Browser Observer 观察到 ≈7401KB blob（高度一致）
// → 优先 NORMAL_FULL_RESPONSE_RECOVERY：不发送 Range header，直接 GET
//
// 流程：
//   Step1 选定当前页面已观察到的 video/mp4 resource（资源身份绑定，仅内存）
//   Step2 普通 GET（不带 Range）→ response.arrayBuffer()
//   Step3 Length Gate：actual ≈ 7579070（合理范围内）
//   Step4 MP4 Container Gate：ftyp + moov + (mdat 或 moof+mdat)
//   Step5 保存 B003_6a8d75aa000000002503e3e2_FULL_V3.mp4（不覆盖 V1/V2 文件）
//
// 安全纪律：媒体完整 URL 只存在于浏览器运行时内存；Console 只输出
//           resource_selected/content_type/expected_length/actual_length/
//           container_check/download_status；不打印 URL/query/凭证。
// ============================================================================

(function () {
  "use strict";

  var NOTE_ID = "6a8d75aa000000002503e3e2";
  var OUT_NAME = "B003_" + NOTE_ID + "_FULL_V3.mp4";
  var EXPECTED_LENGTH = 7579070;   // Probe 确认的完整 Content-Length

  // 已观察到的 media resource（仅内存：url → blob）；绑定同一次 discovery 的 resource
  var observed = { url: null, blob: null };

  // ---------- 观察 fetch：捕获与 Probe 相同的 video/mp4 resource ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        if (ct.indexOf("video") >= 0 || ct.indexOf("mp4") >= 0 || url.toLowerCase().indexOf(".mp4") >= 0) {
          // 记录第一个（与 Probe 同源）resource；不打印 URL
          if (!observed.url) {
            observed.url = url;
            console.log("[B003 V3] resource_selected = TRUE (content-type " + ct + ")");
          }
          resp.clone().blob().then(function (b) {
            if (b && b.size > 100000) {
              // 若与 selected url 同源，记录 blob（备用）
              if (observed.url === url || !observed.blob) {
                observed.blob = b;
              }
            }
          }).catch(function () {});
        }
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // ---------- 工具 ----------
  function hasFtyp(buf) {
    if (!buf || buf.length < 16) return false;
    for (var i = 4; i < Math.min(64, buf.length - 4); i++) {
      if (String.fromCharCode(buf[i], buf[i + 1], buf[i + 2], buf[i + 3]) === "ftyp") return true;
    }
    return false;
  }

  function hasAtom(buf, atom) {
    var s = "";
    for (var i = 0; i < buf.length && i < 2000; i++) s += String.fromCharCode(buf[i]);
    return s.indexOf(atom) >= 0;
  }

  // ---------- Step2-5: Full GET + Gate + 保存 ----------
  window.__B003RecoverFullV3 = function () {
    if (!observed.url) {
      return Promise.resolve({ ok: false, reason: "NO_MEDIA_URL_IN_MEMORY",
                               hint: "请确保视频已实际播放（触发媒体 fetch）后重试" });
    }
    // 普通 GET，不带 Range
    return fetch(observed.url).then(function (resp) {
      var ct = resp.headers.get("content-type") || "";
      if (resp.status !== 200) {
        return { ok: false, reason: "NOT_200", status: resp.status, content_type: ct };
      }
      return resp.arrayBuffer().then(function (buf) {
        var actual = buf.byteLength;
        // Length Gate
        var lenOk = Math.abs(actual - EXPECTED_LENGTH) <= Math.max(1024, EXPECTED_LENGTH * 0.01);
        if (!lenOk) {
          // 若明显偏小（几百 KB / 1-2MB）→ PARTIAL_RESPONSE
          return { ok: false, reason: "PARTIAL_RESPONSE",
                   expected_length: EXPECTED_LENGTH, actual_length: actual, content_type: ct };
        }
        var u8 = new Uint8Array(buf);
        var ftyp = hasFtyp(u8);
        var moov = hasAtom(u8, "moov");
        var mdat = hasAtom(u8, "mdat") || hasAtom(u8, "moof");
        if (!ftyp || !moov || !mdat) {
          return { ok: false, reason: "CONTAINER_GATE_FAILED",
                   expected_length: EXPECTED_LENGTH, actual_length: actual,
                   container: { ftyp: ftyp, moov: moov, mdat_or_moof: mdat } };
        }
        // 保存 FULL_V3.mp4
        var blob = new Blob([buf], { type: "video/mp4" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = OUT_NAME;
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { document.body.removeChild(a); }, 500);
        return {
          ok: true, download_status: "TRIGGERED",
          resource_selected: true, content_type: ct,
          expected_length: EXPECTED_LENGTH, actual_length: actual,
          container_check: { ftyp: ftyp, moov: moov, mdat_or_moof: mdat },
          filename: OUT_NAME,
        };
      });
    }).catch(function (e) {
      return { ok: false, reason: "FETCH_ERROR", error: String(e).slice(0, 80) };
    });
  };

  console.log("[B003 V3] 监听已启动。请确保 Pilot1 视频已实际播放。" +
              "执行 __B003RecoverFullV3() 下载 B003_" + NOTE_ID + "_FULL_V3.mp4。");
})();
