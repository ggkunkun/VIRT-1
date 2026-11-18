@echo off
chcp 936 >nul
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if not "%~1"=="" goto :run_args
if not "%DAMODEL_HOST%"=="" goto :run_args
if not "%CLOUD_SSH_HOST%"=="" goto :run_args
if exist "cloud_train_pack\.cloud_creds.json" goto :run_args

echo [START_CLOUD_TRAIN_NOW] No host specified; running preflight & pre-pack (--prepare-only)...
"%PY%" "cloud_train_pack\start_train_now.py" --prepare-only --tracks vericut96-v2,vericut-e,six-software,master-8b
if errorlevel 1 exit /b %ERRORLEVEL%
echo.
echo [Usage] Once the cloud GPU instance comes online, run:
echo   START_CLOUD_TRAIN_NOW.cmd --track vericut-e --host ^<HOST^> --port ^<PORT^> --password ^<PASS^> --follow --auto-deploy
echo   START_CLOUD_TRAIN_NOW.cmd --track master-8b --host ^<HOST^> --port ^<PORT^> --password ^<PASS^> --follow --auto-deploy
echo Or export DAMODEL_HOST / DAMODEL_PORT / DAMODEL_PASS and run:
echo   START_CLOUD_TRAIN_NOW.cmd --track vericut-e --follow --auto-deploy
exit /b 0

:run_args
"%PY%" "cloud_train_pack\start_train_now.py" %*
exit /b %ERRORLEVEL%
