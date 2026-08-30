// ============================================================================
// B003_PILOT1_RANGE_AWARE_RECOVERY_V2.js
// Stage 3A.6 — Pilot1 完整媒体 Range-Aware 重建（只处理 Pilot1，不扩 Pilot20）
//
// ⚠️ V2_RANGE_LOGIC_DEFECT_CONFIRMED（2026-08-30 浏览器实测）
//   Probe 实际返回 status=200, content_type=video/mp4, content_length=7579070（无 content-range）
//   → 该场景应走【Full GET 完整响应恢复】（见 B003_PILOT1_FULL_RESPONSE_RECOVERY_V3.js）
//   V2 的 Range 路线仅在 Probe 返回 206 + Content-Range 时才作为 fallback 使用。
//   修正：HTTP 206 Partial Content 对 Range Request 是【正常成功状态】，不得判失败。
//
// 目标：把该 note 实际加载的媒体资源重建为完整 MP4：
//       B003_6a8d75aa000000002503e3e2_FULL.mp4
//
// 流程：
//   Step1 Response Probe：请求 media resource，判断 HTTP 200 / 206，
//                         输出安全摘要（status/content-type/content-length/
//                         content-range/accept-ranges），不打印 URL
//   Step2a HTTP 200 → 保存完整 response bytes（等价 V3 Full GET）
//   Step2b HTTP 206 → 解析 Content-Range 得 TOTAL → 标准 Range 重建
//   Step3 首块从 byte 0 开始，验证 ftyp 存在，否则 STOP
//   Step4 每块验证 206 + Content-Range 一致，按 offset 严格顺序拼接
//   Step5 输出 FULL.mp4（不覆盖旧 V1 损坏文件）
//
// 安全纪律：只使用当前 Published Playback Page 已合法加载的 resource；
//           不破解 signature / 不伪造 token / 不绕过访问控制；
//           媒体 URL 只存在于浏览器运行时内存；不打印完整 URL / query。
// ============================================================================

