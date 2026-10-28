"""LoRA Model Wrapper and Parameter-Efficient Adapter Manager."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json
import os
from typing import Dict, List, Any, Optional
import torch
import torch.nn as nn

from virtu_edge.qlora.linear_4bit import Linear4bitLoRA


@dataclass
class LoRAConfig:
    """Configuration for Low-Rank Adaptation (LoRA / QLoRA)."""
    r: int = 8
    lora_alpha: float = 16.0
    lora_dropout: float = 0.05
    target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "out_proj", "linear", "mlp"])
    block_size: int = 64


class LoRAModel(nn.Module):
    """Wraps any base PyTorch model to inject 4-bit quantized LoRA adapters."""

    def __init__(self, base_model: nn.Module, config: Optional[LoRAConfig] = None) -> None:
        super().__init__()
        self.base_model = base_model
        self.config = config or LoRAConfig()
        self._injected_modules: Dict[str, Linear4bitLoRA] = {}

        self._freeze_base_model()
        self._inject_lora_layers()

    def _freeze_base_model(self) -> None:
        """Freeze all parameters in the base model."""
        for param in self.base_model.parameters():
            param.requires_grad = False

    def _inject_lora_layers(self) -> None:
        """Scan base model and replace target Linear layers with Linear4bitLoRA."""
        for name, module in list(self.base_model.named_modules()):
            if isinstance(module, nn.Linear):
                matches = any(t in name for t in self.config.target_modules)
                if matches:
                    self._replace_module(name, module)

    def _replace_module(self, full_name: str, linear_layer: nn.Linear) -> None:
        """Helper to replace a specific Linear module in the module tree."""
        parts = full_name.split(".")
        parent = self.base_model
        for part in parts[:-1]:
            parent = getattr(parent, part)
        attr_name = parts[-1]

        lora_layer = Linear4bitLoRA.from_linear(
            linear=linear_layer,
            r=self.config.r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            block_size=self.config.block_size,
        )
        setattr(parent, attr_name, lora_layer)
        self._injected_modules[full_name] = lora_layer

    def get_trainable_parameters(self) -> Dict[str, Any]:
        """Count trainable vs total parameters."""
        trainable = 0
        total = 0
        for p in self.parameters():
            total += p.numel()
            if p.requires_grad:
                trainable += p.numel()

        return {
            "trainable_params": trainable,
            "total_params": total,
            "trainable_percent": round(100.0 * trainable / max(1, total), 4),
            "injected_layers": len(self._injected_modules),
        }

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        """Forward pass delegated to the underlying base model."""
        return self.base_model(*args, **kwargs)

    def save_pretrained(self, save_directory: str) -> str:
        """Save adapter weights and configuration."""
        os.makedirs(save_directory, exist_ok=True)
        adapter_state: Dict[str, torch.Tensor] = {}

        for name, module in self._injected_modules.items():
            if module.lora_A is not None and module.lora_B is not None:
                adapter_state[f"{name}.lora_A"] = module.lora_A.data.cpu()
                adapter_state[f"{name}.lora_B"] = module.lora_B.data.cpu()

        weight_path = os.path.join(save_directory, "adapter_model.pt")
        torch.save(adapter_state, weight_path)

        cfg_path = os.path.join(save_directory, "adapter_config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

        return save_directory

    def load_adapter(self, save_directory: str) -> None:
        """Load adapter weights from directory."""
        weight_path = os.path.join(save_directory, "adapter_model.pt")
        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"Adapter weight not found at {weight_path}")

        adapter_state = torch.load(weight_path, weights_only=True)
        for name, module in self._injected_modules.items():
            key_a = f"{name}.lora_A"
            key_b = f"{name}.lora_B"
            if key_a in adapter_state and key_b in adapter_state:
                module.lora_A.data.copy_(adapter_state[key_a].to(module.lora_A.device))
                module.lora_B.data.copy_(adapter_state[key_b].to(module.lora_B.device))

    def merge_and_unload(self) -> nn.Module:
        """Merge all LoRA adapters into base weights and return the standalone model."""
        for module in self._injected_modules.values():
            module.merge_weights()
        return self.base_model
