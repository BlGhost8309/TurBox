@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - Travelpayouts smoke test

set "SMOKE_FILE=smoke_output\collection_urls_smoke.txt"

echo ============================================================
echo   TurBox SMOKE - Travelpayouts for one result
echo   Input: %SMOKE_FILE%
echo ============================================================
echo.

if not exist "%SMOKE_FILE%" (
    echo [ERROR] File not found: %SMOKE_FILE%
    echo Run run_smoke_collection.bat first.
    echo.
    pause
    exit /b 2
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_link_converter.py --input "%SMOKE_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Travelpayouts smoke test finished.
    echo Check the newest postsCollections\collection_*.txt
) else (
    echo [FAILED] Travelpayouts smoke test failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
)
echo.
pause
exit /b %EXIT_CODE%
