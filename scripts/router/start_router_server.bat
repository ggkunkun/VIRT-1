@echo off
REM Virtu P1-3 router HTTP service - persistent launcher (CRLF)
cd /d "%~dp0"
set ROUTER_PORT=8800
set ROUTER_HOST=127.0.0.1
set ROUTER_MAX_CONCURRENT=4
set ROUTER_KEEP_ALIVE=10m
REM Optional: set ROUTER_AUTH_TOKEN before launching; otherwise a protected per-user token file is used.
"%~dp0..\..\.venv\Scripts\pythonw.exe" router_server.py >> "%~dp0router_server.log" 2>&1
