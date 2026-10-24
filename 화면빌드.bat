@echo off
chcp 65001 >nul
rem 화면(frontend)을 고친 뒤 다시 빌드 → backend\web\index.html 만 바꾼다. Node.js 18 이상 필요
rem (빌드가 web\backup.json 을 읽어서, backend\web 에서 먼저 복사해 둔다)
if not exist "%~dp0web" mkdir "%~dp0web"
copy /y "%~dp0backend\web\backup.json" "%~dp0web\backup.json" >nul
cd /d "%~dp0frontend"
where npm >nul 2>nul || (echo Node.js 가 필요해요: https://nodejs.org/ & pause & exit /b 1)
rem 패키지가 바뀌었을 수 있어서(예: three) 매번 확인 · 이미 있으면 몇 초면 끝나요
call npm install --no-audit --no-fund || (pause & exit /b 1)
call npm run build || (pause & exit /b 1)
copy /y "%~dp0web\index.html" "%~dp0backend\web\index.html" >nul
echo 화면을 새로 빌드했어요. 켜져 있으면 브라우저를 새로고침하세요.
pause
