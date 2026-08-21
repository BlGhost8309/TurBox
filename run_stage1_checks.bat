@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - Stage 1 checks

echo ============================================================
echo   TurBox Stage 1 - локальные тесты БЕЗ браузера

echo ============================================================
echo.
python scripts\validate_stage1.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo ПРОВЕРКА НЕ ПРОЙДЕНА. Код: %EXIT_CODE%
) else (
    echo ВСЕ ЛОКАЛЬНЫЕ ПРОВЕРКИ ПРОЙДЕНЫ.
)
pause
exit /b %EXIT_CODE%
