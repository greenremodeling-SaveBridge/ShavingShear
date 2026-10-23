@echo off
chcp 65001 >nul
rem 다건물 기저선 검증 — 서울 비주거 건물을 무작위로 뽑아 같은 모델로 평가. 결과: backend\multi_check_out\summary.md
cd /d "%~dp0backend"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo 먼저 켜기.bat 을 한 번 실행해서 파이썬 패키지를 설치해 주세요.
  pause
  exit /b 1
)
echo 건물 30동 x 76개월 x 전기·가스 = 약 4,600번 호출해요. 20~40분 걸리고, 중간에 끊겨도 다시 실행하면 이어서 해요.
".venv\Scripts\python.exe" multi_check.py %*
echo.
echo 결과: %~dp0backend\multi_check_out\summary.md
pause
