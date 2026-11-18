@echo off
REM ============================================================
REM  Virtu local inference optimizer (RTX 4050 6GB / 16GB RAM)
REM  KV cache quant (q4_0) + flash attention + single model lock
REM  Double-click to start Ollama with GPU-optimized settings.
REM  Agent mode pins 8B Q4_0 + num_ctx=8192 (~100% GPU / ~36-38 tok/s).
REM  Avoid 14B MoE for Agent loops (RAM spill/thrashing on 16GB host).
REM ============================================================
set "OLLAMA_MODELS=E:\migrated\D-MigratedFromC\ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_KV_CACHE_TYPE=q4_0"
set "OLLAMA_FLASH_ATTENTION=1"
set "OLLAMA_NUM_THREADS=10"
set "OLLAMA_NUM_PARALLEL=1"
set "OLLAMA_MAX_LOADED_MODELS=1"
set "OLLAMA_CONTEXT_LENGTH=8192"
set "OLLAMA_KEEP_ALIVE=2m"
set "NO_PROXY=*"
set "no_proxy=*"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="

echo [Virtu] Stopping existing Ollama...
taskkill /IM "ollama.exe" /F >nul 2>&1
taskkill /IM "ollama app.exe" /F >nul 2>&1
timeout /t 2

set "OLLAMA_BIN=C:\Users\Administrator\AppData\Local\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA_BIN%" set "OLLAMA_BIN=E:\OllamaApp\ollama.exe"
echo [Virtu] Starting Ollama with GPU-optimized settings on 127.0.0.1:11434...
start "" "%OLLAMA_BIN%" serve
echo [Virtu] Done. Run "ollama ps" to confirm 100%% GPU offload.
