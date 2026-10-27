@echo off
cd /d C:\Users\ATUL\Desktop\stock-agent
.venv\Scripts\python.exe -m src.data.update >> logs\update.log 2>&1
