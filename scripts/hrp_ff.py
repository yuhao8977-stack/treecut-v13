# -*- coding: utf-8 -*-
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
WORK = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\hrp_work")
FF = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
tf = WORK / "_t.txt"
tf.write_text("PAIR 01", encoding="utf-8")
FONT = "C\\:/Windows/Fonts/msyh.ttc"
tfq = str(tf).replace("\\", "/").replace(":", "\\:")
vf = (f"drawtext=fontfile={FONT}:textfile='{tfq}':fontsize=44:fontcolor=white:"
      f"x=(w-text_w)/2:y=520")
r = subprocess.run([FF, "-y", "-f", "lavfi", "-i", "color=black:s=720x1280:r=30:d=1",
                    "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-an", str(WORK / "_t.mp4")], capture_output=True, timeout=120)
print("rc", r.returncode)
print(r.stderr.decode("utf-8", errors="replace")[-800:])
