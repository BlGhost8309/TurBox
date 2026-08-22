@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - OnlineTours smoke test

set "SMOKE_DIR=smoke_output"
set "SMOKE_FILE=%SMOKE_DIR%\collection_urls_smoke.txt"

if not exist "%SMOKE_DIR%" mkdir "%SMOKE_DIR%"
if exist "%SMOKE_FILE%" del /q "%SMOKE_FILE%"

echo ============================================================
echo   TurBox SMOKE - first query only
echo   Output: %SMOKE_FILE%
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_url_generator.py --limit 1 --output "%SMOKE_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] OnlineTours smoke test finished.
    echo Check: %SMOKE_FILE%
    echo Next: run_smoke_link_converter.bat
) else (
    echo [FAILED] OnlineTours smoke test failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
)
echo.
pause
exit /b %EXIT_CODE%
