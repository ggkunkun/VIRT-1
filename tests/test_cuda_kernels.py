# -*- coding: utf-8 -*-
"""Counter-evidence tests for the runtime-compiled CUDA kernels.

Rules pinned here:
  1. every kernel must reproduce a float64 reference (no self-referential oracle);
  2. the equivalence gate must be falsifiable: a wrong binding (sin<->cos,
     up->gate) has to fail it;
  3. the domain kernels must agree with ``wm_verifier.recompute`` exactly where
     the two formulations coincide (tau=0, sy=0 -> sigma_vm=|sx|; collision
     verdicts mapped uint8 -> contract literals);
  4. the architecture fast path must stay numerically equivalent to the torch
     reference path it replaces, and must refuse CPU / non-contiguous input
     instead of silently copying or computing on the wrong device.
"""
from __future__ import annotations

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
import torch.nn.functional as F

from virtu_omni.config import ModelConfig
from virtu_omni.models import cuda_ops as K
from virtu_omni.models.architecture import UniRoPE, VirtuRMSNorm, VirtuSwiGLU

pytestmark = pytest.mark.skipif(
    not torch.cuda.is_available() or not K.available(),
    reason="needs CUDA + bundled NVRTC (sm_89 box)",
)

DEV = "cuda"
DT_TOL = {
    torch.float32: dict(rtol=3e-5, atol=3e-5),
    torch.float16: dict(rtol=4e-3, atol=4e-3),
    torch.bfloat16: dict(rtol=3e-2, atol=3e-2),
}


def _assert_close(got, ref, dt):
    assert torch.allclose(got.float(), ref.float(), **DT_TOL[dt]), (
        (got.float() - ref.float()).abs().max().item(), dt)


def test_capabilities_are_content_addressed():
    caps = K.capabilities()
    assert caps["available"] is True
    assert caps["capability"] == "8.9"
    assert caps["build"]["kind"] in ("cubin", "ptx")
    assert len(caps["source_sha256"]) == 64
    assert caps["source_sha256"] == K.kernel_source_sha256()


@pytest.mark.parametrize("dt", [torch.float32, torch.float16, torch.bfloat16])
def test_rmsnorm_matches_fp64(dt):
    rows, cols, eps = 37, 768, 1e-6
    x = torch.randn(rows, cols, device=DEV, dtype=dt)
    w = torch.randn(cols, device=DEV, dtype=dt)
    out = K.rmsnorm(x, w, eps)
    xd, wd = x.double().cpu(), w.double().cpu()
    ref = (xd * torch.rsqrt(xd.pow(2).mean(-1, keepdim=True) + eps)) * wd
    _assert_close(out.cpu(), ref, dt)


@pytest.mark.parametrize("dt", [torch.float32, torch.float16, torch.bfloat16])
def test_swiglu_matches_fp64(dt):
    g = torch.randn(1000003, device=DEV, dtype=dt)   # odd tail exercises the scalar branch
    u = torch.randn(1000003, device=DEV, dtype=dt)
    out = K.swiglu(g, u)
    gd, ud = g.double().cpu(), u.double().cpu()
    _assert_close(out.cpu(), gd * torch.sigmoid(gd) * ud, dt)


