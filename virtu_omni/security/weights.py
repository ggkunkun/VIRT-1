"""安全权重反序列化入口（安全 / 凭据无关）。

统一 `torch.load` 的 `weights_only` 语义，供 smelt 权重包加载、训练断点续跑与
权重格式转换脚本共用，避免同一语义在多处各自实现。

设计约束：
- 默认 `weights_only=True`（只反序列化张量与基础容器），降低 pickle 反序列化风险。
- 仅在旧版 torch（< 2.0，不接受 `weights_only` 关键字）或调用方显式允许时，
  才回退到 `weights_only=False`，回退时发出 RuntimeWarning，不静默降级。
- `torch` 采用函数内局部导入，使本模块不引入额外的重量级模块级依赖。
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any, Union

__all__ = ["safe_torch_load", "_safe_torch_load"]

PathLike = Union[str, "os.PathLike[str]"]


def safe_torch_load(
    path: PathLike,
    map_location: Any = "cpu",
    *,
    weights_only: bool = True,
    allow_legacy_pickle_fallback: bool = True,
) -> Any:
    """按统一安全语义加载权重文件。

    Args:
        path: 权重文件路径。
        map_location: 传给 `torch.load` 的设备映射，默认 "cpu"。
        weights_only: 是否启用受限反序列化，默认 True。
        allow_legacy_pickle_fallback: 受限加载失败时是否回退到完整反序列化。
            仅应对本地可信权重包置为 True。

    Returns:
        `torch.load` 的返回对象（通常为 state_dict 或包含 state_dict 的字典）。

    Raises:
        FileNotFoundError: 路径不存在。
        IsADirectoryError: 路径是目录而非文件。
        RuntimeError: 受限加载失败且未允许回退，或回退后仍失败。
    """
    import torch  # 局部导入，保持本模块轻量

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Weights file not found: {target}")
    if target.is_dir():
        raise IsADirectoryError(f"Expected a weights file, got directory: {target}")

    try:
        return torch.load(target, map_location=map_location, weights_only=weights_only)
    except TypeError:
        # torch < 2.0 不支持 weights_only 关键字
        return torch.load(target, map_location=map_location)
    except Exception as exc:  # noqa: BLE001 - 需要按不同失败原因决定是否回退
        if not (weights_only and allow_legacy_pickle_fallback):
            raise RuntimeError(
                f"Failed to load weights from {target} with weights_only={weights_only}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        warnings.warn(
            f"weights_only=True load failed for {target} "
            f"({type(exc).__name__}: {exc}); falling back to weights_only=False. "
            "Only load trusted local checkpoints this way.",
            RuntimeWarning,
            stacklevel=2,
        )
        try:
            return torch.load(target, map_location=map_location, weights_only=False)
        except Exception as exc2:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to load weights from {target}: {type(exc2).__name__}: {exc2}"
            ) from exc2


# 历史调用点使用下划线前缀命名，保留别名以兼容既有调用
_safe_torch_load = safe_torch_load
