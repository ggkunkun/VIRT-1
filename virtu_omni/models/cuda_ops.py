# -*- coding: utf-8 -*-
"""cuda_ops —— 运行时编译的定制 CUDA 算子（NVRTC + 驱动 API，零安装）

背景（实测 2026-11-08）
------------------------
`benchmarks/model_operator_theoretical_limit_report.md` 把「自定义融合 kernel」
判为工具链不可达：本机没有 CUDA Toolkit（无 nvcc）、没有 Triton（Windows 无官方
支持）、没有 CuPy。但 torch 2.6.0+cu124 的 wheel 里自带 NVRTC 12.4
（`torch/lib/nvrtc64_120_0.dll`），显示驱动自带 CUDA Driver API
（`nvcuda.dll`）——两者拼起来即可在运行时编译 sm_89 的 CUDA C++、加载并
launch，全程零安装、零新依赖。

本模块提供三族算子（全部带 CPU/fp64 参照可判等价）：

1. 世界模型物理批算子（领域内核）：
   - `fea_batch`：von Mises 等效应力 + FOS + FOS>=1.5 闸门，向量化 N 场景一次
     launch（对应 wm_verifier.recompute(fea_fos) 的批量化，语料级判分热路径）。
   - `collision_batch`：rapid_min/safe_plane/stock_top → collision_risk/gouge/
     autodiff，与 wm_verifier 现行判据（gouge 单独构成 high）同源。
2. 世界模型 Transformer 热路径（本地 PyTorch 推理/训练）：
   - `rmsnorm`（f32/f16/bf16，单遍 block 归约）
   - `swiglu`（silu(gate)*up 单 kernel，替掉 silu+mul 两次访存）
   - `rope1d`（RoPE 连续切片路径：一次读 x、一次写 out，无 cat 中间量）
3. 可用性自省：`available()/capabilities()/kernel_source_sha256()`，供报告与
   闸门做内容寻址（源码哈希进 provenance）。

纪律
----
- 不静默回退：算子对本模块不支持的 dtype/形状一律抛错；架构层的 `*_or_none`
  包装是显式的「不可用即返回 None，由调用方走 torch 路径」。
- 正确性必须由外部参照判：pytest 里对 fp64 CPU 参照 + 植入坏核反证
  （`tests/test_cuda_kernels.py`）。
- 未测不报：性能数字只出自 `scripts/bench_cuda_kernels.py` 的 CUDA Event 实测。
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import threading
from typing import Any, Optional, Tuple

import torch

__all__ = [
    "CudaKernelError",
    "available",
    "capabilities",
    "kernel_source_sha256",
    "rmsnorm",
    "swiglu",
    "rope1d",
    "rope2d",
    "fea_batch",
    "collision_batch",
    "swiglu_or_none",
    "rmsnorm_or_none",
    "rope1d_or_none",
    "rope2d_or_none",
]

# ---------------------------------------------------------------------------
# CUDA C++ 源码（extern "C"，无头文件依赖：16 位转换走内联 PTX）
# ---------------------------------------------------------------------------
_CUDA_SRC = r"""
typedef unsigned char  u8;
typedef unsigned short u16;

// NVRTC 按 C++ 编译：不加 extern "C" 时符号被修饰，cuModuleGetFunction 查不到（rc=500）。
extern "C" {

// ---- 16-bit <-> fp32 转换：不依赖 cuda_fp16.h / cuda_bf16.h（本机无 CUDA include） ----
__device__ __forceinline__ float f32_from_f16(u16 h) {
    float f; asm("cvt.f32.f16 %0, %1;" : "=f"(f) : "h"(h)); return f;
}
__device__ __forceinline__ u16 f16_from_f32(float f) {
    u16 h; asm("cvt.rn.f16.f32 %0, %1;" : "=h"(h) : "f"(f)); return h;
}
__device__ __forceinline__ float f32_from_bf16(u16 h) {
    float f; asm("cvt.f32.bf16 %0, %1;" : "=f"(f) : "h"(h)); return f;
}
__device__ __forceinline__ u16 bf16_from_f32(float f) {
    u16 h; asm("cvt.rn.bf16.f32 %0, %1;" : "=h"(h) : "f"(f)); return h;
}

// ---- block 归约：只依赖 shared memory（NVRTC 内置头对 shuffle 声明不保证） ----
__device__ float block_sum(float v, float* smem) {
    int tid = threadIdx.x;
    smem[tid] = v;
    __syncthreads();
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) smem[tid] += smem[tid + stride];
        __syncthreads();
    }
    return smem[0];
}

// ======================= RMSNorm =======================
// 单遍：读 x 一次（平方和）-> 归约 -> 再读一次做缩放。weight 与 x 同 dtype。
__global__ void v_rmsnorm_f32(const float* __restrict__ x, const float* __restrict__ w,
                              float* __restrict__ out, float eps, int rows, int cols) {
    extern __shared__ float smem[];
    const int row = blockIdx.x;
    const float* xr = x + (long)row * cols;
    float* orow = out + (long)row * cols;
    float acc = 0.f;
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = xr[i];
        acc += v * v;
    }
    acc = block_sum(acc, smem);
    float scale = rsqrtf(acc / (float)cols + eps);
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        orow[i] = xr[i] * scale * w[i];
    }
}

__global__ void v_rmsnorm_f16(const u16* __restrict__ x, const u16* __restrict__ w,
                              u16* __restrict__ out, float eps, int rows, int cols) {
    extern __shared__ float smem[];
    const int row = blockIdx.x;
    const u16* xr = x + (long)row * cols;
    u16* orow = out + (long)row * cols;
    float acc = 0.f;
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = f32_from_f16(xr[i]);
        acc += v * v;
    }
    acc = block_sum(acc, smem);
    float scale = rsqrtf(acc / (float)cols + eps);
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = f32_from_f16(xr[i]);
        float wv = f32_from_f16(w[i]);
        orow[i] = f16_from_f32(v * scale * wv);
    }
}

