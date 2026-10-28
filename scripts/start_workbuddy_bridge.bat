@echo off
chcp 65001 >nul
title Virtu-CAD-CAM-10B WorkBuddy Bridge Server
echo ============================================================
echo   Starting Virtu-CAD-CAM-10B OpenAI API Bridge for WorkBuddy
echo   Endpoint: http://127.0.0.1:8000/v1
echo   Model: virtu-cad-cam-10b
echo ============================================================
cd /d "D:\Virtu模型"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" scripts/workbuddy_virtu_bridge.py
pause
