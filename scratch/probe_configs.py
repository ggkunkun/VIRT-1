# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko

HOST = 'cpod-1xesnvd6jbqp.podtcp.compshare.cn'
PORT = 24334
USER = 'root'
PASS = _pw(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
py_bin = '/usr/local/miniconda3/envs/py312/bin/python'

code = """
from trl import DPOConfig

try:
    dpo = DPOConfig(
        output_dir='/tmp/test_dpo',
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=5e-6,
        num_train_epochs=1.0,
        max_steps=15,
        beta=0.1,
        max_length=2048,
        logging_steps=5,
        save_strategy='no',
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        report_to='none'
    )
    print('DPOConfig SUCCESS!')
except Exception as e:
    print('DPOConfig FAILED:', e)
"""

cmd = f"{py_bin} -c \"{code}\""
stdin, stdout, stderr = client.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode().strip())
print("STDERR:\n", stderr.read().decode().strip())
client.close()
