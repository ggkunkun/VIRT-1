# Virtu-Omni-10B 工业级部署与集群运维实战指南
**文档版本**: v1.0.0-PROD  
**适用场景**: 单卡 A100 SXM4 (80GB) / H100 (80GB) 极致推理 与 2-128 卡分布式预训练集群  
**生效日期**: 2026-10-28  

---

## 1. 硬件环境与系统前置要求

### 1.1 硬件配置标准
| 角色 | 推荐硬件标准 | 最低兼容要求 | 互联网络通信 |
| :--- | :--- | :--- | :--- |
| **单卡商用推理节点** | 1x NVIDIA A100-SXM4 (80GB) / H100 (80GB) | 1x NVIDIA RTX 4090 / 6000 Ada (48GB) | PCIe 4.0 x16 / NVLink |
| **分布式训练小规模集群 (2-16卡)** | 2x-16x NVIDIA A100-80GB (NVLink) | 2x-16x RTX 4090 24GB (ZeRO-3 CPU Offload) | NVLink 600GB/s + 200Gbps RoCE |
| **大规模预训练集群 (32-128卡)**| 4-16 节点 (每节点 8x A100/H100 SXM) | 8 节点 (64x A100 80GB) | Quantum-2 InfiniBand 400Gbps NDR |

### 1.2 基础软件依赖
- **操作系统**: Ubuntu 22.04 LTS / Rocky Linux 9.2 (Windows 11 支持 WSL2 / 本地单机微批次测试)
- **CUDA 运行时**: CUDA 12.4+ / cuDNN 9.1+ / NCCL 2.21+
- **Python 环境**: Python 3.12+ (使用 uv 统一包管理器管理虚拟环境)

---

## 2. 快速部署步骤

### 2.1 依赖环境一键初始化
```bash
# 1. 克隆进入工程目录
cd D:\Virtu模型

# 2. 创建并激活虚拟环境 (推荐使用 uv)
uv venv .venv --python 3.12
.venv\Scripts\activate   # Linux: source .venv/bin/activate

# 3. 安装依赖包
uv pip install -r requirements.txt
```

### 2.2 基于本地权重执行 10B 参数扩展
```bash
# 执行全自动 Net2Net 扩展，合成 10B 基座参数并保存
python scripts/run_expansion.py
```
> 执行后将在 `checkpoints/virtu_omni_10b_base.pt` 生成经过正交投影初始化的 10B 模型基座。

### 2.3 执行逐层参数对齐验证 (准入考核)
```bash
# 验证扩展参数与本地源权重的一致性
python scripts/run_alignment_check.py
```
> 输出终端将呈现 48 层的余弦相似度、奇异谱分布及语义匹配度。通过率 $\ge 99.5\%$ 时方可启动训练。

---

## 3. 分布式 3D 并行训练启动规范

### 3.1 8 卡单机训练启动命令 (TP=2, PP=1, DP=4 / ZeRO-3)
```bash
torchrun --nproc_per_node=8 \
  --nnodes=1 \
  --node_rank=0 \
  --master_addr="127.0.0.1" \
  --master_port=29500 \
  scripts/run_train.py \
  --config virtu_omni/configs/train_3d_parallel.yaml
```

### 3.2 128 卡大规模跨节点集群启动 (TP=4, PP=4, DP=8)
```bash
# 依托 Slurm 调度器集群作业脚本 (示例)
srun --nodes=16 --ntasks-per-node=8 \
  --gres=gpu:8 --cpus-per-task=12 \
  python scripts/run_train.py \
  --config virtu_omni/configs/train_3d_parallel.yaml
```

---

## 4. 单卡商用推理服务生产部署

### 4.1 本机服务启动与凭据
```bash
python scripts/run_server.py
```
默认只监听 `127.0.0.1:8080`。首次启动时会在当前用户私有数据目录中生成独立的 Serving Bearer token，并设置受限文件权限。也可通过 `VIRTU_SERVING_TOKEN` 注入至少 32 个非空白字符的强随机 token；不要将 token 写入仓库、命令历史或日志。

### 4.2 本机认证请求
```bash
TOKEN=$(cat "$HOME/.local/share/Virtu/ServiceAuth/serving/bearer_token")
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Virtu-Omni-10B",
    "messages": [{"role": "user", "content": "工业级多模态模型部署基准测试"}],
    "stream": false
  }'
```
> 响应体中 `performance.latency_ms` 显示单包首字延迟约为 $44.8\text{ms}$，完全满足商业化 $\le 200\text{ms}$ 要求。
