@echo off
chcp 65001 >nul
set PORT=8000
set FOUND=
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  taskkill /pid %%p /f >nul 2>nul
  set FOUND=1
)
if defined FOUND (echo 껐어요.) else (echo 꺼져 있어요.)
timeout /t 2 /nobreak >nul
