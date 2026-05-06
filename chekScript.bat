@echo off
chcp 65001 >nul
cd /d "%~dp0"
python top_hotels_parser.py --input "results/result_Санкт-Петербург-Египет.json"
pause
