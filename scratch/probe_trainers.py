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

test_script = """
import torch
import torch.nn as nn
from transformers import AutoTokenizer, PretrainedConfig
from peft import LoraConfig, get_peft_model
from trl import DPOTrainer, DPOConfig
from datasets import Dataset

tok = AutoTokenizer.from_pretrained('/model/ModelScope/Qwen/Qwen3-14B')

class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = PretrainedConfig()
        self.config.is_encoder_decoder = False
        self.config.pad_token_id = 0
        self.input_modalities = ['text']
        self.linear = nn.Linear(32, 32)
    def forward(self, input_ids=None, attention_mask=None, **kwargs):
        bsz, seq_len = input_ids.shape
        logits = torch.randn(bsz, seq_len, 32)
        class Output: pass
        out = Output()
        out.logits = logits
        return out

model = TinyModel()
lora_cfg = LoraConfig(target_modules=['linear'])
peft_model = get_peft_model(model, lora_cfg)

dpo_cfg = DPOConfig(output_dir='/tmp/t_dpo', max_steps=1, max_length=64)
ds = Dataset.from_dict({
    'prompt': ['p1'],
    'chosen': ['c1'],
    'rejected': ['r1']
})

try:
    trainer = DPOTrainer(
        model=peft_model,
        ref_model=None,
        train_dataset=ds,
        processing_class=tok,
        args=dpo_cfg
    )
    print('DPOTrainer with processing_class: SUCCESS!')
except Exception as e:
    import traceback
    traceback.print_exc()
"""

sftp = client.open_sftp()
with sftp.file('/tmp/test_dpo_peft.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = client.exec_command(f"{py_bin} /tmp/test_dpo_peft.py")
print("STDOUT:\n", stdout.read().decode().strip())
print("STDERR:\n", stderr.read().decode().strip())
client.close()
