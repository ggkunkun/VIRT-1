import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

# 1) 升级 accelerate 到最新（带 parallelism_config），并清理旧训练残留
upgrade = (
    "/opt/conda/bin/python3.11 -m pip install -U accelerate 2>&1 | tail -4; "
    "echo '--- verify ---'; "
    "/opt/conda/bin/python3.11 -c \"from accelerate import Accelerator, __version__ as v; print('accelerate', v, 'has_parallelism_config', hasattr(Accelerator,'parallelism_config'))\"; "
)
out, err, rc = S.run(upgrade, timeout=400)
print(out)
if err.strip(): print("STDERR:", err[:800])

# 确认属性存在再开训
if "has_parallelism_config True" in out:
    # 2) 后台开训（基座/数据已就位，fp16，跳过重装与重下）
    train_cmd = (
        "/opt/conda/bin/python3.11 scripts/train_qwen3_8b_qlora.py "
        "--base ./models/Qwen3-8B --data data/sft/virtu_capability_sft_v6.jsonl "
        "--out checkpoints/cad_cam_boundary_lora --lora_r 32 --lora_alpha 64 "
        "--lr 2e-4 --epochs 3 --bs 4 --accum 4 --seed 20261031"
    )
    pid = S.run_bg(train_cmd, "/root/virtu_train", "/root/virtu_train/train.log")
    print("TRAIN bg launched:", pid)
else:
    print("!! accelerate 属性仍缺失，未开训，需换 transformers 版本")
