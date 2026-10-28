"""
ckpt 读回门（对应 WPT2_NATIVE_SMELT.md §5.7）

- 用 .venv-train（带 CUDA torch）
- 不起 waitgpu、不训练、不重建数据
- 唯一目的：torch.load(ckpt.pt) 一次 + 核对总参数 = params.json["total"]

退出码：
  0 = 读回成功，参数核对一致
  非 0 = 读回失败（截断 zip / 字段缺失 / 数量不符）
"""
from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path

import torch

CKPT = Path(r"D:\智能制造Agent\Virtu\out\wpt2_mfg_main\ckpt.pt")
PARAMS = Path(r"D:\智能制造Agent\Virtu\out\wpt2_mfg_main\params.json")
EVAL = Path(r"D:\智能制造Agent\Virtu\out\wpt2_mfg_main\eval_results.json")


def count_params(state: dict) -> int:
    total = 0
    for k, v in state.items():
        if isinstance(v, torch.Tensor):
            total += v.numel()
    return total


def main() -> int:
    print(f"[i] ckpt    = {CKPT}  size={CKPT.stat().st_size} bytes")
    print(f"[i] params  = {PARAMS}")
    print(f"[i] eval    = {EVAL}")

    try:
        expected_total = json.loads(PARAMS.read_text(encoding="utf-8"))["total"]
        print(f"[i] params.total (expected) = {expected_total:,}")
    except Exception as e:
        print(f"[FAIL] params.json 读不到: {e}", file=sys.stderr)
        return 2

    # 关键门：torch.load 真读一次（§5.7）
    try:
        state = torch.load(CKPT, map_location="cpu", weights_only=False)
    except Exception as e:
        print(f"[FAIL] torch.load 抛出: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return 3

    if not isinstance(state, dict):
        print(f"[FAIL] ckpt 顶层不是 dict, 实际类型={type(state).__name__}", file=sys.stderr)
        return 4

    n_tensors = sum(1 for v in state.values() if isinstance(v, torch.Tensor))
    n_other = len(state) - n_tensors
    print(f"[i] ckpt 顶层键 = {len(state)} 个  ({n_tensors} 张量 / {n_other} 非张量)")
    # 找 state_dict：可能直接在顶层，也可能装在 'model' 键里（promote 格式）
    sd: dict
    if n_tensors > 0:
        sd = state
        where = "top-level"
    elif isinstance(state.get("model"), dict):
        sd = state["model"]
        where = "state['model']"
        n_tensors = sum(1 for v in sd.values() if isinstance(v, torch.Tensor))
        print(f"[i] state_dict 装在 {where!r}, 含 {n_tensors} 张量")
    else:
        print(f"[FAIL] 既不是 state_dict 也不是 promote 格式", file=sys.stderr)
        return 6
    total = count_params(sd)
    print(f"[i] 数到参数   = {total:,}  (来源={where})")
    if total != expected_total:
        print(f"[FAIL] 参数数 {total:,} 与 params.json 的 {expected_total:,} 不一致", file=sys.stderr)
        return 5
    print(f"[OK] 参数数 {total:,} == params.json['total']")
    # 额外核对：ckpt 自带的 total_params / trainable_params
    if state.get("total_params") == expected_total:
        print(f"[OK] ckpt['total_params']      = {state['total_params']:,}  (== expected)")
    if state.get("trainable_params") is not None:
        print(f"[i]  ckpt['trainable_params']  = {state['trainable_params']:,}")

    # 附：eval_results.json 关键 3 个数
    try:
        ev = json.loads(EVAL.read_text(encoding="utf-8"))
        print(f"[i] eval_results.json:")
        for k in ("subsystem_top1_acc", "pair_verifier_acc", "lm_token_acc",
                 "lm_perplexity", "gate_c_satisfied"):
            print(f"     {k} = {ev.get(k)}")
    except Exception as e:
        print(f"[WARN] eval_results.json 读不到: {e}")

    print("[OK] 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
