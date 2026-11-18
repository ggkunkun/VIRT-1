"""Virtu-Omni 集中配置（环境变量优先），P2 工程化的渐进式迁移入口。

本模块把散落的硬编码 ``WORKSPACE_ROOT`` / ``OLLAMA_URL`` / 各服务端口 / 常用阈值
收拢到一处，并让 **环境变量优先**（未设置时回落到仓库默认值）。
但本模块 **不**一次性替换仓库里 576 处硬编码 ``D:\\Virtu模型`` 与 417 处硬编码
端口：``virtu_omni/config.py`` 仍完全独立、可单独工作（本模块不 import、不修改它），
调用方可按下面示例逐个迁移，互不影响。

迁移示例（把某处硬编码替换为 settings 读取）::

    # ---- 旧（散落硬编码）----
    #   ROOT   = r"D:\\Virtu模型"
    #   OLLAMA = "http://127.0.0.1:11434"
    #   resp   = requests.post("http://localhost:8000/v1/completions", json=payload)
    #   port   = 8080
    #
    # ---- 新（集中配置，可被环境变量覆盖）----
    from virtu_omni.settings import get_settings
    _s = get_settings()
    ROOT   = _s.workspace_root                 # 等价旧常量，可被 VIRTU_WORKSPACE_ROOT 覆盖
    OLLAMA = _s.ollama_url                     # 等价旧 URL
    resp   = requests.post(_s.bridge_url + "/v1/completions", json=payload)
    port   = _s.serving_port                   # 取代 config.ServingConfig.port 的硬编码值

    # 阈值同理：
    #   安全系数 FOS >= 1.5        -> get_settings().safety_factor_min
    #   首包时延 <= 200ms          -> get_settings().target_latency_ms
    #   GPU 温度上限 85.0          -> get_settings().gpu_temp_max_celsius

环境变量优先级：``get_settings()`` 每次按当前 ``os.environ`` 构造一份快照，
未设置（或值非法）的键回落到下列默认值。设置 ``VIRTU_*`` / ``OLLAMA_HOST`` 等即可
覆盖，无需改代码、无需改动 config.py。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

__all__ = ["Settings", "get_settings"]

# 默认工作区根：本文件位于 <root>/virtu_omni/settings.py，故 parent.parent 即仓库根。
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _resolve_ollama():
    """返回 ``(host, port, url)``，兼容 OLLAMA_HOST 的三种常见写法。

    ``OLLAMA_HOST`` 可能是 ``127.0.0.1``（裸主机）、``127.0.0.1:11434``
    （主机:端口）或 ``http://127.0.0.1:11434``（完整 URL）；若直接设置了
    ``VIRTU_OLLAMA_URL``，则它作为最终 URL 优先。
    """
    explicit = os.getenv("VIRTU_OLLAMA_URL")
    raw = os.getenv("OLLAMA_HOST") or os.getenv("VIRTU_OLLAMA_HOST") or "127.0.0.1"
    port = _env_int("OLLAMA_PORT", _env_int("VIRTU_OLLAMA_PORT", 11434))
    base = None
    host = raw
    if "://" in raw:
        base = raw.rstrip("/")
        host = raw.split("://", 1)[1].split("/", 1)[0]
    if ":" in host:
        h, p = host.rsplit(":", 1)
        try:
            port = int(p)
            host = h
        except ValueError:
            pass
    url = explicit or base or f"http://{host}:{port}"
    return host, port, url


@dataclass(frozen=True)
class Settings:
    """一次配置快照。字段默认值即仓库当前口径，环境变量可逐项覆盖。"""

    # --- 路径与地址 ---
    workspace_root: Path = _DEFAULT_ROOT

    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    ollama_url: str = "http://127.0.0.1:11434"

    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8000

    # 与 virtu_omni/config.py::ServingConfig 对齐（host 为绑定地址 0.0.0.0，port 8080）
    serving_host: str = "0.0.0.0"
    serving_port: int = 8080

    # 其余常见服务端口（集中登记，避免再散落硬编码）
    service_ports: Dict[str, int] = field(default_factory=lambda: {
        "ollama": 11434,
        "bridge": 8000,
        "serving": 8080,
        "agent_bus": 8766,
        "context_gateway": 8192,
        "postgres": 5432,
        "redis": 6379,
        "https_alt": 8443,
        "tool_proxy": 8988,
    })

    # --- 常用阈值（与 config.py 的训练/监控/服务默认值一致）---
    safety_factor_min: float = 1.5              # FOS >= 1.5
    target_latency_ms: float = 200.0            # 单卡首包时延 <= 200ms
    gpu_temp_max_celsius: float = 85.0
    gpu_memory_threshold_percent: float = 98.5
    loss_spike_sigma_threshold: float = 3.0
    grad_norm_hard_threshold: float = 5.0
    max_concurrency: int = 64

    @property
    def bridge_url(self) -> str:
        """可连接（非绑定）的桥接服务基地址。"""
        return f"http://{self.bridge_host}:{self.bridge_port}"

    @property
    def serving_url(self) -> str:
        """可连接（非绑定）的推理服务基地址；绑定地址 0.0.0.0 改写为 127.0.0.1。"""
        host = "127.0.0.1" if self.serving_host in ("0.0.0.0", "") else self.serving_host
        return f"http://{host}:{self.serving_port}"

    @property
    def memory_dir(self) -> Path:
        return self.workspace_root / "data" / "memory"


def get_settings() -> Settings:
    """按当前环境变量构造一份配置快照（环境变量优先，缺失回落默认值）。"""
    ollama_host, ollama_port, ollama_url = _resolve_ollama()

    root = Path(_env_str("VIRTU_WORKSPACE_ROOT", str(_DEFAULT_ROOT)))

    return Settings(
        workspace_root=root,
        ollama_host=ollama_host,
        ollama_port=ollama_port,
        ollama_url=ollama_url,
        bridge_host=_env_str("VIRTU_BRIDGE_HOST", "127.0.0.1"),
        bridge_port=_env_int("VIRTU_BRIDGE_PORT", 8000),
        serving_host=_env_str("VIRTU_SERVING_HOST", "0.0.0.0"),
        serving_port=_env_int("VIRTU_SERVING_PORT", 8080),
        service_ports={
            "ollama": ollama_port,
            "bridge": _env_int("VIRTU_BRIDGE_PORT", 8000),
            "serving": _env_int("VIRTU_SERVING_PORT", 8080),
            "agent_bus": _env_int("VIRTU_AGENT_BUS_PORT", 8766),
            "context_gateway": _env_int("VIRTU_CONTEXT_GATEWAY_PORT", 8192),
            "postgres": _env_int("VIRTU_POSTGRES_PORT", 5432),
            "redis": _env_int("VIRTU_REDIS_PORT", 6379),
            "https_alt": _env_int("VIRTU_HTTPS_ALT_PORT", 8443),
            "tool_proxy": _env_int("VIRTU_TOOL_PROXY_PORT", 8988),
        },
        safety_factor_min=_env_float("VIRTU_SAFETY_FACTOR_MIN", 1.5),
        target_latency_ms=_env_float("VIRTU_TARGET_LATENCY_MS", 200.0),
        gpu_temp_max_celsius=_env_float("VIRTU_GPU_TEMP_MAX_CELSIUS", 85.0),
        gpu_memory_threshold_percent=_env_float("VIRTU_GPU_MEMORY_THRESHOLD_PERCENT", 98.5),
        loss_spike_sigma_threshold=_env_float("VIRTU_LOSS_SPIKE_SIGMA_THRESHOLD", 3.0),
        grad_norm_hard_threshold=_env_float("VIRTU_GRAD_NORM_HARD_THRESHOLD", 5.0),
        max_concurrency=_env_int("VIRTU_MAX_CONCURRENCY", 64),
    )
