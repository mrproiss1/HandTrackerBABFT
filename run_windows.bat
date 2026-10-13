@echo off
setlocal
cd /d "%~dp0"

:: Prefer 64-bit Python launcher
py -3-64 Handspython.py 2>nul
if %ERRORLEVEL% equ 0 exit /b

:: Try generic py -3 launcher
py -3 Handspython.py 2>nul
if %ERRORLEVEL% equ 0 exit /b

:: Try system python on PATH
python Handspython.py
if %ERRORLEVEL% equ 0 exit /b

:: If Python failed and standalone exe exists, offer to run it
if exist "release\HandTracker.exe" (
    echo.
    echo Launching standalone HandTracker.exe from release folder...
    start "" "release\HandTracker.exe"
    exit /b
)
if exist "dist\HandTracker.exe" (
    echo.
    echo Launching standalone HandTracker.exe from dist folder...
    start "" "dist\HandTracker.exe"
    exit /b
)
if exist "HandTracker.exe" (
    echo.
    echo Launching standalone HandTracker.exe...
    start "" "HandTracker.exe"
    exit /b
)

echo.
echo Launch failed. Please install 64-bit Python with pip or download HandTracker.exe from Releases.
pause

