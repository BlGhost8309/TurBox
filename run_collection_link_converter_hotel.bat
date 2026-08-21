@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - партнёрские ссылки hotel mode

echo ============================================================
echo   TurBox: конвертация hotel-mode ссылок

echo   Вход: последний postsCollections\hotel_cities_*.txt
echo   Результат: postsCollections\hotel_cities_PARTNERS_*.txt
echo ============================================================
echo.

python collection_link_converter.py --hotel-mode
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo   ОШИБКА: Python завершился с кодом %EXIT_CODE%
    echo   Проверь сообщения выше и папку debug_logs.
    echo ============================================================
) else (
    echo ============================================================
    echo   Скрипт завершён. Проверь postsCollections\hotel_cities_PARTNERS_*.txt
    echo ============================================================
)
pause >nul
exit /b %EXIT_CODE%
