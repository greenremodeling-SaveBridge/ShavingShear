@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0backend"
set PYTHONUTF8=1
set PORT=8000

rem ---- python ----
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopy

rem ---- broken venv (copied from another PC)? remove it ----
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import uvicorn, fastapi" >nul 2>nul || (
    echo [정리] 다른 PC에서 만든 .venv 라서 지우고 새로 설치해요...
    rmdir /s /q .venv
  )
)

rem ---- first run: venv + packages ----
if not exist ".venv\Scripts\python.exe" (
  echo [준비] 처음 한 번만 파이썬 패키지를 설치해요. 1~3분 걸려요...
  %PY% -m venv .venv || goto nopy
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto fail
)

rem ---- already running? ----
curl -s -o nul -m 2 http://localhost:%PORT%/api/demo && (
  echo 이미 켜져 있어요.
  start "" http://localhost:%PORT%/app/
  goto end
)

echo 세이빙 셰어를 켜는 중이에요...
start "saving-share-server" /b ".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port %PORT%
set /a N=0
:wait
set /a N+=1
if %N% GTR 60 goto slow
timeout /t 1 /nobreak >nul
curl -s -o nul -m 2 http://localhost:%PORT%/api/demo || goto wait

start "" http://localhost:%PORT%/app/
echo.
echo  켜졌어요  →  http://localhost:%PORT%/app/
echo  이 창을 닫으면 꺼져요. (끄기.bat 으로 꺼도 돼요)
echo.
goto end

:slow
echo 60초 안에 켜지지 않았어요. 위 메시지를 확인해 주세요.
pause
goto end

:nopy
echo 파이썬 3.9 이상이 필요해요: https://www.python.org/downloads/
echo 설치할 때 "Add python.exe to PATH" 를 꼭 체크해 주세요.
pause
goto end

:fail
echo 패키지 설치에 실패했어요. 인터넷 연결을 확인하고 다시 실행해 주세요.
rmdir /s /q .venv
pause

:end
endlocal
