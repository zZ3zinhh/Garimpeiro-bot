@echo off
rem Runs the bot once and adds the output to bot_log.txt.
rem The Windows Task Scheduler runs this file every 10 minutes.
cd /d "%~dp0\.."
echo. >> bot\bot_log.txt
echo ===== %date% %time% >> bot\bot_log.txt
"C:\Users\joser\AppData\Local\Python\pythoncore-3.14-64\python.exe" bot\main.py >> bot\bot_log.txt 2>&1
