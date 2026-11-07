@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================================
echo   Virtu模型 云端 Bug 修复回传一键应用脚本
echo ========================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" apply_virtu_bugfixes.py
) else (
    python apply_virtu_bugfixes.py
)
echo.
echo [完成] 如需停止并清理 Google Drive 对 .venv 的缓慢同步，可执行:
echo   attrib +h +s .venv
pause
