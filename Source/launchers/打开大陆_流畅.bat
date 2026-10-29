@echo off
chcp 936 >nul
setlocal EnableExtensions
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

rem ---- 找项目根（deliverable 在 D 盘，不在仓库里）----
rem 实测（2026-10-28，跨盘 D:→H: 复验）：双击任何同名符号链接时，%~dp0 报的仍是
rem   【链接所在目录】—— 从 D 盘根跑就是 D:\BrainMaker\大镖客2解包分析\，
rem   不是 H:\...\Source\launchers\。逐级向上试，是为了兼容【直接在仓库里跑】的情形。
set "PROJ="
for %%R in ("%~dp0." "%~dp0.." "%~dp0..\..") do (
  if not defined PROJ if exist "%%~fR\deliverable\blender\continent" set "PROJ=%%~fR"
)
if not defined PROJ if exist "D:\BrainMaker\大镖客2解包分析\deliverable\blender\continent" set "PROJ=D:\BrainMaker\大镖客2解包分析"
if not defined PROJ (
  echo [ERROR] 找不到项目根（需要有 deliverable\blender\continent 的目录）。
  echo         试过: "%~dp0." 及其上两级、"D:\BrainMaker\大镖客2解包分析"
  pause
  exit /b 1
)

set "BLENDDIR=%PROJ%\deliverable\blender\continent"

rem 自动挑最新修改的一版 continent_v*.blend（以后有 v11 也不用改这个文件）
set "BLEND="
for /f "delims=" %%F in ('dir /b /o-d "%BLENDDIR%\continent_v*.blend" 2^>nul') do if not defined BLEND set "BLEND=%BLENDDIR%\%%F"
if not defined BLEND set "BLEND=%BLENDDIR%\continent_v10.blend"

if not exist "%BLENDER%" (
  echo [ERROR] 找不到 Blender: "%BLENDER%"
  pause
  exit /b 1
)
if not exist "%BLEND%" (
  echo [ERROR] 找不到 blend 文件: "%BLEND%"
  echo         目录 "%BLENDDIR%" 里有:
  dir /b "%BLENDDIR%\*.blend" 2>nul
  pause
  exit /b 1
)

echo 正在打开："%BLEND%"
echo   1. 先等它加载完（约 1~3 分钟）
echo   2. 加载完自动执行 tools\blender_autoload.py（Solid 着色 / 地形减面 / 分区 / RDR2 面板）
echo   3. N 面板「RDR2」页：12 类开关、水面、水位、植被（隐藏不删）
echo   提示：地形 patch 与植被默认隐藏，要看就单独勾上；别一上来全开再切材质预览
echo.

start "" "%BLENDER%" "%BLEND%" --python "%PROJ%\tools\blender_autoload.py"

