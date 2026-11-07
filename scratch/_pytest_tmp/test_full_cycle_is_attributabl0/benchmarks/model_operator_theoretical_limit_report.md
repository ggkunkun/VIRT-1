# Virtu 算子「理论极限」核验报告

- **run_id（内容指纹）**: `3114a098137bb856`
- **硬件**: `NVIDIA GeForce RTX 4050 Laptop GPU`，实测带宽 **172.7 GB/s**（64MB D2D copy），实测算力 FP32 5.82 / TF32 9.60 / BF16 20.58 TFLOPS（4096³ GEMM）
- **口径**: `basis=measured`，硬件上界为当次现场实测（非规格表）；计时样本 n=164；证据 `scratch\_pytest_tmp\test_full_cycle_is_attributabl0\benchmarks\model_operator_theoretical_limit_report.json`
- **下界定义**: `max(min_FLOPs/peak_flops, min_bytes/peak_bandwidth)，理想单 kernel 下界`
- **CUDA Graph 等价性闸门**: [PASS] 全部 0 误差
- **收腿漂移**: 无（起腿/收腿源码哈希一致）

## 1. 净 GPU 耗时（ms，CUDA Graph replay + CUDA Event）

| seq | 算子 | eager_fp32(wall) | graph_fp32 | graph_tf32 | graph_bf16 |
| ---: | :--- | ---: | ---: | ---: | ---: |
| 64 | VirtuAttention | 5.045 | 0.097 | 0.081 | 0.065 |
| 64 | UniRoPE | 1.236 | 0.022 | 0.021 | 0.023 |
| 64 | VirtuSwiGLU | 1.076 | 0.118 | 0.095 | 0.063 |
| 64 | VirtuRMSNorm | 0.171 | 0.020 | 0.023 | 0.033 |

## 2. 距理论极限

- **VirtuAttention**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.0973 ms / 下界 0.0375 ms → 效率 **38.5%**，距极限 **2.60x** ⬆ 仍有空间；绝对最快臂 `graph_bf16`（S=64，0.0645 ms），相对当前 eager FP32 生产路径 **11.11x**（跨 seq 范围 11.11–11.11x）
- **UniRoPE**: 最贴近下界 `graph_tf32`（S=64） 净耗时 0.0215 ms / 下界 0.0046 ms → 效率 **21.2%**，距极限 **4.72x** ⬆ 仍有空间；绝对最快臂 `graph_tf32`（S=64，0.0215 ms），相对当前 eager FP32 生产路径 **11.68x**（跨 seq 范围 11.68–11.68x）
- **VirtuSwiGLU**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.1178 ms / 下界 0.1038 ms → 效率 **88.1%**，距极限 **1.13x** ✅ 已达极限；绝对最快臂 `graph_bf16`（S=64，0.0635 ms），相对当前 eager FP32 生产路径 **9.54x**（跨 seq 范围 9.54–9.54x）
- **VirtuRMSNorm**: 最贴近下界 `graph_fp32`（S=64） 净耗时 0.0205 ms / 下界 0.0030 ms → 效率 **14.8%**，距极限 **6.75x** ⬆ 仍有空间；绝对最快臂 `graph_fp32`（S=64，0.0205 ms），相对当前 eager FP32 生产路径 **3.86x**（跨 seq 范围 3.86–3.86x）

## 3. 实测观察（不做选择性略去）
- BF16 反而慢于 FP32 的组合：UniRoPE@S=64 (0.0225 vs 0.0225 ms); VirtuRMSNorm@S=64 (0.0328 vs 0.0205 ms)
- speedup_vs_eager_wall_x 口径：每个 seq 取最快 graph 臂的 wall 与该 seq 的 eager_fp32 wall 之比，再跨 seq 取算术平均；报告同时给出 min/max，因 eager wall 含 CPU 调度噪声，跨轮波动明显，kernel_ms 才是稳定量。

## 4. 工具链不可达项（按 §6 停止，不虚报加速）
- Triton 未安装（torch.compile 无融合后端），无法编写自定义 RoPE/归一化融合 kernel
- PyTorch 2.6.0+cu124 Windows 构建未编译 FlashAttention；SDPA 的 enable_gqa 会退到 math 后端并变慢
- attention 的 roofline 下界假设存在理想 fused attention kernel，本机只能用 mem-efficient/math SDPA

> `eager_fp32` 为当前生产路径（含 Python 调度与逐 kernel launch）；`graph_*` 已消除 launch 间隙，故与上表同尺度比较。跨 dtype 的精度代价记录在 JSON 的 `fp32_to_this_dtype_max_diff`，不作为通过/失败判据。