__global__ void v_rmsnorm_bf16(const u16* __restrict__ x, const u16* __restrict__ w,
                               u16* __restrict__ out, float eps, int rows, int cols) {
    extern __shared__ float smem[];
    const int row = blockIdx.x;
    const u16* xr = x + (long)row * cols;
    u16* orow = out + (long)row * cols;
    float acc = 0.f;
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = f32_from_bf16(xr[i]);
        acc += v * v;
    }
    acc = block_sum(acc, smem);
    float scale = rsqrtf(acc / (float)cols + eps);
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
        float v = f32_from_bf16(xr[i]);
        float wv = f32_from_bf16(w[i]);
        orow[i] = bf16_from_f32(v * scale * wv);
    }
}

// ======================= SwiGLU =======================
// out = silu(gate) * up，元素级一次读写。
__device__ __forceinline__ float silu1(float g) {
    return g / (1.0f + expf(-g));
}

__global__ void v_swiglu_f32(const float* __restrict__ g, const float* __restrict__ u,
                             float* __restrict__ o, int n) {
    int i = (blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (i + 3 < n) {
        float4 gv = *reinterpret_cast<const float4*>(g + i);
        float4 uv = *reinterpret_cast<const float4*>(u + i);
        float4 ov;
        ov.x = silu1(gv.x) * uv.x; ov.y = silu1(gv.y) * uv.y;
        ov.z = silu1(gv.z) * uv.z; ov.w = silu1(gv.w) * uv.w;
        *reinterpret_cast<float4*>(o + i) = ov;
    } else {
        for (; i < n; ++i) o[i] = silu1(g[i]) * u[i];
    }
}

__global__ void v_swiglu_f16(const u16* __restrict__ g, const u16* __restrict__ u,
                             u16* __restrict__ o, int n) {
    int i = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 < n) {
        float g0 = f32_from_f16(g[i]), g1 = f32_from_f16(g[i + 1]);
        float u0 = f32_from_f16(u[i]), u1 = f32_from_f16(u[i + 1]);
        o[i] = f16_from_f32(silu1(g0) * u0);
        o[i + 1] = f16_from_f32(silu1(g1) * u1);
    } else if (i < n) {
        o[i] = f16_from_f32(silu1(f32_from_f16(g[i])) * f32_from_f16(u[i]));
    }
}

__global__ void v_swiglu_bf16(const u16* __restrict__ g, const u16* __restrict__ u,
                              u16* __restrict__ o, int n) {
    int i = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 < n) {
        float g0 = f32_from_bf16(g[i]), g1 = f32_from_bf16(g[i + 1]);
        float u0 = f32_from_bf16(u[i]), u1 = f32_from_bf16(u[i + 1]);
        o[i] = bf16_from_f32(silu1(g0) * u0);
        o[i + 1] = bf16_from_f32(silu1(g1) * u1);
    } else if (i < n) {
        o[i] = bf16_from_f32(silu1(f32_from_bf16(g[i])) * f32_from_bf16(u[i]));
    }
}

// ======================= RoPE (1D, contiguous rows) =======================
// x[B,S,H,D] 连续；cos/sin 为 [S,D] 连续表（UniRoPE 的 contiguous_slice 缓存）。
// out[d] = x[d]*cos[s,d] + rot(x)[d]*sin[s,d]; rot(x)[d]=-x[d+D/2] (d<D/2) else +x[d-D/2]
__global__ void v_rope1d_f32(const float* __restrict__ x, const float* __restrict__ cos,
                             const float* __restrict__ sin, float* __restrict__ out,
                             int B, int S, int H, int D) {
    long total = (long)B * S * H * D;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (i + 3 >= total) {
        for (; i < total; ++i) {
            long row = i / D;
            int d = (int)(i - row * D);
            int s = (int)((row / H) % S);
            long base = row * D;
            int half = D >> 1;
            float xv = x[i];
            float rv = (d < half) ? -x[base + d + half] : x[base + d - half];
            out[i] = xv * cos[(long)s * D + d] + rv * sin[(long)s * D + d];
        }
        return;
    }
    long row = i / D;
    int d = (int)(i - row * D);
    int s = (int)((row / H) % S);
    long base = row * D;
    int half = D >> 1;
    float4 xv = *reinterpret_cast<const float4*>(x + i);
    float4 ov;
    float c = cos[(long)s * D + d], sn = sin[(long)s * D + d];
    float r = (d < half) ? -x[base + d + half] : x[base + d - half];
    ov.x = xv.x * c + r * sn;
    c = cos[(long)s * D + d + 1]; sn = sin[(long)s * D + d + 1];
    r = (d + 1 < half) ? -x[base + d + 1 + half] : x[base + d + 1 - half];
    ov.y = xv.y * c + r * sn;
    c = cos[(long)s * D + d + 2]; sn = sin[(long)s * D + d + 2];
    r = (d + 2 < half) ? -x[base + d + 2 + half] : x[base + d + 2 - half];
    ov.z = xv.z * c + r * sn;
    c = cos[(long)s * D + d + 3]; sn = sin[(long)s * D + d + 3];
    r = (d + 3 < half) ? -x[base + d + 3 + half] : x[base + d + 3 - half];
    ov.w = xv.w * c + r * sn;
    *reinterpret_cast<float4*>(out + i) = ov;
}

