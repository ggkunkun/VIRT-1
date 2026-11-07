# 云端训练包（cloud_train_package）

针对 **Virtu CAD/CAM 边界强化** 的 QLoRA 微调包。已针对 **V100 / T4（无 bf16）** 自适应退回 fp16，
在 **Ampere+（4090/L40S/A100）** 自动用 bf16。上传到 GPU 实例后，**一条命令即可开训**。

## 目录结构
```
cloud_train_package/
├── scripts/
│   ├── train_qwen3_8b_qlora.py   # 单卡 QLoRA 训练核心（含 --selftest 自检）
│   ├── cloud_launch.sh           # 一键启动器：装依赖→下基座→自检→开训
│   ├── merge_numpy.py            # 本地合并 LoRA→基座（delta 模式）
│   └── convert_lora_to_gguf.py   # 本地把 HF 模型转 GGUF（Ollama 部署用）
├── data/sft/virtu_capability_sft_v6.jsonl   # 强化语料 4233 条
└── CLOUD_FINETUNE_PLAN.md        # 完整计划与部署闭环说明
```

## 一、云端开训（在你租好的 GPU 实例上）
1. 把本包整个上传到实例（AutoDL 可用「文件上传」或 `scp`/`rsync`），
   解压到工作目录，例如 `/root/autodl-tmp/virtu_train/`。
2. 进入目录并开训：
   ```bash
   cd /root/autodl-tmp/virtu_train
   bash scripts/cloud_launch.sh
   ```
   脚本会自动：装依赖 → 下载 Qwen3-8B 基座（modelscope，失败回退 HF 镜像）→
   先 `--selftest` 校验数据与分词 → 正式训练。
3. 进度看 `checkpoints/cad_cam_boundary_lora/training_receipt.json`，
   adapter 落在 `checkpoints/cad_cam_boundary_lora/`（约几十 MB）。
4. 可选环境变量覆盖：`LR=2e-4 EPOCHS=3 BS=4 ACCUM=4 LORA_R=32 LORA_ALPHA=64`
   （V100 32G 可直接用默认；若 OOM 把 `BS=2 ACCUM=8`）。

## 二、拿回 adapter 并本地合并部署（在你本机/部署机）
把云端 `checkpoints/cad_cam_boundary_lora/` 整个目录下载回来，例如放到
`D:/Virtu模型/checkpoints/cad_cam_boundary_lora/`。

1. **合并**（需要 Qwen3-8B 基座 safetensors 在本地，例如 `models/Qwen3-8B`）：
   ```bash
   python scripts/merge_numpy.py --base models/Qwen3-8B --out checkpoints/virtu_merged --mode delta
   ```
2. **转 GGUF**（用 llama.cpp 的 `convert_hf_to_gguf.py`，或本包 `convert_lora_to_gguf.py`
   仅用于把 LoRA 单独转 GGUF；建议先合并再整模转 GGUF 以适配现有 Ollama 桥）。
3. **注册 Ollama 独立名**（保留旧模型不动，灰度切）：新建 Modelfile
   `FROM ./checkpoints/virtu_merged.q8_0.gguf` → `ollama create virtu-cad-cam-10b-sft -f Modelfile`。
4. **切桥**：把 `scripts/workbuddy_virtu_bridge.py` 的 `MODEL_ID` 从 `virtu-cad-cam-10b`
   改为 `virtu-cad-cam-10b-sft`（或经 `start_bridge_service.py` 的环境变量注入），重启桥。
5. **重评测**：
   ```bash
   python virtu_eval/report.py --runs "virtu:_eval_full4" --out benchmarks/virtu_capability_v1
   ```
   达标判据：边界 ≥80、综合 ≥78、其余七维任一不掉 >5 分。

## 三、成本与预期
- V100 32G @ ¥1.98/h，8B QLoRA 单轮约 2–3 小时 → **单轮约 4–6 元**；迭代追加 <30 元。
- 全程不换基座（复用 qwen3:8b + 工具壳），工具调用能力零成本保留。