@pytest.mark.parametrize("dt", [torch.float32, torch.float16, torch.bfloat16])
def test_rope_matches_fp64(dt):
    B, S, H, D = 2, 16, 4, 64
    x = torch.randn(B, S, H, D, device=DEV, dtype=dt)
    ang = torch.randn(S, D // 2, device=DEV, dtype=dt)
    emb = torch.cat((ang, ang), dim=-1)
    cos, sin = emb.cos(), emb.sin()
    out = K.rope1d(x, cos, sin)
    xd = x.double().cpu()
    half = D // 2
    rot = torch.cat((-xd[..., half:], xd[..., :half]), dim=-1)
    ref = xd * cos.double().cpu().unsqueeze(0).unsqueeze(2) \
        + rot * sin.double().cpu().unsqueeze(0).unsqueeze(2)
    _assert_close(out.cpu(), ref, dt)


@pytest.mark.parametrize("dt", [torch.float32, torch.float16, torch.bfloat16])
def test_rope2d_matches_fp64(dt):
    B, gh, gw, H, D = 2, 5, 7, 3, 64
    N, half = gh * gw, D // 2
    x = torch.randn(B, N, H, D, device=DEV, dtype=dt)
    ang_y = torch.randn(N, half // 2, device=DEV, dtype=dt)
    ang_x = torch.randn(N, half // 2, device=DEV, dtype=dt)
    emb_y = torch.cat((ang_y, ang_y), dim=-1)
    emb_x = torch.cat((ang_x, ang_x), dim=-1)
    cy, sy = emb_y.cos(), emb_y.sin()
    cx, sx = emb_x.cos(), emb_x.sin()
    out = K.rope2d(x, cy, sy, cx, sx)
    xd = x.double().cpu()

    def _rot_axis(xs, c, s):
        q = xs.shape[-1] // 2
        rot = torch.cat((-xs[..., q:], xs[..., :q]), dim=-1)
        return xs * c + rot * s

    cy_d, sy_d = cy.double().cpu().unsqueeze(0).unsqueeze(2), sy.double().cpu().unsqueeze(0).unsqueeze(2)
    cx_d, sx_d = cx.double().cpu().unsqueeze(0).unsqueeze(2), sx.double().cpu().unsqueeze(0).unsqueeze(2)
    ref = torch.cat([_rot_axis(xd[..., :half], cy_d, sy_d),
                     _rot_axis(xd[..., half:], cx_d, sx_d)], dim=-1)
    _assert_close(out.cpu(), ref, dt)


def test_rope2d_axis_swap_is_caught():
    B, gh, gw, H, D = 1, 4, 6, 2, 64
    N, half = gh * gw, D // 2
    x = torch.randn(B, N, H, D, device=DEV)
    ang_y = torch.randn(N, half // 2, device=DEV)
    ang_x = torch.randn(N, half // 2, device=DEV)
    emb_y = torch.cat((ang_y, ang_y), dim=-1)
    emb_x = torch.cat((ang_x, ang_x), dim=-1)
    cy, sy, cx, sx = emb_y.cos(), emb_y.sin(), emb_x.cos(), emb_x.sin()
    good = K.rope2d(x, cy, sy, cx, sx)
    mutant = K.rope2d(x, cx, sx, cy, sy)          # x/y 轴表互换
    xd = x.double().cpu()
    half_ = D // 2

    # 直接以参考实现判 good 通过、mutant 必须红
    def _rot_axis(xs, c, s):
        q = xs.shape[-1] // 2
        return xs * c + torch.cat((-xs[..., q:], xs[..., :q]), dim=-1) * s

    ref = torch.cat([
        _rot_axis(xd[..., :half_], cy.double().cpu().unsqueeze(0).unsqueeze(2),
                  sy.double().cpu().unsqueeze(0).unsqueeze(2)),
        _rot_axis(xd[..., half_:], cx.double().cpu().unsqueeze(0).unsqueeze(2),
                  sx.double().cpu().unsqueeze(0).unsqueeze(2)),
    ], dim=-1)
    _assert_close(good.cpu(), ref, torch.float32)
    with pytest.raises(AssertionError):
        _assert_close(mutant.cpu(), ref, torch.float32)


class TestGateIsFalsifiable:
    """Wrong bindings must fail the same comparison the other tests pass."""

    def test_rope_sin_cos_swap_is_caught(self):
        B, S, H, D = 1, 8, 2, 64
        x = torch.randn(B, S, H, D, device=DEV)
        ang = torch.randn(S, D // 2, device=DEV)
        emb = torch.cat((ang, ang), dim=-1)
        cos, sin = emb.cos(), emb.sin()
        good = K.rope1d(x, cos, sin)
        mutant = K.rope1d(x, cos, cos)          # sin replaced by cos
        half = D // 2
        xd = x.double().cpu()
        rot = torch.cat((-xd[..., half:], xd[..., :half]), dim=-1)
        ref = xd * cos.double().cpu().unsqueeze(0).unsqueeze(2) \
            + rot * sin.double().cpu().unsqueeze(0).unsqueeze(2)
        _assert_close(good.cpu(), ref, torch.float32)
        with pytest.raises(AssertionError):
            _assert_close(mutant.cpu(), ref, torch.float32)

    def test_swiglu_wrong_gate_binding_is_caught(self):
        g = torch.randn(4096, device=DEV)
        u = torch.randn(4096, device=DEV)
        mutant = K.swiglu(g, g)                  # up replaced by gate
        gd, ud = g.double().cpu(), u.double().cpu()
        ref = gd * torch.sigmoid(gd) * ud
        with pytest.raises(AssertionError):
            _assert_close(mutant.cpu(), ref, torch.float32)


def test_fea_batch_matches_wm_verifier_on_the_shared_formulation():
    """tau=0, sy=0 makes sigma_vm=|sx|, so recompute(fea_fos) is directly comparable."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts"))
    import wm_verifier

    n = 257
    sx = torch.rand(n, device=DEV) * 180 + 20
    sy = torch.zeros(n, device=DEV)
    tau = torch.zeros(n, device=DEV)
    Sy = torch.rand(n, device=DEV) * 600 + 200
    svm, fos, gate = K.fea_batch(sx, sy, tau, Sy)
    for i in (0, 1, 128, n - 1):
        ref = wm_verifier.recompute(
            {"task": "fea_fos", "inputs": {"Sy": float(Sy[i]), "sigma": float(sx[i])}})
        assert svm[i].item() == pytest.approx(float(sx[i]), rel=1e-6)
        assert fos[i].item() == pytest.approx(ref["safety_factor"], rel=1e-5)
        assert bool(gate[i].item()) == (ref["fos_gate"] == "pass")


def test_collision_batch_matches_wm_verifier_verdicts():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts"))
    import wm_verifier

    n = 301
    zs = torch.rand(n, device=DEV) * 60 + 10
    zm = torch.rand(n, device=DEV) * 80 - 10
    zt = torch.rand(n, device=DEV) * 60
    risk, gouge, adiff = K.collision_batch(zs, zm, zt)
    diff_map = {0: "green", 1: "yellow", 2: "red"}
    for i in range(0, n, 37):
        ref = wm_verifier.recompute({"task": "collision", "inputs": {
            "z_safe": float(zs[i]), "z_min_rapid": float(zm[i]),
            "stock_top": float(zt[i])}})
        assert bool(risk[i].item()) == (ref["collision_risk"] == "high")
        assert bool(gouge[i].item()) is ref["gouge"]
        assert diff_map[int(adiff[i].item())] == ref["autodiff"]


class TestArchitectureFastPath:
    def _tiny_model(self):
        from virtu_omni.models.architecture import VirtuOmni10B
        torch.manual_seed(11)
        cfg = ModelConfig(num_layers=2, hidden_dim=128, intermediate_dim=384,
                          num_attention_heads=4, num_kv_heads=2, head_dim=32,
                          vocab_size=1000, max_position_embeddings=128)
        return VirtuOmni10B(cfg).to(DEV).eval()

    def test_full_model_forward_is_numerically_equivalent(self):
        model = self._tiny_model()
        ids = torch.randint(0, 1000, (2, 24), device=DEV)
        with torch.no_grad():
            on = model(ids)["logits"]
            orig = K.available
            try:
                K.available = lambda: False
                off = model(ids)["logits"]
            finally:
                K.available = orig
        diff = (on - off).abs().max().item()
        assert diff < 1e-3, diff
        assert K.available() is True   # 别把开关留错

    def test_full_model_actually_calls_the_custom_kernels(self):
        """Fast path must be *engaged* inside a real forward, not just compiled."""
        model = self._tiny_model()
        ids = torch.randint(0, 1000, (2, 24), device=DEV)
        calls = {"rms": 0, "swiglu": 0, "rope": 0}
        orig = (K.rmsnorm_or_none, K.swiglu_or_none, K.rope1d_or_none)

        def rms(*a, **k):
            out = orig[0](*a, **k)
            calls["rms"] += out is not None
            return out

        def swi(*a, **k):
            out = orig[1](*a, **k)
            calls["swiglu"] += out is not None
            return out

        def rope(*a, **k):
            out = orig[2](*a, **k)
            calls["rope"] += out is not None
            return out

        K.rmsnorm_or_none, K.swiglu_or_none, K.rope1d_or_none = rms, swi, rope
        try:
            with torch.no_grad():
                model(ids)
        finally:
            K.rmsnorm_or_none, K.swiglu_or_none, K.rope1d_or_none = orig
        assert calls["rms"] > 0 and calls["swiglu"] > 0 and calls["rope"] > 0, calls

    def test_rope2d_module_fast_path_equivalent_and_engaged(self):
        rope = UniRoPE(64, max_seq_len=512).to(DEV)
        q = torch.randn(2, 35, 3, 64, device=DEV)   # N = 5*7 视觉网格
        k = torch.randn(2, 35, 2, 64, device=DEV)
        calls = 0
        orig_fn = K.rope2d_or_none

        def counting(*a, **kw):
            nonlocal calls
            out = orig_fn(*a, **kw)
            calls += out is not None
            return out

        K.rope2d_or_none = counting
        try:
            with torch.no_grad():
                on_q, on_k = rope.apply_2d_rope(q, k, 5, 7)
                orig_avail = K.available
                K.available = lambda: False
                try:
                    off_q, off_k = rope.apply_2d_rope(q, k, 5, 7)
                finally:
                    K.available = orig_avail
        finally:
            K.rope2d_or_none = orig_fn
        assert calls == 2, f"2D fast path not engaged (calls={calls})"
        _assert_close(on_q.cpu(), off_q.double().cpu(), torch.float32)
        _assert_close(on_k.cpu(), off_k.double().cpu(), torch.float32)

    def test_virtu_rmsnorm_forward_matches_fp64(self):
        torch.manual_seed(3)
        norm = VirtuRMSNorm(768).to(DEV, torch.bfloat16).eval()
        x = torch.randn(4, 9, 768, device=DEV, dtype=torch.bfloat16)
        out = norm(x)
        xd, wd = x.double().cpu(), norm.weight.double().cpu()
        ref = (xd * torch.rsqrt(xd.pow(2).mean(-1, keepdim=True) + norm.eps)) * wd
        _assert_close(out.cpu(), ref, torch.bfloat16)

    def test_swiglu_module_matches_manual_reference(self):
        torch.manual_seed(4)
        cfg = ModelConfig(num_layers=2, hidden_dim=256, intermediate_dim=512,
                          vocab_size=1000)
        ffn = VirtuSwiGLU(cfg).to(DEV, torch.bfloat16).eval()
        x = torch.randn(3, 7, 256, device=DEV, dtype=torch.bfloat16)
        out = ffn(x)
        gd = F.linear(x.double().cpu(), ffn.gate_proj.weight.double().cpu())
        ud = F.linear(x.double().cpu(), ffn.up_proj.weight.double().cpu())
        ref = F.linear(gd * torch.sigmoid(gd) * ud,
                       ffn.down_proj.weight.double().cpu())
        _assert_close(out.cpu(), ref, torch.bfloat16)

    def test_rope_matches_uncached_reference_implementation(self):
        torch.manual_seed(5)
        rope = UniRoPE(64, max_seq_len=256).to(DEV, torch.bfloat16)
        q = torch.randn(2, 33, 4, 64, device=DEV, dtype=torch.bfloat16)
        k = torch.randn(2, 33, 2, 64, device=DEV, dtype=torch.bfloat16)
        pos = torch.arange(33, device=DEV)
        got_q, got_k = rope.apply_1d_rope(q, k, pos, contiguous_slice=(0, 33))
        ref_q, ref_k = rope._apply_1d_rope_unopt(q, k, pos)
        _assert_close(got_q.cpu(), ref_q.double().cpu(), torch.bfloat16)
        _assert_close(got_k.cpu(), ref_k.double().cpu(), torch.bfloat16)


class TestFailClosed:
    def test_cpu_input_refuses(self):
        x = torch.randn(4, 8)
        w = torch.randn(8)
        with pytest.raises(K.CudaKernelError):
            K.rmsnorm(x, w)

    def test_non_contiguous_refuses(self):
        x = torch.randn(8, 16, device=DEV).t()   # transposed view, non-contiguous
        w = torch.randn(8, device=DEV)
        with pytest.raises(K.CudaKernelError):
            K.rmsnorm(x, w)
        assert K.rmsnorm_or_none(x, w) is None    # 架构层显式回退

    def test_dtype_mismatch_refuses(self):
        g = torch.randn(64, device=DEV, dtype=torch.float32)
        u = torch.randn(64, device=DEV, dtype=torch.bfloat16)
        with pytest.raises(K.CudaKernelError):
            K.swiglu(g, u)
