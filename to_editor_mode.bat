@echo off
REM RDR2 module: game mode -> editor mode
REM Must be run BEFORE opening ModKit (editor needs Assets/).
REM Pure ASCII only. Do not use bare ">" in echo lines (escape as ^>).
set "MOD=%~dp0"
cd /d "%MOD%"

echo [1/2] AssetSources
if exist "%MOD%AssetSources_disabled" (
  if exist "%MOD%AssetSources" (
    echo   [warn] both AssetSources and AssetSources_disabled exist - skipping
  ) else (
    ren "%MOD%AssetSources_disabled" "AssetSources"
    echo   AssetSources_disabled -^> AssetSources
  )
) else (
  echo   AssetSources_disabled not found - nothing to do
)

echo [2/2] Assets
if exist "%MOD%Assets_disabled" (
  if exist "%MOD%Assets" (
    echo   [warn] both Assets and Assets_disabled exist - skipping
  ) else (
    ren "%MOD%Assets_disabled" "Assets"
    echo   Assets_disabled -^> Assets
  )
) else (
  echo   Assets_disabled not found - nothing to do
)

echo done. Open ModKit now.
pause
