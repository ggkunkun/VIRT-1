@echo off
cd /d D:\Virtu模型
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -u scripts\impeller_design_workbench.py --mode auto --rounds 3 --out projects\impeller_workbench_v1\runs_full > temp\wb3.log 2>&1
echo EXITCODE=%ERRORLEVEL% >> temp\wb3.log
