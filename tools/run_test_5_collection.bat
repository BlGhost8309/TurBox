@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  pause
  exit /b 1
)

echo [INFO] Running OnlineTours generator for first 5 config rows...
python collection_url_generator.py --limit 5 --output smoke_output\collection_urls_5.txt
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Generator finished with code %EXIT_CODE%.
  pause
  exit /b %EXIT_CODE%
)

echo.
if exist "smoke_output\collection_urls_5.txt" (
  echo [OK] Done. Output file:
  echo smoke_output\collection_urls_5.txt
) else (
  echo [WARNING] Script finished, but output file was not found.
)

pause
endlocal
