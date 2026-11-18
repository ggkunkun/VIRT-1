# 定制 CUDA 算子实测（2026-11-08）

- run_id: `cba36ca2b550fb16`（内容指纹：配置+内核源码 sha）
- 硬件: `NVIDIA GeForce RTX 4050 Laptop GPU`，驱动 617.14，torch 2.6.0+cu124
- 内核编译: cubin 96160B @ sm_89，源 sha256 `7689609d3f302a1a…`
- 口径: basis=measured；CUDA Event 计时 warmup=5/repeats=20 取 min

## 结果（ms，min）

| op | seq/n | dtype | torch | cuda_ops | speedup |
|---|---|---|---:|---:|---:|
| module:model_forward | 24 | fp32 | 6.3222 | 3.5492 | 1.78x |
| swiglu | 128 | fp32 | 0.0111 (torch_silu_mul) | 0.0061 | 1.80x |
| swiglu | 128 | bf16 | 0.0092 (torch_silu_mul) | 0.0071 | 1.29x |
| swiglu | 512 | fp32 | 0.0276 (torch_silu_mul) | 0.0154 | 1.80x |
| swiglu | 512 | bf16 | 0.0246 (torch_silu_mul) | 0.0174 | 1.41x |
| swiglu | 1024 | fp32 | 0.2191 (torch_silu_mul) | 0.2038 | 1.08x |
| swiglu | 1024 | bf16 | 0.0440 (torch_silu_mul) | 0.0307 | 1.43x |
| rmsnorm | 128 | fp32 | 0.0165 (torch_F.rms_norm) | 0.0072 | 2.30x |
| rmsnorm | 128 | bf16 | 0.0225 (torch_F.rms_norm) | 0.0072 | 3.14x |
| rmsnorm | 512 | fp32 | 0.0289 (torch_F.rms_norm) | 0.0174 | 1.66x |
| rmsnorm | 512 | bf16 | 0.0410 (torch_F.rms_norm) | 0.0174 | 2.35x |
| rmsnorm | 1024 | fp32 | 0.0451 (torch_F.rms_norm) | 0.0317 | 1.42x |
| rmsnorm | 1024 | bf16 | 0.0664 (torch_F.rms_norm) | 0.0316 | 2.10x |
| rope1d | 128 | fp32 | 0.0758 (unirope_apply_1d) | 0.0072 | 10.57x |
| rope1d | 128 | bf16 | 0.0993 (unirope_apply_1d) | 0.0091 | 10.97x |
| rope1d | 512 | fp32 | 0.1362 (unirope_apply_1d) | 0.0133 | 10.23x |
| rope1d | 512 | bf16 | 0.0960 (unirope_apply_1d) | 0.0215 | 4.46x |
| rope1d | 1024 | fp32 | 0.1935 (unirope_apply_1d) | 0.0223 | 8.68x |
| rope1d | 1024 | bf16 | 0.1587 (unirope_apply_1d) | 0.0378 | 4.20x |
| rope2d | 16x16 | fp32 | 0.5315 (unirope_apply_2d) | 0.0102 | 51.90x |
| rope2d | 32x32 | fp32 | 0.6216 (unirope_apply_2d) | 0.0276 | 22.48x |
| fea_batch | 1000 | fp32 | 0.0226 | 0.0031 | 7.34x |
| fea_batch | 100000 | fp32 | 0.0317 | 0.0051 | 6.20x |
| fea_batch | 1000000 | fp32 | 0.1843 | 0.0315 | 5.85x |
| collision_batch | 1000 | fp32 | 0.0123 | 0.0031 | 4.00x |
| collision_batch | 100000 | fp32 | 0.0163 | 0.0051 | 3.18x |
| collision_batch | 1000000 | fp32 | 0.0480 | 0.0256 | 1.87x |
| module:rmsnorm | 128 | fp32 | 0.0164 | 0.0072 | 2.29x |
| module:swiglu | 128 | fp32 | 0.2089 | 0.2099 | 1.00x |
| module:rope1d | 128 | fp32 | 0.0586 | 0.0072 | 8.17x |
| module:rmsnorm | 512 | fp32 | 0.0287 | 0.0174 | 1.65x |
| module:swiglu | 512 | fp32 | 0.8069 | 0.8069 | 1.00x |
| module:rope1d | 512 | fp32 | 0.1304 | 0.0133 | 9.80x |
| module:rmsnorm | 1024 | fp32 | 0.0451 | 0.0317 | 1.42x |
| module:swiglu | 1024 | fp32 | 1.6722 | 1.6712 | 1.00x |
| module:rope1d | 1024 | fp32 | 0.1894 | 0.0224 | 8.47x |

> 跨臂形状与既有《理论极限》报告同源（B=2, hidden=512, heads=8, head_dim=64, inter=1536）。未做跨 dtype 精度判据：精度由 `tests/test_cuda_kernels.py` 对 fp64 参照判定。
