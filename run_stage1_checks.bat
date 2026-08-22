@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
title TurBox - Stage 1 checks

echo ============================================================
echo   TurBox Stage 1 - local checks without browser
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    echo Start the same Python environment that you use for TurBox.
    echo.
    pause
    exit /b 9009
)

python scripts\validate_stage1.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [FAILED] Stage 1 checks failed. Exit code: %EXIT_CODE%
) else (
    echo [OK] All local Stage 1 checks passed.
)
echo.
pause
exit /b %EXIT_CODE%