__global__ void v_rope1d_f16(const u16* __restrict__ x, const u16* __restrict__ cos,
                             const u16* __restrict__ sin, u16* __restrict__ out,
                             int B, int S, int H, int D) {
    long total = (long)B * S * H * D;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 >= total) {
        if (i < total) {
            long row = i / D; int d = (int)(i - row * D);
            int s = (int)((row / H) % S); long base = row * D; int half = D >> 1;
            float rv = (d < half) ? -f32_from_f16(x[base + d + half]) : f32_from_f16(x[base + d - half]);
            out[i] = f16_from_f32(f32_from_f16(x[i]) * f32_from_f16(cos[(long)s * D + d])
                                  + rv * f32_from_f16(sin[(long)s * D + d]));
        }
        return;
    }
    long row = i / D; int d = (int)(i - row * D);
    int s = (int)((row / H) % S); long base = row * D; int half = D >> 1;
    for (int k = 0; k < 2; ++k) {
        long e = i + k; int dk = d + k;
        float xv = f32_from_f16(x[e]);
        float rv = (dk < half) ? -f32_from_f16(x[base + dk + half]) : f32_from_f16(x[base + dk - half]);
        out[e] = f16_from_f32(xv * f32_from_f16(cos[(long)s * D + dk])
                              + rv * f32_from_f16(sin[(long)s * D + dk]));
    }
}

__global__ void v_rope1d_bf16(const u16* __restrict__ x, const u16* __restrict__ cos,
                              const u16* __restrict__ sin, u16* __restrict__ out,
                              int B, int S, int H, int D) {
    long total = (long)B * S * H * D;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 >= total) {
        if (i < total) {
            long row = i / D; int d = (int)(i - row * D);
            int s = (int)((row / H) % S); long base = row * D; int half = D >> 1;
            float rv = (d < half) ? -f32_from_bf16(x[base + d + half]) : f32_from_bf16(x[base + d - half]);
            out[i] = bf16_from_f32(f32_from_bf16(x[i]) * f32_from_bf16(cos[(long)s * D + d])
                                   + rv * f32_from_bf16(sin[(long)s * D + d]));
        }
        return;
    }
    long row = i / D; int d = (int)(i - row * D);
    int s = (int)((row / H) % S); long base = row * D; int half = D >> 1;
    for (int k = 0; k < 2; ++k) {
        long e = i + k; int dk = d + k;
        float xv = f32_from_bf16(x[e]);
        float rv = (dk < half) ? -f32_from_bf16(x[base + dk + half]) : f32_from_bf16(x[base + dk - half]);
        out[e] = bf16_from_f32(xv * f32_from_bf16(cos[(long)s * D + dk])
                               + rv * f32_from_bf16(sin[(long)s * D + dk]));
    }
}

// ======================= RoPE 2D（视觉网格） =======================
// x[B,N,H,D]，N=grid_h*grid_w。D 的前半区用 y 轴表、后半区用 x 轴表（各 [N, D/2]）；
// 半区内部再按 rotate_half 以 D/4 为界换位 —— 与 UniRoPE.apply_2d_rope 逐字同式。
__device__ __forceinline__ void rope2d_map(int d, int D, int& j, int& partner,
                                           float& sign) {
    int half = D >> 1;
    int quarter = half >> 1;
    int base_half = (d < half) ? 0 : half;
    j = (d < half) ? d : d - half;
    partner = base_half + ((j < quarter) ? j + quarter : j - quarter);
    sign = (j < quarter) ? -1.0f : 1.0f;
}

__global__ void v_rope2d_f32(const float* __restrict__ x,
                             const float* __restrict__ cosy, const float* __restrict__ siny,
                             const float* __restrict__ cosx, const float* __restrict__ sinx,
                             float* __restrict__ out, int B, int N, int H, int D) {
    long total = (long)B * N * H * D;
    int half = D >> 1;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (i + 3 >= total) {
        for (; i < total; ++i) {
            long row = i / D; int d = (int)(i - row * D);
            int n = (int)((row / H) % N);
            int j, partner; float sign;
            rope2d_map(d, D, j, partner, sign);
            const float* c = (d < half) ? cosy : cosx;
            const float* s = (d < half) ? siny : sinx;
            long ti = (long)n * half + j;
            out[i] = x[i] * c[ti] + sign * x[row * D + partner] * s[ti];
        }
        return;
    }
    long row = i / D; int d = (int)(i - row * D);
    int n = (int)((row / H) % N);
    float4 xv = *reinterpret_cast<const float4*>(x + i);
    float vals[4] = {xv.x, xv.y, xv.z, xv.w};
    float4 ov;
    float* op = reinterpret_cast<float*>(&ov);
    for (int k = 0; k < 4; ++k) {
        int dk = d + k;
        int j, partner; float sign;
        rope2d_map(dk, D, j, partner, sign);
        const float* c = (dk < half) ? cosy : cosx;
        const float* s = (dk < half) ? siny : sinx;
        long ti = (long)n * half + j;
        op[k] = vals[k] * c[ti] + sign * x[row * D + partner] * s[ti];
    }
    *reinterpret_cast<float4*>(out + i) = ov;
}

