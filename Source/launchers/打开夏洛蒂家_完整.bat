@echo off
chcp 936 >nul
setlocal EnableExtensions
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

rem ---- 找项目根（deliverable 在 D 盘，不在仓库里）----
set "PROJ="
for %%R in ("%~dp0." "%~dp0.." "%~dp0..\..") do (
  if not defined PROJ if exist "%%~fR\deliverable\blender\willard" set "PROJ=%%~fR"
)
if not defined PROJ if exist "D:\BrainMaker\大镖客2解包分析\deliverable\blender\willard" set "PROJ=D:\BrainMaker\大镖客2解包分析"
if not defined PROJ (
  echo [ERROR] 找不到项目根（需要有 deliverable\blender\willard 的目录）。
  pause
  exit /b 1
)

set "BLEND=%PROJ%\deliverable\blender\willard\willard_full.blend"

if not exist "%BLENDER%" (
  echo [ERROR] 找不到 Blender: "%BLENDER%"
  pause
  exit /b 1
)
if not exist "%BLEND%" (
  echo [ERROR] 找不到 blend 文件: "%BLEND%"
  pause
  exit /b 1
)

echo 打开 夏洛蒂的家（完整版：外观 + 室内 415 件）
echo   文件："%BLEND%"
echo.

start "" "%BLENDER%" "%BLEND%" --python "%PROJ%\tools\blender_autoload.py"

