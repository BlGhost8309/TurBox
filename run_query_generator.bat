@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - query generator

echo ============================================================
echo   TurBox - build search requests
echo   Config: configs\query_generator_config.json
echo   Output: configs\url_generation_config.txt
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo.
    pause
    exit /b 9009
)

python query_generator.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Query generator failed. Exit code: %EXIT_CODE%
) else (
    echo [OK] Search requests were generated.
    echo Next: run_collection_url_generator.bat
)
echo.
pause
exit /b %EXIT_CODE%
