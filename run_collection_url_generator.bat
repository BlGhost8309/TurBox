@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - collection URL generator

echo ============================================================
echo   TurBox - search tour collections
echo   Config: configs\url_generation_config.txt
echo   Output: configs\collection_urls.txt
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_url_generator.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] URL generator failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
) else (
    echo [OK] URL generator finished.
    echo Check: configs\collection_urls.txt
)
echo.
pause
exit /b %EXIT_CODE%
