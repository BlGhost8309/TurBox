@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - генератор URL подборок

echo ============================================================
echo   TurBox: поиск выгодных подборок
echo   Конфиг: configs\url_generation_config.txt
echo   Результат: configs\collection_urls.txt
echo ============================================================
echo.

python collection_url_generator.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo   ОШИБКА: Python завершился с кодом %EXIT_CODE%
    echo   Проверь сообщения выше и папку debug_logs.
    echo ============================================================
) else (
    echo ============================================================
    echo   Скрипт завершён. Проверь configs\collection_urls.txt
    echo ============================================================
)
pause >nul
exit /b %EXIT_CODE%
