@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - hotel mode affiliate converter

echo ============================================================
echo   TurBox - convert hotel-mode links to affiliate links
echo   Input: newest postsCollections\hotel_cities_*.txt
echo   Output: postsCollections\hotel_cities_PARTNERS_*.txt
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_link_converter.py --hotel-mode
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Hotel-mode link converter failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
) else (
    echo [OK] Hotel-mode link converter finished.
    echo Check: postsCollections\hotel_cities_PARTNERS_*.txt
)
echo.
pause
exit /b %EXIT_CODE%
