@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0.."

if "%VIRTU_RSI_BASE_URL%"=="" (
  echo [rsi-cloud] set VIRTU_RSI_BASE_URL first, e.g. https://host:8000/v1
  exit /b 2
)
if "%VIRTU_RSI_MODEL_ID%"=="" (
  echo [rsi-cloud] set VIRTU_RSI_MODEL_ID to the id the endpoint serves
  exit /b 2
)

set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [rsi-cloud] endpoint=%VIRTU_RSI_BASE_URL% model=%VIRTU_RSI_MODEL_ID%
"%PY%" cloud_train_pack\rsi_cloud_entry.py --probe
if errorlevel 1 (
  echo [rsi-cloud] probe failed; refusing to start the loop
  exit /b 1
)
"%PY%" cloud_train_pack\rsi_cloud_entry.py
exit /b %ERRORLEVEL%
