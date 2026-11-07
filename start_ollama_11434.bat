@echo off
REM Virtu PRIMARY Ollama serve on 11434 - explicit env (app.exe auto-start loses OLLAMA_MODELS)
set OLLAMA_MODELS=E:\ollama\models
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1
set OLLAMA_MAX_LOADED_MODELS=1
set OLLAMA_CONTEXT_LENGTH=8192
set NO_PROXY=*
set no_proxy=*
"E:\OllamaApp\ollama.exe" serve > "%~dp0runs\ollama_11434.log" 2>&1