__global__ void v_rope2d_f16(const u16* __restrict__ x,
                             const u16* __restrict__ cosy, const u16* __restrict__ siny,
                             const u16* __restrict__ cosx, const u16* __restrict__ sinx,
                             u16* __restrict__ out, int B, int N, int H, int D) {
    long total = (long)B * N * H * D;
    int half = D >> 1;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 >= total) {
        if (i < total) {
            long row = i / D; int d = (int)(i - row * D);
            int n = (int)((row / H) % N);
            int j, partner; float sign;
            rope2d_map(d, D, j, partner, sign);
            const u16* c = (d < half) ? cosy : cosx;
            const u16* s = (d < half) ? siny : sinx;
            long ti = (long)n * half + j;
            float rv = f32_from_f16(x[row * D + partner]);
            out[i] = f16_from_f32(f32_from_f16(x[i]) * f32_from_f16(c[ti])
                                  + sign * rv * f32_from_f16(s[ti]));
        }
        return;
    }
    long row = i / D; int d = (int)(i - row * D);
    int n = (int)((row / H) % N);
    for (int k = 0; k < 2; ++k) {
        long e = i + k; int dk = d + k;
        int j, partner; float sign;
        rope2d_map(dk, D, j, partner, sign);
        const u16* c = (dk < half) ? cosy : cosx;
        const u16* s = (dk < half) ? siny : sinx;
        long ti = (long)n * half + j;
        float rv = f32_from_f16(x[row * D + partner]);
        out[e] = f16_from_f32(f32_from_f16(x[e]) * f32_from_f16(c[ti])
                              + sign * rv * f32_from_f16(s[ti]));
    }
}

__global__ void v_rope2d_bf16(const u16* __restrict__ x,
                              const u16* __restrict__ cosy, const u16* __restrict__ siny,
                              const u16* __restrict__ cosx, const u16* __restrict__ sinx,
                              u16* __restrict__ out, int B, int N, int H, int D) {
    long total = (long)B * N * H * D;
    int half = D >> 1;
    long i = ((long)blockIdx.x * blockDim.x + threadIdx.x) * 2;
    if (i + 1 >= total) {
        if (i < total) {
            long row = i / D; int d = (int)(i - row * D);
            int n = (int)((row / H) % N);
            int j, partner; float sign;
            rope2d_map(d, D, j, partner, sign);
            const u16* c = (d < half) ? cosy : cosx;
            const u16* s = (d < half) ? siny : sinx;
            long ti = (long)n * half + j;
            float rv = f32_from_bf16(x[row * D + partner]);
            out[i] = bf16_from_f32(f32_from_bf16(x[i]) * f32_from_bf16(c[ti])
                                   + sign * rv * f32_from_bf16(s[ti]));
        }
        return;
    }
    long row = i / D; int d = (int)(i - row * D);
    int n = (int)((row / H) % N);
    for (int k = 0; k < 2; ++k) {
        long e = i + k; int dk = d + k;
        int j, partner; float sign;
        rope2d_map(dk, D, j, partner, sign);
        const u16* c = (dk < half) ? cosy : cosx;
        const u16* s = (dk < half) ? siny : sinx;
        long ti = (long)n * half + j;
        float rv = f32_from_bf16(x[row * D + partner]);
        out[e] = bf16_from_f32(f32_from_bf16(x[e]) * f32_from_bf16(c[ti])
                               + sign * rv * f32_from_bf16(s[ti]));
    }
}

// ======================= 物理批算子（世界模型领域内核） =======================
// sigma_vm = sqrt(sx^2 - sx*sy + sy^2 + 3*tau^2); fos = Sy/sigma_vm;
// gate = fos >= 1.5（与 wm_verifier.recompute(fea_fos) 同式同阈值）。
__device__ __forceinline__ float vm_stress(float sx, float sy, float tau) {
    return sqrtf(fmaxf(sx * sx - sx * sy + sy * sy + 3.0f * tau * tau, 0.0f));
}

