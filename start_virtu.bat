@echo off
chcp 65001 >nul
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
:menu
cls
echo ==============================================
echo        Virtu-CAD-CAM 启动菜单
echo ==============================================
echo  [1] cloud        (云端真实模型, 零本地算力, 立即可用) - 推荐
echo  [2] llama.cpp    (GGUF, 无显卡也能跑)
echo  [3] transformers (GPU + 你的对话/CAD LoRA)
echo  [4] vLLM HTTP    (指向已运行的 vLLM 服务)
echo  [5] 仅诊断       (--check, 不启动)
echo  [Q] 退出
echo ==============================================
set /p choice=请选择 [1-5/Q]:
if "%choice%"=="1" goto cloud
if "%choice%"=="2" goto llamacpp
if "%choice%"=="3" goto transformers
if "%choice%"=="4" goto vllm
if "%choice%"=="5" goto check
if /i "%choice%"=="q" goto end
goto menu

:cloud
set VIRTU_BACKEND=cloud
"%PY%" "%~dp0start_virtu_bridge.py"
goto end

:llamacpp
set VIRTU_BACKEND=llamacpp
set /p gp=GGUF 路径(可留空用 models/ 下默认文件):
if not "%gp%"=="" set VIRTU_GGUF_PATH=%gp%
"%PY%" "%~dp0start_virtu_bridge.py"
goto end

:transformers
set VIRTU_BACKEND=transformers
set /p mp=Qwen3-8B 基座路径:
if not "%mp%"=="" set VIRTU_MODEL_PATH=%mp%
"%PY%" "%~dp0start_virtu_bridge.py"
goto end

:vllm
set VIRTU_BACKEND=vllm_http
set /p vu=vLLM 端点(如 http://127.0.0.1:8001/v1):
if not "%vu%"=="" set VIRTU_VLLM_URL=%vu%
"%PY%" "%~dp0start_virtu_bridge.py"
goto end

:check
"%PY%" "%~dp0start_virtu_bridge.py" --check
goto end

:end
pause
