// ============================================================================
// B003_PILOT20_RECOVER_CURRENT_NOTE_V1.js
// Stage 3A.7 — Pilot20 通用单条恢复工具（可在任意 B003 Published Playback Page 复用）
//
// 已验证路线（Pilot1 冻结，禁止再研究）：
//   Published Playback Page → 实际 MP4 → 普通 Full GET → 保存完整 bytes → ffprobe 为准
//
// 流程：
//   1. 从 window.location.pathname 读 /explore/{note_id} → CURRENT_NOTE_ID
//   2. Current Page Identity Gate：CURRENT_NOTE_ID 必须属于 Remaining19 Manifest
//   3. 实际播放视频 → 锁定当前 note 的 video/mp4 media resource
//   4. 普通 Full GET（不带 Range）→ 保存前只做 status/content-type/length/ftyp 基本检查
//   5. 保存 B003_{note_id}_FULL.mp4
//
// 安全纪律：不保存 location.search / xsec_token / cookie / auth / signed query；
//           Console 只输出安全摘要；Browser 不用 mdat/moof 字符串搜索作 hard gate。
//
// 执行：播放视频后 → __B003Pilot20RecoverCurrent()
// ============================================================================

(function () {
  "use strict";

  // 由 Harness 生成：Remaining 待恢复 note_id 集合（用户粘贴）
  var REMAINING_NOTE_IDS = ["6a0c5bcf0000000006035b71", "6a793c240000000029032c35", "6a2bf90a0000000021016392", "6a3bebde000000001101f594", "6a71c3300000000033036b66", "6a8192f90000000022015cbe", "6a7858c40000000032031a87", "6a21866000000000210174ec", "6a1ed6730000000006036ec0", "6a1c40b5000000000702d129", "6a461418000000001503f346", "69ccc361000000002003a03b", "6a64bd140000000013025d63", "6a14462e0000000007028a67", "69fdac61000000001f0064db", "69eb29150000000022025cfc", "69d495e9000000001f003a0d", "69bed64b000000002300425e", "6a49142300000000160277df", "69b2894f0000000004002d82"];

  var observed = { url: null, videoSrc: null };
  var result = null;

  // ---------- 读取当前 note_id ----------
  function currentNoteId() {
    var m = window.location.pathname.match(/\/explore\/([0-9a-f]{24})/);
    return m ? m[1] : null;
  }

  // ---------- Identity Gate ----------
  function identityGate() {
    var nid = currentNoteId();
    if (!nid) return { ok: false, status: "WRONG_PAGE", reason: "无法从路径读取 note_id" };
    if (REMAINING_NOTE_IDS.indexOf(nid) < 0) {
      return { ok: false, status: "NOT_IN_PILOT20", note_id: nid };
    }
    return { ok: true, note_id: nid };
  }

  // ---------- 观察 media resource ----------
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var p = origFetch.apply(this, args);
    try {
      var url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      p.then(function (resp) {
        var ct = (resp.headers && resp.headers.get && resp.headers.get("content-type")) || "";
        if (ct.indexOf("video/mp4") >= 0 || ct.indexOf("video") >= 0 ||
            url.toLowerCase().indexOf(".mp4") >= 0) {
          if (!observed.url) {
            observed.url = url;
            console.log("[Pilot20] media resource selected (video/mp4)");
          }
        }
      }).catch(function () {});
    } catch (e) {}
    return p;
  };

  // 观察 video element（playback 关联）
  document.addEventListener("loadeddata", function (ev) {
    var v = ev.target;
    if (v && v.tagName === "VIDEO" && v.currentSrc) {
      observed.videoSrc = v.currentSrc;
      console.log("[Pilot20] video playback linked (host not printed)");
    }
  }, true);

  // ---------- 保存 ----------
  window.__B003Pilot20RecoverCurrent = function () {
    var gate = identityGate();
    if (!gate.ok) return Promise.resolve(gate);
    var nid = gate.note_id;

    if (!observed.url) {
      return Promise.resolve({ ok: false, note_id: nid, status: "RESOURCE_DISCOVERED_NOT_SAVED",
                               reason: "未观察到 video/mp4 resource；请先播放视频" });
    }

    return fetch(observed.url).then(function (resp) {
      var ct = resp.headers.get("content-type") || "";
      var info = { note_id: nid, http_status: resp.status, content_type: ct };
      if (resp.status !== 200) {
        // 非 200：标记，不现场改架构
        return { ok: false, status: resp.status === 206 ? "STREAM_ONLY" : "RECOVERY_NEEDS_REVIEW",
                 ...info, note: "非 HTTP 200 完整响应，标 RECOVERY_NEEDS_REVIEW 继续下一条" };
      }
      if (ct.indexOf("video") < 0 && ct.indexOf("mp4") < 0) {
        return { ok: false, status: "RECOVERY_NEEDS_REVIEW", ...info,
                 note: "content-type 非 video" };
      }
      return resp.arrayBuffer().then(function (buf) {
        var actual = buf.byteLength;
        var u8 = new Uint8Array(buf);
        var ftyp = false;
        if (u8.length >= 16) {
          for (var i = 4; i < Math.min(64, u8.length - 4); i++) {
            if (String.fromCharCode(u8[i], u8[i + 1], u8[i + 2], u8[i + 3]) === "ftyp") { ftyp = true; break; }
          }
        }
        if (!ftyp || actual < 100000) {
          return { ok: false, status: "RECOVERY_NEEDS_REVIEW", ...info,
                   actual_length: actual, ftyp_present: ftyp };
        }
        // 保存
        var fn = "B003_" + nid + "_FULL.mp4";
        var blob = new Blob([buf], { type: "video/mp4" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = fn;
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { document.body.removeChild(a); }, 500);
        result = { note_id: nid, browser_recovery_status: "FULL_RESPONSE_SAVED",
                   http_status: 200, content_type: ct,
                   expected_length: resp.headers.get("content-length") || null,
                   actual_length: actual, ftyp_present: ftyp,
                   saved_filename: fn, timestamp: new Date().toISOString() };
        console.log("[Pilot20] SAVED " + fn + " (" + Math.round(actual / 1024) + "KB)");
        return result;
      });
    }).catch(function (e) {
      return { ok: false, note_id: nid, status: "RECOVERY_ERROR", error: String(e).slice(0, 80) };
    });
  };

  console.log("[Pilot20] 通用恢复工具就绪。打开目标 Pilot 笔记 → 播放视频 → 执行 __B003Pilot20RecoverCurrent()。");
})();
