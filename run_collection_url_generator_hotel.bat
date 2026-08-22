@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - hotel mode URL generator

echo ============================================================
echo   TurBox - one hotel from multiple departure cities
echo   Config: configs\hotel_urls.txt
echo   Config: configs\departure_cities.txt
echo   Output: postsCollections\hotel_cities_*.txt
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python collection_url_generator.py --hotel-mode
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Hotel-mode URL generator failed. Exit code: %EXIT_CODE%
    echo Check the console output and debug_logs.
) else (
    echo [OK] Hotel-mode URL generator finished.
    echo Check: postsCollections\hotel_cities_*.txt
)
echo.
pause
exit /b %EXIT_CODE%