__global__ void v_fea_batch_f32(const float* __restrict__ sx, const float* __restrict__ sy,
                                const float* __restrict__ tau, const float* __restrict__ Sy,
                                float* __restrict__ svm, float* __restrict__ fos,
                                u8* __restrict__ gate, int n) {
    int i = (blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (i + 3 < n) {
        float4 a = *reinterpret_cast<const float4*>(sx + i);
        float4 b = *reinterpret_cast<const float4*>(sy + i);
        float4 t = *reinterpret_cast<const float4*>(tau + i);
        float4 y = *reinterpret_cast<const float4*>(Sy + i);
        float4 v, f;
        v.x = vm_stress(a.x, b.x, t.x); v.y = vm_stress(a.y, b.y, t.y);
        v.z = vm_stress(a.z, b.z, t.z); v.w = vm_stress(a.w, b.w, t.w);
        f.x = y.x / v.x; f.y = y.y / v.y; f.z = y.z / v.z; f.w = y.w / v.w;
        *reinterpret_cast<float4*>(svm + i) = v;
        *reinterpret_cast<float4*>(fos + i) = f;
        gate[i] = f.x >= 1.5f; gate[i + 1] = f.y >= 1.5f;
        gate[i + 2] = f.z >= 1.5f; gate[i + 3] = f.w >= 1.5f;
    } else {
        for (; i < n; ++i) {
            float v = vm_stress(sx[i], sy[i], tau[i]);
            svm[i] = v;
            fos[i] = Sy[i] / v;
            gate[i] = (Sy[i] / v) >= 1.5f;
        }
    }
}

// 与 wm_verifier 现行判据同源：risk = (zm < zs && zm < zt+1) || gouge；gouge = zm < zt
// autodiff: 0=green, 1=yellow, 2=red
__global__ void v_collision_batch_f32(const float* __restrict__ zs, const float* __restrict__ zm,
                                      const float* __restrict__ zt,
                                      u8* __restrict__ risk, u8* __restrict__ gouge,
                                      u8* __restrict__ adiff, int n) {
    int i = (blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (i + 3 < n) {
        float4 a = *reinterpret_cast<const float4*>(zs + i);
        float4 b = *reinterpret_cast<const float4*>(zm + i);
        float4 c = *reinterpret_cast<const float4*>(zt + i);
        float av[4] = {a.x, a.y, a.z, a.w};
        float bv[4] = {b.x, b.y, b.z, b.w};
        float cv[4] = {c.x, c.y, c.z, c.w};
        for (int k = 0; k < 4; ++k) {
            bool g = bv[k] < cv[k];
            bool r = ((bv[k] < av[k]) && (bv[k] < cv[k] + 1.0f)) || g;
            long e = i + k;
            gouge[e] = g; risk[e] = r;
            adiff[e] = g ? 2 : (r ? 1 : 0);
        }
    } else {
        for (; i < n; ++i) {
            bool g = zm[i] < zt[i];
            bool r = ((zm[i] < zs[i]) && (zm[i] < zt[i] + 1.0f)) || g;
            gouge[i] = g; risk[i] = r;
            adiff[i] = g ? 2 : (r ? 1 : 0);
        }
    }
}

}  // extern "C"
"""

# ---------------------------------------------------------------------------
# ctypes 绑定：NVRTC（torch/lib）+ CUDA Driver API（nvcuda.dll）
# ---------------------------------------------------------------------------
class CudaKernelError(RuntimeError):
    pass


def _torch_lib_dir() -> str:
    return os.path.join(os.path.dirname(torch.__file__), "lib")


def _load_nvrtc() -> ctypes.CDLL:
    libdir = _torch_lib_dir()
    cands = sorted(n for n in os.listdir(libdir)
                   if n.lower().startswith("nvrtc64_") and n.lower().endswith(".dll"))
    if not cands:
        raise CudaKernelError("torch 未携带 nvrtc64_*.dll，无法运行时编译")
    # 优先与 nvrtc-builtins 匹配的版本（版本号在后缀里）
    dll = ctypes.CDLL(os.path.join(libdir, cands[-1]))
    dll.nvrtcCreateProgram.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    dll.nvrtcCreateProgram.restype = ctypes.c_int
    dll.nvrtcCompileProgram.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    dll.nvrtcCompileProgram.restype = ctypes.c_int
    dll.nvrtcGetProgramLogSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    dll.nvrtcGetProgramLogSize.restype = ctypes.c_int
    dll.nvrtcGetProgramLog.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.nvrtcGetProgramLog.restype = ctypes.c_int
    dll.nvrtcGetCUBINSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    dll.nvrtcGetCUBINSize.restype = ctypes.c_int
    dll.nvrtcGetCUBIN.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.nvrtcGetCUBIN.restype = ctypes.c_int
    dll.nvrtcGetPTXSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    dll.nvrtcGetPTXSize.restype = ctypes.c_int
    dll.nvrtcGetPTX.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.nvrtcGetPTX.restype = ctypes.c_int
    dll.nvrtcDestroyProgram.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    dll.nvrtcDestroyProgram.restype = ctypes.c_int
    return dll


def _load_driver() -> ctypes.CDLL:
    drv = ctypes.CDLL("nvcuda.dll")
    drv.cuInit.argtypes = [ctypes.c_uint]
    drv.cuInit.restype = ctypes.c_int
    drv.cuCtxGetCurrent.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    drv.cuCtxGetCurrent.restype = ctypes.c_int
    drv.cuDevicePrimaryCtxRetain.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
    drv.cuDevicePrimaryCtxRetain.restype = ctypes.c_int
    drv.cuCtxSetCurrent.argtypes = [ctypes.c_void_p]
    drv.cuCtxSetCurrent.restype = ctypes.c_int
    drv.cuModuleLoadDataEx.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_uint,
        ctypes.c_void_p, ctypes.c_void_p]
    drv.cuModuleLoadDataEx.restype = ctypes.c_int
    drv.cuModuleGetFunction.argtypes = [
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_char_p]
    drv.cuModuleGetFunction.restype = ctypes.c_int
    drv.cuLaunchKernel.argtypes = ([ctypes.c_void_p] + [ctypes.c_uint] * 6
                                   + [ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p])
    drv.cuLaunchKernel.restype = ctypes.c_int
    drv.cuGetErrorString.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
    drv.cuGetErrorString.restype = ctypes.c_int
    return drv


class _Runtime:
    """编译一次、按进程缓存 module/function；线程安全。"""

    _lock = threading.Lock()

    def __init__(self) -> None:
        self.nvrtc = _load_nvrtc()
        self.drv = _load_driver()
        self.modules: dict = {}      # (dev_cc) -> module handle
        self.funcs: dict = {}        # (dev_cc, name) -> CUfunction
        self.build_info: dict = {}   # cc -> {"kind": cubin|ptx, "bytes": n}
        self.error: Optional[str] = None

    # -- 编译 --
    def _compile(self, src: bytes, arch: str) -> Tuple[str, bytes]:
        prog = ctypes.c_void_p()
        rc = self.nvrtc.nvrtcCreateProgram(
            ctypes.byref(prog), src, b"virtu_ops.cu", 0, None, None)
        if rc != 0:
            raise CudaKernelError(f"nvrtcCreateProgram rc={rc}")
        opts = [b"--gpu-architecture=" + arch.encode(), b"--std=c++17"]
        arr = (ctypes.c_char_p * len(opts))(*opts)
        rc = self.nvrtc.nvrtcCompileProgram(prog, len(opts), arr)
        logsize = ctypes.c_size_t()
        self.nvrtc.nvrtcGetProgramLogSize(prog, ctypes.byref(logsize))
        log = b""
        if logsize.value:
            buf = ctypes.create_string_buffer(logsize.value)
            self.nvrtc.nvrtcGetProgramLog(prog, buf)
            log = buf.value
        if rc != 0:
            self.nvrtc.nvrtcDestroyProgram(ctypes.byref(prog))
            raise CudaKernelError("nvrtc 编译失败: " + log.decode("utf-8", "replace")[:1200])
        # 优先 CUBIN（真实 arch 才能出 cubin），否则 PTX（驱动 JIT）
        csize = ctypes.c_size_t()
        kind = "cubin"
        if self.nvrtc.nvrtcGetCUBINSize(prog, ctypes.byref(csize)) == 0 and csize.value:
            buf = ctypes.create_string_buffer(csize.value)
            if self.nvrtc.nvrtcGetCUBIN(prog, buf) == 0:
                self.nvrtc.nvrtcDestroyProgram(ctypes.byref(prog))
                return kind, buf.raw
        psize = ctypes.c_size_t()
        rc = self.nvrtc.nvrtcGetPTXSize(prog, ctypes.byref(psize))
        if rc != 0 or not psize.value:
            self.nvrtc.nvrtcDestroyProgram(ctypes.byref(prog))
            raise CudaKernelError("nvrtc 未产出 CUBIN/PTX")
        buf = ctypes.create_string_buffer(psize.value)
        self.nvrtc.nvrtcGetPTX(prog, buf)
        self.nvrtc.nvrtcDestroyProgram(ctypes.byref(prog))
        return "ptx", buf.raw

    def ensure(self, device_index: int = 0) -> None:
        torch.cuda.init()
        cc = torch.cuda.get_device_capability(device_index)
        key = int(cc[0] * 10 + cc[1])
        with self._lock:
            if key in self.modules:
                return
            ctx = ctypes.c_void_p()
            self.drv.cuCtxGetCurrent(ctypes.byref(ctx))
            if not ctx.value:  # torch 上下文尚未绑定到本线程
                rc = self.drv.cuDevicePrimaryCtxRetain(ctypes.byref(ctx), device_index)
                if rc != 0:
                    raise CudaKernelError(f"cuDevicePrimaryCtxRetain rc={rc}")
                self.drv.cuCtxSetCurrent(ctx)
            kind, blob = self._compile(_CUDA_SRC.encode(), f"sm_{key}")
            mod = ctypes.c_void_p()
            rc = self.drv.cuModuleLoadDataEx(ctypes.byref(mod), blob, 0, None, None)
            if rc != 0:
                raise CudaKernelError(f"cuModuleLoadDataEx rc={rc} kind={kind}")
            self.modules[key] = mod
            self.build_info[key] = {"kind": kind, "bytes": len(blob), "arch": f"sm_{key}"}

    def function(self, name: str, device_index: int = 0) -> ctypes.c_void_p:
        cc = torch.cuda.get_device_capability(device_index)
        key = int(cc[0] * 10 + cc[1])
        self.ensure(device_index)
        fk = (key, name)
        if fk not in self.funcs:
            fn = ctypes.c_void_p()
            rc = self.drv.cuModuleGetFunction(
                ctypes.byref(fn), self.modules[key], name.encode())
            if rc != 0:
                raise CudaKernelError(f"cuModuleGetFunction({name}) rc={rc}")
            self.funcs[fk] = fn
        return self.funcs[fk]

    def launch(self, name: str, grid: int, block: int, holders: list,
               smem_bytes: int = 0) -> None:
        fn = self.function(name)
        stream = ctypes.c_void_p(torch.cuda.current_stream().cuda_stream)
        # kernelParams[i] 必须是"指向实参值"的地址（驱动解引用取参）；
        # holders 在此保持存活直到 launch 返回。
        params = (ctypes.c_void_p * len(holders))(
            *[ctypes.cast(ctypes.byref(h), ctypes.c_void_p) for h in holders])
        rc = self.drv.cuLaunchKernel(fn, grid, 1, 1, block, 1, 1, smem_bytes,
                                     stream, params, None)
        if rc != 0:
            es = ctypes.c_char_p()
            self.drv.cuGetErrorString(rc, ctypes.byref(es))
            raise CudaKernelError(f"cuLaunchKernel({name}) rc={rc} "
                                  f"{(es.value or b'').decode('utf-8', 'replace')}")


_RT: Optional[_Runtime] = None
_RT_ERROR: Optional[str] = None


def _runtime() -> _Runtime:
    global _RT, _RT_ERROR
    if _RT is not None:
        return _RT
    if _RT_ERROR is not None:
        raise CudaKernelError(_RT_ERROR)
    if not torch.cuda.is_available():
        _RT_ERROR = "CUDA 不可用"
        raise CudaKernelError(_RT_ERROR)
    try:
        _RT = _Runtime()
        _RT.ensure(0)
    except Exception as exc:  # noqa: BLE001 - 可用性查询需要吞掉并记录
        _RT_ERROR = f"{type(exc).__name__}: {exc}"
        raise CudaKernelError(_RT_ERROR) from exc
    return _RT


def available() -> bool:
    try:
        _runtime()
        return True
    except CudaKernelError:
        return False


def capabilities() -> dict:
    """报告编译/加载状态与内容指纹，供报告与 provenance 使用。"""
    out: dict = {"available": False}
    try:
        rt = _runtime()
        cc = torch.cuda.get_device_capability(0)
        key = int(cc[0] * 10 + cc[1])
        out.update({
            "available": True,
            "device": torch.cuda.get_device_name(0),
            "capability": f"{cc[0]}.{cc[1]}",
            "build": rt.build_info.get(key, {}),
            "source_sha256": kernel_source_sha256(),
            "cuda_driver": _driver_version(),
            "torch": torch.__version__,
        })
    except CudaKernelError as exc:
        out["error"] = str(exc)
        if _RT_ERROR:
            out["error"] = _RT_ERROR
    return out


def _driver_version() -> Optional[str]:
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip().splitlines()[0] if r.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def kernel_source_sha256() -> str:
    return hashlib.sha256(_CUDA_SRC.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 参数/张量校验
# ---------------------------------------------------------------------------
_F32 = torch.float32
_F16 = torch.float16
_BF16 = torch.bfloat16


def _check(t: torch.Tensor, name: str) -> None:
    if not t.is_cuda:
        raise CudaKernelError(f"{name} 必须在 CUDA 上")
    if not t.is_contiguous():
        raise CudaKernelError(f"{name} 必须 contiguous（避免隐藏拷贝把加速吃掉）")


def _ptr(t: torch.Tensor) -> ctypes.c_void_p:
    return ctypes.c_void_p(t.data_ptr())


def _i(v: int) -> ctypes.c_int:
    return ctypes.c_int(int(v))


def _f(v: float) -> ctypes.c_float:
    return ctypes.c_float(float(v))


def _numel(*ts: torch.Tensor) -> int:
    n = ts[0].numel()
    for t in ts[1:]:
        if t.numel() != n:
            raise CudaKernelError("算子输入元素数不一致")
    return n


# ---------------------------------------------------------------------------
# 公共算子
# ---------------------------------------------------------------------------
def rmsnorm(x: torch.Tensor, weight: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    _check(x, "x")
    _check(weight, "weight")
    if x.dim() < 1 or weight.dim() != 1 or weight.numel() != x.shape[-1]:
        raise CudaKernelError("rmsnorm 形状不符：weight 必须为 [cols]")
    if weight.dtype != x.dtype:
        raise CudaKernelError("rmsnorm 要求 weight.dtype == x.dtype")
    if x.dtype not in (_F32, _F16, _BF16):
        raise CudaKernelError(f"rmsnorm 不支持 dtype={x.dtype}")
    rows = int(x.numel() // x.shape[-1])
    cols = int(x.shape[-1])
    out = torch.empty_like(x)
    rt = _runtime()
    block = 256
    name = {_F32: "v_rmsnorm_f32", _F16: "v_rmsnorm_f16", _BF16: "v_rmsnorm_bf16"}[x.dtype]
    smem = block * 4
    rt.launch(name, rows, block,
              [_ptr(x), _ptr(weight), _ptr(out), _f(eps), _i(rows), _i(cols)],
              smem_bytes=smem)
    return out


def swiglu(gate: torch.Tensor, up: torch.Tensor) -> torch.Tensor:
    _check(gate, "gate")
    _check(up, "up")
    if gate.shape != up.shape or gate.dtype != up.dtype:
        raise CudaKernelError("swiglu 要求同形同 dtype")
    if gate.dtype not in (_F32, _F16, _BF16):
        raise CudaKernelError(f"swiglu 不支持 dtype={gate.dtype}")
    n = _numel(gate, up)
    out = torch.empty_like(gate)
    rt = _runtime()
    name = {_F32: "v_swiglu_f32", _F16: "v_swiglu_f16", _BF16: "v_swiglu_bf16"}[gate.dtype]
    per = 4 if gate.dtype == _F32 else 2
    block = 256
    grid = (n + block * per - 1) // (block * per)
    rt.launch(name, grid, block, [_ptr(gate), _ptr(up), _ptr(out), _i(n)])
    return out


def rope1d(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    """x[B,S,H,D] 与 [S,D] 的 cos/sin 表（UniRoPE contiguous_slice 路径）。"""
    _check(x, "x")
    _check(cos, "cos")
    _check(sin, "sin")
    if x.dim() != 4:
        raise CudaKernelError("rope1d 需要 x[B,S,H,D]")
    if x.dtype not in (_F32, _F16, _BF16):
        raise CudaKernelError(f"rope1d 不支持 dtype={x.dtype}")
    if cos.dtype != x.dtype or sin.dtype != x.dtype:
        raise CudaKernelError("rope1d 要求 cos/sin dtype == x.dtype")
    B, S, H, D = x.shape
    if cos.shape != (S, D) or sin.shape != (S, D):
        raise CudaKernelError(f"rope1d 表形状应为 [{S},{D}]，实际 {tuple(cos.shape)}")
    if D % 4 != 0 or D % 2 != 0:
        raise CudaKernelError("rope1d 要求 D 为 4 的倍数")
    out = torch.empty_like(x)
    rt = _runtime()
    name = {_F32: "v_rope1d_f32", _F16: "v_rope1d_f16", _BF16: "v_rope1d_bf16"}[x.dtype]
    per = 4 if x.dtype == _F32 else 2
    block = 256
    total = x.numel()
    grid = (total + block * per - 1) // (block * per)
    rt.launch(name, grid, block,
              [_ptr(x), _ptr(cos), _ptr(sin), _ptr(out),
               _i(B), _i(S), _i(H), _i(D)])
    return out


def rope2d(x: torch.Tensor, cos_y: torch.Tensor, sin_y: torch.Tensor,
           cos_x: torch.Tensor, sin_x: torch.Tensor) -> torch.Tensor:
    """视觉网格 2D RoPE：x[B,N,H,D]，N=grid_h*grid_w；四张表 [N, D/2]。"""
    for t, n in ((x, "x"), (cos_y, "cos_y"), (sin_y, "sin_y"),
                 (cos_x, "cos_x"), (sin_x, "sin_x")):
        _check(t, n)
    if x.dim() != 4:
        raise CudaKernelError("rope2d 需要 x[B,N,H,D]")
    if x.dtype not in (_F32, _F16, _BF16):
        raise CudaKernelError(f"rope2d 不支持 dtype={x.dtype}")
    for t, n in ((cos_y, "cos_y"), (sin_y, "sin_y"), (cos_x, "cos_x"), (sin_x, "sin_x")):
        if t.dtype != x.dtype:
            raise CudaKernelError(f"rope2d 要求 {n}.dtype == x.dtype")
    B, N, H, D = x.shape
    half = D // 2
    for t, n in ((cos_y, "cos_y"), (sin_y, "sin_y"), (cos_x, "cos_x"), (sin_x, "sin_x")):
        if tuple(t.shape) != (N, half):
            raise CudaKernelError(f"rope2d 表 {n} 形状应为 [{N},{half}]，实际 {tuple(t.shape)}")
    if D % 4 != 0 or half % 2 != 0:
        raise CudaKernelError("rope2d 要求 D 为 4 的倍数且 D/2 为偶数")
    out = torch.empty_like(x)
    rt = _runtime()
    name = {_F32: "v_rope2d_f32", _F16: "v_rope2d_f16", _BF16: "v_rope2d_bf16"}[x.dtype]
    per = 4 if x.dtype == _F32 else 2
    block = 256
    total = x.numel()
    grid = (total + block * per - 1) // (block * per)
    rt.launch(name, grid, block,
              [_ptr(x), _ptr(cos_y), _ptr(sin_y), _ptr(cos_x), _ptr(sin_x), _ptr(out),
               _i(B), _i(N), _i(H), _i(D)])
    return out


def fea_batch(sigma_x: torch.Tensor, sigma_y: torch.Tensor, tau: torch.Tensor,
              Sy: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """批量 von Mises/FOS/闸门。返回 (sigma_vm, FOS, gate[uint8 0/1])。"""
    for t, n in ((sigma_x, "sigma_x"), (sigma_y, "sigma_y"), (tau, "tau"), (Sy, "Sy")):
        _check(t, n)
        if t.dtype != _F32:
            raise CudaKernelError("fea_batch 目前只支持 float32")
        if t.dim() != 1:
            raise CudaKernelError(f"{n} 需为一维扁平数组")
    n = _numel(sigma_x, sigma_y, tau, Sy)
    svm = torch.empty_like(sigma_x)
    fos = torch.empty_like(sigma_x)
    gate = torch.empty(n, dtype=torch.uint8, device=sigma_x.device)
    rt = _runtime()
    block = 256
    grid = (n + block * 4 - 1) // (block * 4)
    rt.launch("v_fea_batch_f32", grid, block,
              [_ptr(sigma_x), _ptr(sigma_y), _ptr(tau), _ptr(Sy),
               _ptr(svm), _ptr(fos), _ptr(gate), _i(n)])
    return svm, fos, gate


def collision_batch(z_safe: torch.Tensor, z_min_rapid: torch.Tensor,
                    stock_top: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """批量碰撞判定。返回 (risk_high uint8, gouge uint8, autodiff uint8 0/1/2)。"""
    for t, n in ((z_safe, "z_safe"), (z_min_rapid, "z_min_rapid"),
                 (stock_top, "stock_top")):
        _check(t, n)
        if t.dtype != _F32:
            raise CudaKernelError("collision_batch 目前只支持 float32")
        if t.dim() != 1:
            raise CudaKernelError(f"{n} 需为一维扁平数组")
    n = _numel(z_safe, z_min_rapid, stock_top)
    risk = torch.empty(n, dtype=torch.uint8, device=z_safe.device)
    gouge = torch.empty(n, dtype=torch.uint8, device=z_safe.device)
    adiff = torch.empty(n, dtype=torch.uint8, device=z_safe.device)
    rt = _runtime()
    block = 256
    grid = (n + block * 4 - 1) // (block * 4)
    rt.launch("v_collision_batch_f32", grid, block,
              [_ptr(z_safe), _ptr(z_min_rapid), _ptr(stock_top),
               _ptr(risk), _ptr(gouge), _ptr(adiff), _i(n)])
    return risk, gouge, adiff


# ---------------------------------------------------------------------------
# 架构层显式回退包装：不可用/形状不满足 → None（由调用方走 torch 原路径）
# ---------------------------------------------------------------------------
def _fastpath_ok(*ts: torch.Tensor) -> bool:
    if not all(t.is_cuda and t.is_contiguous() for t in ts):
        return False
    # 自定义 kernel 的产物不带 autograd 图：任何需要梯度的输入都必须回退到
    # torch 路径，否则训练梯度会被静默截断（实测 2026-11-08：SwiGLU/RoPE
    # 在 train() + backward 下参数 grad 变 None）。
    if torch.is_grad_enabled() and any(t.requires_grad for t in ts):
        return False
    return available()


def rmsnorm_or_none(x: torch.Tensor, weight: torch.Tensor,
                    eps: float = 1e-6) -> Optional[torch.Tensor]:
    if not _fastpath_ok(x, weight):
        return None
    try:
        return rmsnorm(x, weight, eps)
    except CudaKernelError:
        return None


def swiglu_or_none(gate: torch.Tensor, up: torch.Tensor) -> Optional[torch.Tensor]:
    if not _fastpath_ok(gate, up):
        return None
    try:
        return swiglu(gate, up)
    except CudaKernelError:
        return None


def rope1d_or_none(x: torch.Tensor, cos: torch.Tensor,
                   sin: torch.Tensor) -> Optional[torch.Tensor]:
    if not _fastpath_ok(x, cos, sin):
        return None
    try:
        return rope1d(x, cos, sin)
    except CudaKernelError:
        return None


def rope2d_or_none(x: torch.Tensor, cos_y: torch.Tensor, sin_y: torch.Tensor,
                   cos_x: torch.Tensor, sin_x: torch.Tensor) -> Optional[torch.Tensor]:
    if not _fastpath_ok(x, cos_y, sin_y, cos_x, sin_x):
        return None
    try:
        return rope2d(x, cos_y, sin_y, cos_x, sin_x)
    except CudaKernelError:
        return None
