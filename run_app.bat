@echo off
setlocal

cd /d "%~dp0"
title Compact Camera Battery Lookup

echo.
echo ==========================================
echo  Compact Camera Battery Lookup
echo ==========================================
echo.

where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo ERROR: Khong tim thay npm.cmd. Hay cai Node.js truoc.
  echo https://nodejs.org/
  pause
  exit /b 1
)

if not exist "public\data" (
  mkdir "public\data"
)

if exist "data\cameras.json" (
  echo Sync data JSON sang public\data ...
  copy /Y "data\*.json" "public\data\" >nul
)

if not exist "node_modules" (
  echo Chua co node_modules, dang chay npm install ...
  call npm.cmd install
  if errorlevel 1 (
    echo.
    echo ERROR: npm install failed.
    pause
    exit /b 1
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ok = $false; try { $r = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173/' -TimeoutSec 2; $ok = $r.StatusCode -eq 200 } catch {}; if ($ok) { exit 0 } else { exit 1 }"

if not errorlevel 1 (
  echo App dang chay san tai http://127.0.0.1:5173/
  start "" "http://127.0.0.1:5173/"
  exit /b 0
)

echo Dang mo app tai http://127.0.0.1:5173/
start "" "http://127.0.0.1:5173/"
echo.
echo Neu trinh duyet mo qua som, doi vai giay roi refresh.
echo De tat app, dong cua so nay hoac bam Ctrl+C.
echo.

call npm.cmd run dev -- --host 127.0.0.1 --port 5173

echo.
echo App da dung.
pause
