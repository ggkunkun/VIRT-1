# Virtu 模型算子优化与核验报告（可归因版）

- **run_id（内容指纹）**: `f527ad8d74cdd866`
- **硬件 / 引擎**: `NVIDIA GeForce RTX 4050 Laptop GPU` / PyTorch `2.6.0+cu124`（CUDA=True, SDPA 接口可用=True）
- **口径**: 所有耗时与显存数字 `basis=measured`，来自本机实际计时；计时样本总量 `n=36`；证据文件 `benchmarks\model_operator_optimization_report.json`
- **瓶颈诊断**: 以下为静态源码审查结论（`basis=inferred`），**非实测**

## 0. 归因与漂移

被测字节（sha256 前缀）:
  - `virtu_eval/provenance.py` = `33a9617523b72718`
  - `virtu_omni/config.py` = `c986bbe3d6900ad3`
  - `virtu_omni/models/architecture.py` = `59d8070d554f62c7`
  - `virtu_omni/models/operator_optimizer.py` = `4b9308168dd9d6f5`

收腿漂移: 无（起腿与收腿的源码哈希一致）

## 1. 算子瓶颈诊断（静态推断）
- **VirtuAttention**: 显式 torch.matmul(q, k.T) + softmax 会分配 BxHxSxS 稠密矩阵；原 GQA 路径还用 expand().reshape() 实体复制 KV 两次。 -> *单次融合 QKV GEMM + SDPA 融合注意力内核；实测本运行时 enable_gqa=True 会退到 math 后端（2.4x 退化），故保留实体展开 KV 的 SDPA 路径。* (`basis=inferred`)
- **UniRoPE**: 原实现每次 forward 都按 max_seq_len(8192) 建表，并调用 positions.max().item() 造成设备到主机同步；2D 视觉网格三角表完全未缓存。 -> *按需几何扩容缓存 + max_pos_hint 消除同步 + 连续位置零拷贝切片替代 gather；2D 网格 cos/sin 表按 (grid, device, dtype) 缓存。* (`basis=inferred`)
- **VirtuSwiGLU**: gate_proj 与 up_proj 是两次独立 GEMM；旧 mul_ 优化只是省掉一个乘积中间张量，未减少 kernel 启动。 -> *推理态 fuse_projections() 将两路权重拼成单次 GEMM 再 chunk；权重为派生 buffer，参数量/梯度契约不变，训练态自动走原路径。* (`basis=inferred`)
- **VirtuRMSNorm**: 旧 forward 只是把 _forward_unopt 内联，仍是 pow->mean->rsqrt->mul->cast->mul 六次 kernel 启动。 -> *CUDA 上调 F.rms_norm 单次融合内核（CPU/混合精度回退原累加顺序）。* (`basis=inferred`)

## 2. 配对实测结果

计时方法：`perf_counter + CUDA synchronize + no_grad + interleaved AB/BA repeats, median of per-repeat means`；等价性闸门：`all output tensors, finite check, shape/dtype/count match, max_abs_diff <= tolerance (fail-closed)`

| 算子 | seq | 基线 ms | 优化 ms | 加速比 | 显存降幅 | max_abs_diff | 闸门 | n |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| `VirtuAttention (fused QKV + SDPA)` | 64 | 2.257 | 1.602 | 1.41x | +6.2% | `1.40e-04` | PASS | 9 |
| `UniRoPE (1D cached)` | 64 | 1.922 | 1.826 | 1.05x | +43.0% | `2.38e-07` | PASS | 9 |
| `VirtuSwiGLU (fused gate/up GEMM)` | 64 | 2.373 | 2.012 | 1.18x | -22.2% | `3.42e-05` | PASS | 9 |
| `VirtuRMSNorm (fused kernel)` | 64 | 0.456 | 0.395 | 1.16x | +25.0% | `4.77e-07` | PASS | 9 |

- **四算子微基准合计耗时比（非整模型端到端）**: **1.20x**
- **峰值显存降幅**: **5.4%** — 各算子独立隔离测得的峰值显存之和的降幅（非整模型峰值显存）
- **数值等价性核验**: `[PASS] 全部等价性闸门通过`
- **退化算子（speedup < 1.00x，不做平均掩盖）**: 无

> 说明：`overall_speedup` = 本表所有配对的 `基线 ms 之和 / 优化 ms 之和`，仅代表这四个微基准，不代表 Ollama/GGUF 部署模型的端到端生成速度。显存列负值表示优化后占用增加，未做截断。
