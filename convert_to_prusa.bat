@echo off
rem Convert a Bambu Studio / OrcaSlicer .3mf to a PrusaSlicer .3mf.
rem Drag one or more .3mf files onto this file. Each becomes <name>_prusa.3mf
rem in the same folder as the source.

setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Usage: drag one or more .3mf files onto this batch file.
    echo.
    pause
    exit /b 1
)

for %%f in (%*) do call :convert "%%~ff"

echo.
pause
exit /b 0

:convert
set "src=%~1"
if /i not "%~x1"==".3mf" (
    echo Skipping - not a .3mf: %src%
    exit /b 0
)
set "out=%~dp1%~n1_prusa.3mf"
echo.
echo Converting: %src%
rem <nul keeps stdin non-interactive so the extruder-map prompt is skipped.
rem --map keeps Bambu slot N on tool N (no compaction), covering all five tools.
python -m panda2prusa "%src%" "%out%" --map 1=1,2=2,3=3,4=4,5=5 <nul
if errorlevel 1 (
    echo FAILED: %src%
    exit /b 1
)
exit /b 0
