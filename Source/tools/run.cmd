@echo off
rem ============================================================================
rem  tools\run.cmd -- the reliable way to launch console programs here.
rem
rem  Why: in this sandboxed session, starting a console program directly from
rem  PowerShell (piping or `>`-capturing its stdout) fails with either
rem  "Access is denied" or a popup "Application Error 0xc0000142", and the
rem  child's output is often lost or mojibake'd (GBK vs UTF-8).
rem  Redirection created *inside cmd* works: real file handles, no pipe.
rem
rem  Usage:
rem      tools\run.cmd <log-file> <program> [args...]
rem
rem  Example (PowerShell):
rem      cmd /c 'tools\run.cmd D:\BrainMaker\build.log "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b -P tools\blender_continent.py -- --out x.blend'
rem
rem  Notes:
rem    - forces PYTHONIOENCODING/PYTHONUTF8=utf-8 so logs are readable UTF-8
rem    - forces PYTHONUNBUFFERED=1 so heartbeats/tails are not stuck in a buffer
rem    - writes the real exit code as the last line: [rc] exit=N
rem    - every argument is re-quoted, so paths with spaces are safe
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
set "LOG=%~1"
if "%LOG%"=="" (
  echo usage: run.cmd ^<log-file^> ^<program^> [args...]
  exit /b 2
)
shift
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "PYTHONUTF8=1"
rem 65001 avoids GBK mojibake on the way out
chcp 65001 >nul 2>&1

set "CMD="
:collect
if "%~1"=="" goto exec
set "A=%~1"
set "NOSP=!A: =!"
if "!A!"=="!NOSP!" (set "CMD=!CMD! !A!") else (set "CMD=!CMD! "!A!"")
shift
goto collect

:exec
%CMD% >"%LOG%" 2>&1
set "RC=!ERRORLEVEL!"
echo [rc] exit=!RC!>>"%LOG%"
endlocal & exit /b %RC%
