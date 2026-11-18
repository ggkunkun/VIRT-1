@echo off
chcp 65001 >nul
cd /d D:\Virtu模型
set "PYTEST_TEMP=D:\Virtu模型\.pytest_temp\run_%RANDOM%%RANDOM%"
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests\test_agent_chain_executor.py tests\test_toolchain_access_modes.py tests\test_agent_adaptive_routing.py tests\test_memory_safe_agent_team.py tests\test_agent_toolchain_full.py -q -p no:cacheprovider -s --timeout=60 -o tmp_path_retention_policy=all --basetemp="%PYTEST_TEMP%" > _tests_result.txt 2>&1
echo EXITCODE=%ERRORLEVEL%
