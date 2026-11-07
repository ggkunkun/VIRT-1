@echo off
REM ============================================================
REM  Virtu local inference optimizer (RTX 4050 6GB / 16GB RAM)
REM  KV cache quant (q8_0) + flash attention + auto GPU offload
REM  Double-click to start Ollama with GPU-optimized settings.
REM  To restore defaults, launch Ollama normally from Start menu.
REM  NOTE: on 6GB VRAM the 8B model tops out ~77% GPU / ~17 tok/s;
REM        use qwen2.5:3b (or virtu-fast via virtu_router.py) for
REM        100% GPU / ~78 tok/s smooth daily chat.
REM ============================================================
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_NUM_THREADS=10
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_CONTEXT_LENGTH=8192

echo [Virtu] Stopping existing Ollama...
taskkill /IM "ollama.exe" /F
taskkill /IM "ollama app.exe" /F
timeout /t 2

echo [Virtu] Starting Ollama 0.40.14 with GPU-optimized settings on port 11434...
start "" "E:\OllamaApp\ollama.exe" serve
echo [Virtu] Done. Run "ollama ps" to confirm PROCESSOR column (8B ~77%% GPU is the ceiling on 6GB).
