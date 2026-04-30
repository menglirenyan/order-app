@echo off
setlocal
cd /d "%~dp0"
if not exist fy_print_client.exe (
  echo fy_print_client.exe not found. Run this file inside the folder that contains the exe.
  pause
  exit /b 1
)
if not exist config.json (
  echo config.json not found. Copy config.example.json to config.json and edit it first.
  pause
  exit /b 1
)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "FangyuanPrintClient" /t REG_SZ /d "\"%~dp0fy_print_client.exe\"" /f
echo Auto start installed for current Windows user.
pause
