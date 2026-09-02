# -*- coding: utf-8 -*-
"""G2: qwen2.5vl 时序动作探测(L2 候选, 禁当L3) — 每资产5帧 × 逐帧调用, 断点续跑。"""
import base64, json, re, subprocess, sys, time, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FRD = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\g2_frames")
FRD.mkdir(parents=True, exist_ok=True)
RES = OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json"
man = json.load(open(OUT / "_g2_probe_manifest.json", encoding="utf-8"))

Q_TMPL = {
    "EXTEND": ("这一帧中, 可伸缩桌面/岛台是否正在被拉出加宽或被收回? 请严格按以下状态回答一行 state=...;"
               " 再一行 object=桌面/轨道插座/其他; 再一行 desc=一句话画面内容(什么在动/人在做什么)。"
               "状态只能是: NOT_PRESENT(画面无此对象或未发生伸缩) | OBJECT_PRESENT(伸缩桌可见但静止未动) | "
               "ACTION_START(手刚拉动/开始变宽) | ACTION_IN_PROGRESS(桌面正在移动加宽/收回) | "
               "ACTION_END(已拉到位或收回完毕)。若画面主体是插座/其他功能而非伸缩动作, 必须回答 NOT_PRESENT。"),
    "DRAWER": ("这一帧中, 抽屉是否正在被拉开或被推回? 回答 state=NOT_PRESENT|OBJECT_PRESENT(抽屉可见未动)|"
               "ACTION_START|ACTION_IN_PROGRESS(正在开/关)|ACTION_END; 一行 object=上层薄抽/下层抽屉/其他; "
               "一行 desc=一句话画面内容(抽屉位置、人在做什么)。"),
    "SOCKET": ("这一帧中, 是否正在发生 插头插入插座/插座供电使用/轨道插座滑动? 回答 state=NOT_PRESENT|"
               "OBJECT_PRESENT(插座可见未插)|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; 一行 object=轨道插座/插头/电器; "
               "一行 desc=一句话画面内容。"),
    "CABINET": ("这一帧中, 柜门是否正在被打开或被关闭? 回答 state=NOT_PRESENT|OBJECT_PRESENT(柜门可见未开)|"
                "ACTION_START|ACTION_IN_PROGRESS|ACTION_END; 一行 object=柜门/抽屉/其他; 一行 desc=一句话画面内容。"),
    "STORAGE": ("这一帧中, 是否正在把物品放入收纳(抽屉/柜)或从中取出? 回答 state=NOT_PRESENT|"
                "OBJECT_PRESENT(收纳可见, 手未放物)|ACTION_START|ACTION_IN_PROGRESS|ACTION_END; "
                "一行 object=抽屉/柜子/物品; 一行 desc=一句话画面内容。"),
}
ACT_BY_GROUP = {"EXTEND_POS": "EXTEND", "EXTEND_HARDNEG": "EXTEND",
                "DRAWER_POS": "DRAWER", "SOCKET_POS": "SOCKET",
                "CABINET_POS": "CABINET", "STORAGE_POS": "STORAGE"}

def ask(b64, prompt):
    body = json.dumps({"model": "qwen2.5vl:7b", "stream": False, "options": {"temperature": 0.0},
                       "messages": [{"role": "user", "content": prompt, "images": [b64]}]}).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]

def grab(path, t, idx, fidx):
    png = FRD / f"m{idx}_f{fidx}.jpg"
    if png.exists() and png.stat().st_size > 5000:
        return png
    r = subprocess.run([FF, "-y", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(png)], capture_output=True, timeout=90)
    return png if r.returncode == 0 and png.exists() and png.stat().st_size > 5000 else None

out = []
done = set()
if RES.exists():
    old = json.loads(RES.read_text(encoding="utf-8"))
    out = old.get("items", [])
    done = {(it["media_id"], it["frame_idx"]) for it in out}
print("total frames:", sum(len(m["frames"]) for m in man), "done:", len(done), flush=True)
t0 = time.time()
for mi, m in enumerate(man):
    act = ACT_BY_GROUP[m["group"]]
    prompt = Q_TMPL[act]
    for fi, fr in enumerate(m["frames"]):
        if (m["media_id"], fi) in done:
            continue
        if fr.get("t_s") is None:
            out.append({"media_id": m["media_id"], "frame_idx": fi, "error": "no_dur"})
            continue
        png = grab(m["full_path"], fr["t_s"], m["media_id"], fi)
        if png is None:
            out.append({"media_id": m["media_id"], "frame_idx": fi, "t_s": fr["t_s"],
                        "error": "frame_grab_failed"})
            continue
        try:
            txt = ask(base64.b64encode(png.read_bytes()).decode(), prompt)
        except Exception as e:
            time.sleep(2)
            try:
                txt = ask(base64.b64encode(png.read_bytes()).decode(), prompt)
            except Exception as e2:
                out.append({"media_id": m["media_id"], "frame_idx": fi, "t_s": fr["t_s"],
                            "error": f"qwen_failed {str(e2)[:80]}"})
                continue
        out.append({"media_id": m["media_id"], "group": m["group"], "frame_idx": fi,
                    "frac": fr["frac"], "t_s": round(fr["t_s"], 2), "qwen_l2_raw": txt,
                    "level": "L2_VISUAL_CANDIDATE"})
        RES.write_text(json.dumps({"level": "L2_VISUAL_CANDIDATE",
                                   "note": "qwen2.5vl=L2 时序候选; 非L3; 仅用于动作候选与有界校准",
                                   "items": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[media {m['media_id']}] done, elapsed {(time.time()-t0)/60:.0f}min", flush=True)
print(f"DONE total {len(out)} in {(time.time()-t0)/60:.1f}min")
