@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - hotel mode

echo ============================================================
echo   TurBox: один отель из разных городов вылета
echo   Конфиги:
echo     configs\hotel_urls.txt
echo     configs\departure_cities.txt
echo   Результат: postsCollections\hotel_cities_*.txt
echo ============================================================
echo.

python collection_url_generator.py --hotel-mode
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo   ОШИБКА: Python завершился с кодом %EXIT_CODE%
    echo   Проверь сообщения выше и папку debug_logs.
    echo ============================================================
) else (
    echo ============================================================
    echo   Скрипт завершён. Проверь postsCollections\hotel_cities_*.txt
    echo ============================================================
)
pause >nul
exit /b %EXIT_CODE%
