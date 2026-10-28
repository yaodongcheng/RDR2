@echo off
chcp 936 >nul
setlocal EnableExtensions
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
set "ROOT=%~dp0"
set "BLEND=%ROOT%deliverable\blender\willard\willard_full.blend"

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

echo 打开 夏洛蒂的家（完整版：外观 + 室内 415 件）
echo.
echo   [看室内] 左侧大纲视图里，取消勾选这些集合/对象即可
echo        - e_246ed9d0            （房子外壳）
echo        - i_*shell_main         （室内墙壳，最大那个）
echo   或者：把 Camera 的 Clip Start 调大（如 9.6），墙会被裁掉
echo.
echo   [看全屋] 按 小键盘 0 切相机视角；按住 Alt+B 可框选裁剪
start "" "%BLENDER%" "%BLEND%"
