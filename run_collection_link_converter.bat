@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - affiliate link converter

echo ============================================================
echo   TurBox - convert collections to affiliate links
echo   Input: configs\collection_urls.txt
echo   Output: postsCollections\collection_*.txt
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_link_converter.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Link converter failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
) else (
    echo [OK] Link converter finished.
    echo Check: postsCollections\collection_*.txt
)
echo.
pause
exit /b %EXIT_CODE%
