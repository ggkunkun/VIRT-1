# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"

probe_code = """
import torch
from transformers import AutoTokenizer, AutoConfig
model_path = '/model/ModelScope/Qwen/Qwen3-14B'
print('Checking model config...')
cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
print(f'Model type: {cfg.model_type} | Vocab size: {cfg.vocab_size} | Hidden: {cfg.hidden_size}')
print('Checking tokenizer...')
tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
print(f'Tokenizer loaded: {len(tok)} tokens | Pad: {tok.pad_token}')
"""

cmd = f"{py_bin} -c \"{probe_code}\""
stdin, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)

client.close()
