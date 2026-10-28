@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "DOC=%~dp0export"

rem ============================================================
rem  RDR2 unpacking viewer - single launcher
rem  Starts a local static server for the "export" folder,
rem  then opens the home page: http://127.0.0.1:PORT/
rem  Keep the server window open; closing it stops the server.
rem  ASCII only on purpose: avoids code-page / encoding issues.
rem ============================================================

if not exist "%DOC%\index.html" (
  echo [ERROR] Cannot find "%DOC%\index.html".
  echo         Run this bat from the project root folder.
  pause
  exit /b 1
)

rem ---- pick a python interpreter (py launcher > python > uv) ----
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  if exist "%USERPROFILE%\.local\bin\uv.exe" set "PY=%USERPROFILE%\.local\bin\uv.exe run python"
)
if not defined PY (
  if exist "%APPDATA%\com.brainmaker.client\cowork-updates\uv-binary\uv.exe" set "PY=%APPDATA%\com.brainmaker.client\cowork-updates\uv-binary\uv.exe run python"
)
if not defined PY (
  echo [ERROR] No Python found. Install Python 3 and tick "Add to PATH".
  pause
  exit /b 1
)

rem ---- pick a free port (8788 first) ----
set "PORT="
for %%P in (8788 8789 8790 8791 8792) do (
  if not defined PORT (
    netstat -ano | findstr ":%%P " | findstr LISTENING >nul
    if errorlevel 1 set "PORT=%%P"
  )
)
if not defined PORT (
  echo [ERROR] Ports 8788-8792 are all busy. Close other servers and retry.
  pause
  exit /b 1
)

set "URL=http://127.0.0.1:%PORT%/"
echo ============================================================
echo   RDR2 unpacking viewer
echo ------------------------------------------------------------
echo   URL   : %URL%
echo   Root  : %DOC%
echo   Python: %PY%
echo ------------------------------------------------------------
echo   A server window will open. Close it to stop the server.
echo ============================================================
echo.

start "RDR2 viewer server on %PORT% (close this window to stop)" /D "%DOC%" cmd /c "%PY% -m http.server %PORT% --bind 127.0.0.1"

rem ---- wait until the server actually answers (max ~15s) ----
set /a TRIES=0
:wait
set /a TRIES+=1
%PY% -c "import socket,sys;s=socket.socket();s.settimeout(0.5);sys.exit(0 if s.connect_ex(('127.0.0.1',%PORT%))==0 else 1)" >nul 2>nul
if not errorlevel 1 goto ready
if %TRIES% GEQ 15 goto timeout
ping -n 2 127.0.0.1 >nul
goto wait

:timeout
echo [WARN] Server did not answer in 15s. Opening the page anyway.
:ready
start "" "%URL%"
echo Opened: %URL%
exit /b 0
