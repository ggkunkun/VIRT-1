#!/usr/bin/env python3
"""Run bounded Virtu RSI experiments; all model updates still need human review."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_omni.rsi.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(root=ROOT))
