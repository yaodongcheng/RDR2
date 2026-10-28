@echo off
chcp 936 >nul
setlocal EnableExtensions
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
set "ROOT=%~dp0"
set "BLENDDIR=%ROOT%deliverable\blender\continent"

rem 自动挑最新修改的一版 continent_v*.blend（以后有 v7 也不用改这个文件）
set "BLEND="
for /f "delims=" %%F in ('dir /b /o-d "%BLENDDIR%\continent_v*.blend" 2^>nul') do if not defined BLEND set "BLEND=%BLENDDIR%\%%F"
if not defined BLEND set "BLEND=%BLENDDIR%\continent_v5.blend"

if not exist "%BLENDER%" (
  echo [ERROR] 找不到 Blender: %BLENDER%
  pause
  exit /b 1
)
if not exist "%BLEND%" (
  echo [ERROR] 找不到文件: %BLEND%
  pause
  exit /b 1
)

echo 正在打开：%BLEND%
echo   1. 先等它加载完（约 1~3 分钟）
echo   2. 加载完自动执行 tools\blender_autoload.py（Solid 着色 / 地形减面 / 分区 / RDR2 面板）
echo   3. N 面板「RDR2」页：12 类开关、水面、水位、植被（9,676，隐藏不删）
echo   提示：地形 patch 与植被默认隐藏，要看就单独勾上；别一上来全开再切材质预览
echo.

start "" "%BLENDER%" "%BLEND%" --python "%ROOT%tools\blender_autoload.py"