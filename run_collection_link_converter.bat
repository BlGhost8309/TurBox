@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TurBox - конвертер партнёрских ссылок

echo ============================================================
echo   TurBox: конвертация подборок в партнёрские ссылки
echo   Вход: configs\collection_urls.txt
echo   Результат: postsCollections\collection_*.txt
echo ============================================================
echo.

python collection_link_converter.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo ============================================================
    echo   ОШИБКА: Python завершился с кодом %EXIT_CODE%
    echo   Проверь сообщения выше и папку debug_logs.
    echo ============================================================
) else (
    echo ============================================================
    echo   Скрипт завершён. Проверь postsCollections\collection_*.txt
    echo ============================================================
)
pause >nul
exit /b %EXIT_CODE%
