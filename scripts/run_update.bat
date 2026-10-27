@echo off
cd /d C:\Users\ATUL\Desktop\stock-agent
.venv\Scripts\python.exe -m src.data.update >> logs\update.log 2>&1
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m src.paper.run_daily >> logs\paper.log 2>&1
