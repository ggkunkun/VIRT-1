"""Script to execute 10B parameter expansion from local weights."""

import os
import sys
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.config import ModelConfig
from virtu_omni.models.expander import BaseParameterExpander


def main() -> None:
    print("================================================================")
    print("  Virtu-Omni-10B: Parameter Expansion Execution Pipeline")
    print("================================================================")
    start_time = time.time()

    config = ModelConfig()
    output_path = os.path.join("checkpoints", "virtu_omni_10b_base.pt")

    expander = BaseParameterExpander(config=config)
    print(f"Target Parameter Scale: {config.param_scale}")
    print(f"Target Transformer Layers: {config.num_layers}")
    print(f"Target Hidden Dimension: {config.hidden_dim}")
    print(f"Target Intermediate Dim: {config.intermediate_dim}")

    saved_ckpt = expander.save_checkpoint(output_path)
    elapsed = time.time() - start_time

    print(f"[Done] Base parameter expansion completed in {elapsed:.2f}s.")
    print(f"[Done] Checkpoint available at: {saved_ckpt}")


if __name__ == "__main__":
    main()
