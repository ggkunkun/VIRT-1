# Virtu 算子「理论极限」核验报告

- **run_id（内容指纹）**: `6921d72fb7cd7e34`
- **硬件**: `NVIDIA GeForce RTX 4050 Laptop GPU`，实测带宽 **171.4 GB/s**（64MB D2D copy），实测算力 FP32 6.13 / TF32 11.46 / BF16 26.13 TFLOPS（4096³ GEMM）
- **口径**: `basis=measured`，硬件上界为当次现场实测（非规格表）；计时样本 n=3132；证据 `benchmarks\model_operator_theoretical_limit_report.json`
- **下界定义**: `max(min_FLOPs/peak_flops, min_bytes/peak_bandwidth)，理想单 kernel 下界`
- **CUDA Graph 等价性闸门**: [PASS] 全部 0 误差
- **收腿漂移**: 无（起腿/收腿源码哈希一致）

## 1. 净 GPU 耗时（ms，CUDA Graph replay + CUDA Event）

| seq | 算子 | eager_fp32(wall) | graph_fp32 | graph_tf32 | graph_bf16 |
| ---: | :--- | ---: | ---: | ---: | ---: |
| 128 | VirtuAttention | 0.841 | 0.161 | 0.132 | 0.092 |
| 128 | UniRoPE | 0.286 | 0.027 | 0.027 | 0.028 |
| 128 | VirtuSwiGLU | 0.205 | 0.322 | 0.227 | 0.143 |
| 128 | VirtuRMSNorm | 0.091 | 0.014 | 0.014 | 0.018 |
| 512 | VirtuAttention | 1.210 | 0.747 | 0.615 | 0.279 |
| 512 | UniRoPE | 0.256 | 0.058 | 0.058 | 0.058 |
| 512 | VirtuSwiGLU | 1.326 | 0.976 | 0.521 | 0.272 |
| 512 | VirtuRMSNorm | 0.163 | 0.025 | 0.025 | 0.035 |
| 1024 | VirtuAttention | 2.310 | 2.425 | 2.313 | 0.605 |
| 1024 | UniRoPE | 0.325 | 0.101 | 0.102 | 0.099 |
| 1024 | VirtuSwiGLU | 2.028 | 2.010 | 1.163 | 0.495 |
| 1024 | VirtuRMSNorm | 0.067 | 0.040 | 0.039 | 0.056 |

## 2. 距理论极限

- **VirtuAttention**: 最贴近下界 `graph_fp32`（S=512） 净耗时 0.7465 ms / 下界 0.4377 ms → 效率 **58.6%**，距极限 **1.71x** ⬆ 仍有空间；绝对最快臂 `graph_bf16`（S=128，0.0921 ms），相对当前 eager FP32 生产路径 **5.46x**（跨 seq 范围 3.77–8.39x）
- **UniRoPE**: 最贴近下界 `graph_fp32`（S=1024） 净耗时 0.1014 ms / 下界 0.0734 ms → 效率 **72.4%**，距极限 **1.38x** ✅ 已达极限；绝对最快臂 `graph_fp32`（S=128，0.0266 ms），相对当前 eager FP32 生产路径 **5.50x**（跨 seq 范围 3.18–9.16x）
- **VirtuSwiGLU**: 最贴近下界 `graph_tf32`（S=512） 净耗时 0.5212 ms / 下界 0.4215 ms → 效率 **80.9%**，距极限 **1.24x** ✅ 已达极限；绝对最快臂 `graph_bf16`（S=128，0.1434 ms），相对当前 eager FP32 生产路径 **3.42x**（跨 seq 范围 1.40–4.76x）
- **VirtuRMSNorm**: 最贴近下界 `graph_tf32`（S=1024） 净耗时 0.0389 ms / 下界 0.0489 ms → 效率 **125.8%**，距极限 **0.80x** ✅ 已达极限；绝对最快臂 `graph_tf32`（S=128，0.0141 ms），相对当前 eager FP32 生产路径 **3.91x**（跨 seq 范围 1.60–5.17x）

## 3. 实测观察（不做选择性略去）
- BF16 反而慢于 FP32 的组合：UniRoPE@S=128 (0.0277 vs 0.0266 ms); VirtuRMSNorm@S=128 (0.0183 vs 0.0143 ms); VirtuRMSNorm@S=512 (0.0348 vs 0.0246 ms); VirtuRMSNorm@S=1024 (0.0563 vs 0.0397 ms)
- speedup_vs_eager_wall_x 口径：每个 seq 取最快 graph 臂的 wall 与该 seq 的 eager_fp32 wall 之比，再跨 seq 取算术平均；报告同时给出 min/max，因 eager wall 含 CPU 调度噪声，跨轮波动明显，kernel_ms 才是稳定量。

## 4. 工具链不可达项（按 §6 停止，不虚报加速）
- Triton 未安装（torch.compile 无融合后端），无法编写自定义 RoPE/归一化融合 kernel
- PyTorch 2.6.0+cu124 Windows 构建未编译 FlashAttention；SDPA 的 enable_gqa 会退到 math 后端并变慢
- attention 的 roofline 下界假设存在理想 fused attention kernel，本机只能用 mem-efficient/math SDPA

> `eager_fp32` 为当前生产路径（含 Python 调度与逐 kernel launch）；`graph_*` 已消除 launch 间隙，故与上表同尺度比较。跨 dtype 的精度代价记录在 JSON 的 `fp32_to_this_dtype_max_diff`，不作为通过/失败判据。
