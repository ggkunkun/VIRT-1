@echo off
cd /d "%~dp0.."
start "" /b "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0..\scripts\guard_resume_full20.py" >> "%~dp0..\runs\local_training_20261115\guard_boot.log" 2>&1
