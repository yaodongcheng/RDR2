@echo off
chcp 65001 >nul
set "BL=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
set "SCRIPT=%~dp0open_bind_inspect.py"
set "LOG=%~dp0..\work\npc\blender_run.log"

if not exist "%BL%" (
  echo [错误] 找不到 Blender: %BL%
  pause & exit /b 1
)

echo 正在启动 Blender（本次载入主角 + 骨骼）...
echo 日志: %LOG%
echo.
"%BL%" --factory-startup --python "%SCRIPT%" > "%LOG%" 2>&1

echo.
echo Blender 已退出。日志末尾：
powershell -NoProfile -Command "Get-Content -Tail 12 '%LOG%'"
pause
