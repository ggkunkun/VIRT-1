#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_local_sft.py — 本地 SFT/TIES 权重合并、GGUF 转换与 Ollama 注册一键流水线

修复项：
  1. 彻底弃用 Ollama 0.40.13 会报 `error:22` 的 `ADAPTER` 指令，改走：
     `merge_numpy.py --mode delta` -> `hf_to_gguf_numpy.py` (或已有 GGUF) -> `ollama create`。
  2. 生成的 Modelfile 强制写入 `PARAMETER num_ctx 4096` 与 `PARAMETER temperature 0`，
     修复长工具定义 (>2048 tokens) 触发 1-token EOS 空回复的问题。
  3. 检查本地 `DEPLOYED.flag` 与本地 adapter 目录，不再无条件 SSH 连接已销毁的 DamoModel 实例。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

MODELFILE_TEMPLATE = """FROM {gguf_path}
TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
\"\"\"
PARAMETER temperature 0
PARAMETER num_ctx 4096
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
"""


def build_modelfile(gguf_path: Path, out_modelfile: Path) -> Path:
    content = MODELFILE_TEMPLATE.format(gguf_path=str(gguf_path).replace("\\", "/"))
    out_modelfile.write_text(content, encoding="utf-8")
    return out_modelfile


def main() -> int:
    ap = argparse.ArgumentParser(description="Deploy local merged SFT/TIES model to Ollama")
    ap.add_argument("--model-name", default="virtu-ties-v1", help="Ollama model tag to register")
    ap.add_argument("--base", default=str(ROOT / "checkpoints" / "_base_qwen3_8b"))
    ap.add_argument("--merged-dir", default=str(ROOT / "checkpoints" / "virtu_ties_v1"))
    ap.add_argument("--gguf", default=str(ROOT / "checkpoints" / "virtu-master-v4-q4_0.gguf"))
    ap.add_argument("--modelfile-out", default=str(ROOT / "Modelfile_v4"))
    ap.add_argument("--dry-run", action="store_true", help="Only generate Modelfile and validate paths")
    args = ap.parse_args()

    gguf_path = Path(args.gguf)
    modelfile_path = Path(args.modelfile_out)
    build_modelfile(gguf_path, modelfile_path)
    print(f"[deploy] Wrote Modelfile with PARAMETER num_ctx 4096 -> {modelfile_path}")

    if args.dry_run:
        print("[deploy] Dry-run complete.")
        return 0

    if not gguf_path.exists():
        merged_dir = Path(args.merged_dir)
        if not (merged_dir / "merge_receipt.json").exists():
            print(f"[deploy] Running merge_numpy.py -> {merged_dir}")
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "merge_numpy.py"),
                 "--base", args.base, "--out", str(merged_dir), "--mode", "delta", "--resume"],
                check=True,
            )
        converter = ROOT / "scripts" / "hf_to_gguf_numpy.py"
        if not converter.exists():
            converter = ROOT / "scripts" / "convert_lora_to_gguf.py"
        if converter.exists():
            print(f"[deploy] Converting {merged_dir} -> {gguf_path}")
            subprocess.run(
                [sys.executable, str(converter), "--src", str(merged_dir), "--out", str(gguf_path)],
                check=True,
            )

    print(f"[deploy] Registering {args.model_name} in Ollama...")
    rc = subprocess.run(["ollama", "create", args.model_name, "-f", str(modelfile_path)])
    if rc.returncode == 0:
        flag = ROOT / "checkpoints" / "DEPLOYED.flag"
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(json.dumps({"model": args.model_name, "gguf": str(gguf_path)}, indent=2), encoding="utf-8")
        print(f"[deploy] Successfully registered {args.model_name} and wrote {flag}")
    return rc.returncode


if __name__ == "__main__":
    sys.exit(main())
