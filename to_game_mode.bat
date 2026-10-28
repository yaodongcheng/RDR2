@echo off
REM RDR2 module: editor mode -> game mode
REM Must be run BEFORE launching the game (game reads AssetPackages, not Assets).
REM Pure ASCII only. Do not use bare ">" in echo lines (escape as ^>).
set "MOD=%~dp0"
cd /d "%MOD%"

echo [1/2] AssetSources
if exist "%MOD%AssetSources" (
  if exist "%MOD%AssetSources_disabled" (
    echo   [warn] both AssetSources and AssetSources_disabled exist - skipping
  ) else (
    ren "%MOD%AssetSources" "AssetSources_disabled"
    echo   AssetSources -^> AssetSources_disabled
  )
) else (
  echo   AssetSources not found - nothing to do
)

echo [2/2] Assets
if exist "%MOD%Assets" (
  if exist "%MOD%Assets_disabled" (
    echo   [warn] both Assets and Assets_disabled exist - skipping
  ) else (
    ren "%MOD%Assets" "Assets_disabled"
    echo   Assets -^> Assets_disabled
  )
) else (
  echo   Assets not found - nothing to do
)

echo done. Launch the game now.
pause
