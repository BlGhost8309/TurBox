@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - быстрый smoke test

set "SMOKE_DIR=smoke_output"
set "SMOKE_FILE=%SMOKE_DIR%\collection_urls_smoke.txt"
if not exist "%SMOKE_DIR%" mkdir "%SMOKE_DIR%"
if exist "%SMOKE_FILE%" del /q "%SMOKE_FILE%"

echo ============================================================
echo   TurBox SMOKE: только ПЕРВЫЙ запрос из основного конфига

echo   Результат: %SMOKE_FILE%
echo ============================================================
echo.
python collection_url_generator.py --limit 1 --output "%SMOKE_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
    echo Smoke generator завершён. Проверь %SMOKE_FILE%
    echo Для проверки Travelpayouts запусти:
    echo python collection_link_converter.py --input "%SMOKE_FILE%"
) else (
    echo Smoke generator завершился с ошибкой %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
