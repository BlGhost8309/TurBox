@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - smoke Travelpayouts

set "SMOKE_FILE=smoke_output\collection_urls_smoke.txt"

echo ============================================================
echo   TurBox SMOKE: Travelpayouts для одного тестового результата

echo   Вход: %SMOKE_FILE%
echo ============================================================
echo.

if not exist "%SMOKE_FILE%" (
    echo ОШИБКА: %SMOKE_FILE% не найден.
    echo Сначала запусти run_smoke_collection.bat
    echo.
    pause
    exit /b 2
)

python collection_link_converter.py --input "%SMOKE_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Smoke Travelpayouts завершён.
    echo Проверь новый postsCollections\collection_*.txt
) else (
    echo Smoke Travelpayouts завершился с ошибкой %EXIT_CODE%.
    echo Проверь debug_logs.
)
pause
exit /b %EXIT_CODE%
