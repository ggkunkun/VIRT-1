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
from transformers import AutoTokenizer, TrainingArguments
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

tok = AutoTokenizer.from_pretrained('/model/ModelScope/Qwen/Qwen3-14B')
ds = Dataset.from_dict({'text': ['hello world', 'how are you']})
try:
    cfg = SFTConfig(output_dir='/tmp/test', max_steps=1, dataset_text_field='text')
    print('SFTConfig OK')
except Exception as e:
    print('SFTConfig error:', e)
"""

cmd = f"{py_bin} -c \"{probe_code}\""
stdin, stdout, stderr = client.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode().strip())
print("STDERR:\n", stderr.read().decode().strip())

client.close()