(function () {
  "use strict";

  var NOTE_ID = "6a8d75aa000000002503e3e2";
  var OUT_NAME = "B003_" + NOTE_ID + "_FULL.mp4";
  var CHUNK = 2 * 1024 * 1024;   // 2MB / chunk；并发 1

  // 内存中已观察到的 media resource URL（仅内存，不打印完整）
  var mediaUrls = [];

  // ---------- 观察 fetch（记录 resource URL 供后续探测，仅内存） ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        if (ct.indexOf("video") >= 0 || ct.indexOf("mp4") >= 0 || url.toLowerCase().indexOf(".mp4") >= 0) {
          if (mediaUrls.indexOf(url) < 0) mediaUrls.push(url);
          console.log("[B003 RangeV2] observed media resource (host not printed)");
        }
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // ---------- 工具 ----------
  function safeSummary(resp) {
    // 只记录安全 headers；不打印 URL / query
    return {
      status: resp.status,
      content_type: resp.headers.get("content-type") || "",
      content_length: resp.headers.get("content-length") || "",
      content_range: resp.headers.get("content-range") || "",
      accept_ranges: resp.headers.get("accept-ranges") || "",
    };
  }

  function bytes2Hex(buf, off, n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(("0" + buf[off + i].toString(16)).slice(-2));
    return out.join("");
  }

  function hasFtyp(buf) {
    // 检查前 64 bytes 是否含 ftyp box（ftyp + 4字节size + 'ftyp'）
    if (!buf || buf.length < 16) return false;
    for (var i = 4; i < Math.min(64, buf.length - 4); i++) {
      if (String.fromCharCode(buf[i], buf[i + 1], buf[i + 2], buf[i + 3]) === "ftyp") return true;
    }
    return false;
  }

  // ---------- Step1: Response Probe ----------
  window.__B003RangeProbe = function () {
    if (mediaUrls.length === 0) {
      return { ok: false, reason: "NO_MEDIA_URL_IN_MEMORY",
               hint: "请确认视频已实际播放后重试" };
    }
    var url = mediaUrls[0];
    return fetch(url).then(function (resp) {
      var s = safeSummary(resp);
      console.log("[B003 RangeV2] PROBE " + JSON.stringify(s));
      return { ok: true, probe: s, media_count: mediaUrls.length };
    }).catch(function (e) {
      return { ok: false, reason: "PROBE_FETCH_ERROR", error: String(e).slice(0, 80) };
    });
  };

  // ---------- Step2b+3+4: Range Reconstruction ----------
  function fetchRange(url, start, end) {
    return fetch(url, { headers: { "Range": "bytes=" + start + "-" + end } })
      .then(function (resp) {
        if (resp.status !== 206) {
          return { ok: false, status: resp.status, range: "bytes=" + start + "-" + end };
        }
        var cr = resp.headers.get("content-range") || "";
        // 校验 Content-Range 与请求一致
        if (cr.indexOf("bytes " + start + "-" + end + "/") < 0 &&
            cr.indexOf("bytes " + start + "-") !== 0) {
          return { ok: false, status: 206, range_mismatch: cr, requested: "bytes=" + start + "-" + end };
        }
        return resp.arrayBuffer().then(function (ab) {
          return { ok: true, start: start, end: end,
                   cr: cr, length: ab.byteLength, buf: ab };
        });
      });
  }

  window.__B003RangeReconstruct = function (probe) {
    if (mediaUrls.length === 0) return Promise.resolve({ ok: false, reason: "NO_MEDIA_URL" });
    var url = mediaUrls[0];
    var total = null;
    if (probe && probe.content_range) {
      var m = probe.content_range.match(/bytes \d+-\d+\/(\d+)/);
      if (m) total = parseInt(m[1], 10);
    }
    var steps = [];

    // 探测第一块（byte 0 起）验证 ftyp
    return fetchRange(url, 0, Math.min(CHUNK - 1, (total || 4 * 1024 * 1024) - 1))
      .then(function (r0) {
        if (!r0.ok) {
          steps.push({ step: "byte0_probe", status: r0.status || "FAIL" });
          return { ok: false, reason: "FIRST_RANGE_FAILED",
                   detail: r0.range_mismatch || ("status=" + r0.status),
                   steps: steps };
        }
        steps.push({ step: "byte0_probe", status: 206, length: r0.length,
                     cr: r0.cr, ftyp_present: hasFtyp(new Uint8Array(r0.buf)) });
        console.log("[B003 RangeV2] byte0 probe len=" + r0.length +
                    " ftyp=" + hasFtyp(new Uint8Array(r0.buf)));
        if (!hasFtyp(new Uint8Array(r0.buf))) {
          return { ok: false, reason: "NOT_STANDARD_MP4_RESOURCE",
                   detail: "byte0 无 ftyp；不继续全量下载",
                   steps: steps };
        }
        // 确定 total（从 r0 Content-Range）
        var m = r0.cr.match(/bytes \d+-\d+\/(\d+)/);
        total = m ? parseInt(m[1], 10) : total;
        if (!total) {
          return { ok: false, reason: "TOTAL_UNKNOWN",
                   detail: "Content-Range 无 TOTAL，无法 range 重建",
                   steps: steps };
        }
        steps.push({ step: "total_media_size", total: total });
        return assemble(url, total, steps);
      });
  };

  function assemble(url, total, steps) {
    var chunks = [];
    var pos = 0;
    function next() {
      if (pos >= total) return Promise.resolve(chunks);
      var end = Math.min(pos + CHUNK - 1, total - 1);
      return fetchRange(url, pos, end).then(function (r) {
        if (!r.ok) {
          steps.push({ step: "chunk_fail", at: pos, status: r.status || "FAIL",
                       detail: r.range_mismatch || "" });
          return { FAILED: true };
        }
        steps.push({ step: "chunk", range: "bytes=" + r.start + "-" + r.end, length: r.length });
        chunks.push(r.buf);
        pos = end + 1;
        return next();
      });
    }
    return next().then(function (res) {
      if (res && res.FAILED) {
        return { ok: false, reason: "INCOMPLETE_CHUNK_SEQUENCE", steps: steps };
      }
      // 严格顺序合并
      var totalLen = chunks.reduce(function (s, b) { return s + b.byteLength; }, 0);
      var full = new Uint8Array(totalLen);
      var off = 0;
      chunks.forEach(function (b) {
        full.set(new Uint8Array(b), off);
        off += b.byteLength;
      });
      // Browser-side quick gate
      var ftyp = hasFtyp(full);
      var text = "";
      for (var i = 0; i < full.length && i < 400; i++) {
        text += String.fromCharCode(full[i]);
      }
      var moov = text.indexOf("moov") >= 0;
      var mdat = text.indexOf("mdat") >= 0 || text.indexOf("moof") >= 0;
      steps.push({ step: "container_gate", ftyp: ftyp, moov_head: moov,
                   mdat_or_moof_head: mdat, total_bytes: totalLen });
      if (!ftyp || (!mdat && !moov)) {
        return { ok: false, reason: "CONTAINER_GATE_FAILED",
                 detail: "ftyp=" + ftyp + " moov_head=" + moov + " mdat_head=" + mdat,
                 steps: steps };
      }
      // 保存 FULL.mp4（不覆盖旧 V1）
      var blob = new Blob([full], { type: "video/mp4" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = OUT_NAME;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { document.body.removeChild(a); }, 500);
      return { ok: true, total_bytes: totalLen, sha_ready: true,
               container: { ftyp: ftyp, moov: moov, mdat: mdat },
               steps: steps };
    });
  }

  console.log("[B003 RangeV2] 监听已启动。请确保 Pilot1 视频已播放。" +
              "执行 __B003RangeProbe() 探测，再执行 __B003RangeReconstruct(probe) 重建完整 MP4。");
})();
