@echo off
set VIRTU_BACKEND=vllm_http
set VIRTU_VLLM_URL=http://127.0.0.1:11434/v1
set VIRTU_VLLM_MODEL=virtu-ties-v1
set VIRTU_TEMPERATURE=0.3
set VIRTU_MAX_TOKENS=1024
cd /d D:\Virtu模型
D:\Virtu模型\.venv\Scripts\python.exe scripts\workbuddy_virtu_bridge.py
