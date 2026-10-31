@echo off
chcp 936 >nul
setlocal EnableExtensions
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

rem ---- 找项目根（deliverable 在 D 盘，不在仓库里）----
set "PROJ="
for %%R in ("%~dp0." "%~dp0.." "%~dp0..\..") do (
  if not defined PROJ if exist "%%~fR\deliverable\blender\continent" set "PROJ=%%~fR"
)
if not defined PROJ if exist "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent" set "PROJ=D:\BrainMaker\大镖客2解包分析"
if not defined PROJ (
  echo [ERROR] 找不到项目根（需要含 deliverable\blender\continent 的目录）
  pause
  exit /b 1
)

set "BLENDDIR=%PROJ%\deliverable\blender\continent"
for %%P in ("%PROJ%\..") do set "AUDDIR=%%~fP\_test\audit"
for %%P in ("%PROJ%\..") do set "LOGDIR=%%~fP\_logs"
set "LOG=%LOGDIR%\launcher.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
>>"%LOG%" echo [%date% %time%] ---- launcher start ----
>>"%LOG%" echo [%date% %time%] script="%~f0"
>>"%LOG%" echo [%date% %time%] arg=%~1
set "ARG=%~1"
if "%ARG%"=="" (
  echo.
  echo   输入编号打开审计分块（例如 19），直接回车打开最新大陆。
  echo   输入 list 列出所有；也可以直接输入 blend 路径。
  set /p ARG=请输入:
)
>>"%LOG%" echo [%date% %time%] prompted=%ARG%
set "BLEND="

if /i "%ARG%"=="list" (
  echo [大陆版本]
  dir /b /o-d "%BLENDDIR%\continent_v*.blend" 2>nul
  echo.
  echo [审计分块]
  dir /b /o-d "%AUDDIR%\audit_*.blend" 2>nul
  echo.
  pause
  exit /b 0
)

if not "%ARG%"=="" (
  echo %ARG%| findstr /r "^[0-9][0-9]*$" >nul
  if not errorlevel 1 (
    for /f "delims=" %%F in ('dir /b /o-d "%AUDDIR%\audit_%ARG%_*.blend" 2^>nul') do if not defined BLEND set "BLEND=%AUDDIR%\%%F"
    if not defined BLEND (
      echo.
      echo [ERROR] 没找到审计块 #%ARG%
      echo         目录：%AUDDIR%
      echo         可用分块：
      dir /b /o-d "%AUDDIR%\audit_*.blend" 2>nul
      echo.
      pause
      exit /b 1
    )
  ) else (
    if exist "%ARG%" set "BLEND=%ARG%"
    if not defined BLEND if exist "%PROJ%\%ARG%" set "BLEND=%PROJ%\%ARG%"
    if not defined BLEND (
      echo.
      echo [ERROR] 找不到 blend：%ARG%
      echo.
      pause
      exit /b 1
    )
  )
) else (
  for /f "delims=" %%F in ('dir /b /o-d "%BLENDDIR%\continent_v*.blend" 2^>nul') do if not defined BLEND set "BLEND=%BLENDDIR%\%%F"
)

if not exist "%BLENDER%" (
  echo [ERROR] 找不到 Blender: "%BLENDER%"
  pause
  exit /b 1
)
if not defined BLEND (
  echo [ERROR] 没找到 blend 文件
  pause
  exit /b 1
)
if not exist "%BLEND%" (
  echo [ERROR] 找不到 blend: "%BLEND%"
  pause
  exit /b 1
)

echo 正在打开：%BLEND%
echo   用法：打开大陆_流畅.bat            ^(默认最新大陆^)
echo         打开大陆_流畅.bat 19         ^(审计分块 #19^)
echo         打开大陆_流畅.bat list       ^(列出所有大陆/分块^)
echo         打开大陆_流畅.bat ^<路径.blend^>
echo.
>>"%LOG%" echo [%date% %time%] open "%BLEND%"
>>"%LOG%" echo [%date% %time%] cmd "%BLENDER%" "%BLEND%" --python "%PROJ%\tools\blender_autoload.py"
start "" "%BLENDER%" "%BLEND%" --python "%PROJ%\tools\blender_autoload.py"
echo.
echo 已发出 Blender 启动命令。如果几秒后没有 Blender 窗口，请把上面的路径和报错发我。
echo 日志：%LOG%
echo 按任意键关闭本窗口...
pause
