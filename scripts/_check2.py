import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
cmd = (
    "echo '=== versions ==='; "
    "/opt/conda/bin/python3.11 -c \"import torch,transformers,tokenizers; print('torch',torch.__version__); print('transformers',transformers.__version__); print('tokenizers',tokenizers.__version__); print('cuda',torch.cuda.is_available()); print('gpu',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NA'); print('bf16_ok',torch.cuda.is_bf16_supported() if torch.cuda.is_available() else 'NA')\" 2>&1; "
    "echo '=== base model ==='; du -sh /root/virtu_train/models/Qwen3-8B 2>/dev/null; ls /root/virtu_train/models/Qwen3-8B 2>/dev/null | head; "
    "echo '=== peft/bnb ==='; /opt/conda/bin/python3.11 -c \"import peft,bitsandbytes,accelerate; print('peft',peft.__version__,'bnb',bitsandbytes.__version__,'acc',accelerate.__version__)\" 2>&1; "
    "echo '=== data ==='; ls -la /root/virtu_train/data/sft/ 2>/dev/null"
)
out, err, rc = S.run(cmd, timeout=90)
print(out)
if err.strip(): print("STDERR:", err[:2000])
