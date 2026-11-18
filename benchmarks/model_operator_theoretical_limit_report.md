# Virtu 算子「理论极限」核验报告

- **run_id（内容指纹）**: `2f3570ff888451a0`
- **硬件**: `NVIDIA GeForce RTX 4050 Laptop GPU`，实测带宽 **173.4 GB/s**（64MB D2D copy），实测算力 FP32 6.45 / TF32 12.26 / BF16 26.25 TFLOPS（4096³ GEMM）
- **口径**: `basis=measured`，硬件上界为当次现场实测（非规格表）；计时样本 n=1044；证据 `benchmarks\model_operator_theoretical_limit_report.json`
- **下界定义**: `max(min_FLOPs/peak_flops, min_bytes/peak_bandwidth)，理想单 kernel 下界`
- **CUDA Graph 等价性闸门**: [PASS] 全部 0 误差
- **收腿漂移**: 无（起腿/收腿源码哈希一致）

## 1. 净 GPU 耗时（ms，CUDA Graph replay + CUDA Event）

| seq | 算子 | eager_fp32(wall) | graph_fp32 | graph_tf32 | graph_bf16 |
| ---: | :--- | ---: | ---: | ---: | ---: |
| 64 | VirtuAttention | 1.547 | 0.082 | 0.066 | 0.057 |
| 64 | UniRoPE | 0.140 | 0.008 | 0.008 | 0.009 |
| 64 | VirtuSwiGLU | 0.283 | 0.114 | 0.086 | 0.142 |
| 64 | VirtuRMSNorm | 0.046 | 0.019 | 0.021 | 0.021 |

## 2. 距理论极限

- **VirtuAttention**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.0819 ms / 下界 0.0338 ms → 效率 **41.3%**，距极限 **2.42x** ⬆ 仍有空间；绝对最快臂 `graph_bf16`（S=64，0.0573 ms），相对当前 eager FP32 生产路径 **25.94x**（跨 seq 范围 25.94–25.94x）
- **UniRoPE**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.0082 ms / 下界 0.0045 ms → 效率 **55.4%**，距极限 **1.81x** ⬆ 仍有空间；绝对最快臂 `graph_fp32`（S=64，0.0082 ms），相对当前 eager FP32 生产路径 **11.67x**（跨 seq 范围 11.67–11.67x）
- **VirtuSwiGLU**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.1137 ms / 下界 0.0936 ms → 效率 **82.3%**，距极限 **1.21x** ✅ 已达极限；绝对最快臂 `graph_tf32`（S=64，0.0860 ms），相对当前 eager FP32 生产路径 **3.13x**（跨 seq 范围 3.13–3.13x）
- **VirtuRMSNorm**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.0195 ms / 下界 0.0030 ms → 效率 **15.5%**，距极限 **6.43x** ⬆ 仍有空间；绝对最快臂 `graph_fp32`（S=64，0.0195 ms），相对当前 eager FP32 生产路径 **2.10x**（跨 seq 范围 2.10–2.10x）

## 3. 实测观察（不做选择性略去）
- BF16 反而慢于 FP32 的组合：UniRoPE@S=64 (0.0091 vs 0.0082 ms); VirtuSwiGLU@S=64 (0.1423 vs 0.1137 ms); VirtuRMSNorm@S=64 (0.0215 vs 0.0195 ms)
- speedup_vs_eager_wall_x 口径：每个 seq 取最快 graph 臂的 wall 与该 seq 的 eager_fp32 wall 之比，再跨 seq 取算术平均；报告同时给出 min/max，因 eager wall 含 CPU 调度噪声，跨轮波动明显，kernel_ms 才是稳定量。

## 4. 工具链不可达项（按 §6 停止，不虚报加速）
- Triton 未安装（torch.compile 无融合后端），无法编写自定义 RoPE/归一化融合 kernel
- PyTorch 2.6.0+cu124 Windows 构建未编译 FlashAttention；SDPA 的 enable_gqa 会退到 math 后端并变慢
- attention 的 roofline 下界假设存在理想 fused attention kernel，本机只能用 mem-efficient/math SDPA

> `eager_fp32` 为当前生产路径（含 Python 调度与逐 kernel launch）；`graph_*` 已消除 launch 间隙，故与上表同尺度比较。跨 dtype 的精度代价记录在 JSON 的 `fp32_to_this_dtype_max_diff`，不作为通过/失败判据。
