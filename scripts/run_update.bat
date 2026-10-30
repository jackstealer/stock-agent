@echo off
cd /d C:\Users\ATUL\Desktop\stock-agent
echo ===== %date% %time% chain start ===== >> logs\chain.log
.venv\Scripts\python.exe -m src.news.collect >> logs\news.log 2>&1
echo %date% %time% news exit %errorlevel% >> logs\chain.log
.venv\Scripts\python.exe -m src.data.update >> logs\update.log 2>&1
set UPD=%errorlevel%
echo %date% %time% update exit %UPD% >> logs\chain.log
if not "%UPD%"=="0" exit /b 1
.venv\Scripts\python.exe -m src.paper.run_daily >> logs\paper.log 2>&1
echo %date% %time% paper exit %errorlevel% >> logs\chain.log
