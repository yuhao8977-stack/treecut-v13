Set ws = CreateObject("WScript.Shell")
ws.Environment("PROCESS")("PYTHONPATH") = "C:\Users\admin\github\treecut-v13\src"
ws.Environment("PROCESS")("TREECUT_DATA_ROOT") = "E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
ws.Environment("PROCESS")("TREECUT_MODEL_ROOT") = "E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\models"
ws.Environment("PROCESS")("HF_HUB_OFFLINE") = "1"
ws.CurrentDirectory = "C:\Users\admin\github\treecut-v13"
ws.Run """E:\树剪整理\02_安装程序\TreeCut_v13\runtime\pythonw.exe"" -m treecut.desktop", 0, False