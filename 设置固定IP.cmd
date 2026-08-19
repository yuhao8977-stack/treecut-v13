@echo off
chcp 65001 >nul
echo ============================================
echo   树剪主机固定 IP 设置工具
echo   （需要以管理员身份运行）
echo ============================================
echo 正在把本机 WLAN 的 IP 固定为 192.168.1.110 ...
netsh interface ipv4 set address name="WLAN" static 192.168.1.110 255.255.255.0 192.168.1.1
if errorlevel 1 (
  echo 设置失败：请右键本文件 - 以管理员身份运行。
  pause
  exit /b 1
)
netsh interface ipv4 set dns name="WLAN" static 202.96.128.166
echo.
echo 固定成功！本机新 IP：192.168.1.110
echo 以后树剪下载地址为：http://192.168.1.110:8001/
echo 主机管理端地址为：http://192.168.1.110:8766
echo.
echo 注意：设置后若本机网络短暂断开是正常的，几秒后恢复。
pause
