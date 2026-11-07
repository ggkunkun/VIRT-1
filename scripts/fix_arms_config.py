"""Repair and extend virtu_eval/arms.json.

Two jobs:

1. The stored paths were written through a lossy GBK round-trip, so
   ``D:/Virtu模型/`` became ``D:/Virtu妯″瀷/`` and every arm pointed at a
   path that does not exist.  Resolve them against the real repo root.
2. The deployed models that actually serve traffic are the Ollama GGUF
   exports.  They are 12x faster than the transformers path on this box and
   are what production talks to, so they need arms of their own.

Also: an arm must be able to say *which* model it really is.  A bridge arm
can silently proxy to a third-party cloud model, so arms carry a
``expect_identity`` block and the runner records what the server says it
served.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = os.path.join(ROOT, "virtu_eval", "arms.json")


def rel(*parts):
    return "/".join([ROOT.replace("\\", "/")] + [p.replace("\\", "/") for p in parts])


def main():
    with open(ARMS, encoding="utf-8") as f:
        arms = json.load(f)

    # --- 1. repair paths -------------------------------------------------
    fixed = []
    for key, spec in arms.items():
        for field in ("model_path", "adapter_path"):
            if field in spec and spec[field]:
                # keep only the tail after the last known-good prefix marker
                raw = spec[field]
                tail = raw.split("/checkpoints/", 1)[-1]
                if raw.rsplit("/", 1)[-1] != tail:
                    spec[field] = rel("checkpoints", tail)
                spec[field] = spec[field].replace("\\", "/")
                fixed.append((key, field, spec[field], os.path.exists(spec[field])))
        for field in ("base_url",):
            if field in spec and spec[field]:
                spec[field] = spec[field].strip()
        # the transformer path was measured at ~1.8 tok/s on this box
        if spec.get("kind") == "hf_local":
            spec.setdefault("max_tokens_cap", 256)
        spec.setdefault("note", "")

    # --- 2. add the Ollama deployment arms -------------------------------
    ollama_tools = None
    manifest_path = os.path.join(ROOT, "cadcam_toolchain_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            ollama_tools = json.load(f).get("tools")

    def ollama_arm(model, note, ident):
        spec = {
            "kind": "ollama_native",
            "base_url": "http://127.0.0.1:11434",
            "model_id": model,
            "num_ctx": 4096,
            "timeout": 600,
            "retries": 1,
            "note": note,
            "expect_identity": ident,
        }
        if ollama_tools:
            spec["tools"] = ollama_tools
            spec["tools_dimensions"] = ["toolcall"]
        return spec

    arms["ollama_qwen3_8b_base"] = ollama_arm(
        "qwen3:8b",
        "对照基座：官方 Qwen3-8B GGUF（与全部 LoRA 同一基底），用于算 LoRA 的净增益",
        {"family": "qwen3", "must_not_be": "virtu"},
    )
    arms["ollama_virtu_omni_v1"] = ollama_arm(
        "virtu-omni-8b:latest",
        "部署产物 v1：virtu-q4_0.gguf 导入（对话 LoRA 合并 + Q4_0）",
        {"family": "qwen3"},
    )
    arms["ollama_virtu_omni_v2"] = ollama_arm(
        "virtu-omni-8b:v2",
        "部署产物 v2：virtu-omni-v2-q4_0.gguf 导入",
        {"family": "qwen3"},
    )
    arms["ollama_virtu_toolcall"] = ollama_arm(
        "virtu-toolcall:latest",
        "部署产物：virtu-toolcall-q4_0.gguf 导入（工具调用 LoRA 合并）",
        {"family": "qwen3"},
    )
    arms["ollama_virtu_production_v3"] = ollama_arm(
        "virtu-production:v3",
        "部署产物：virtu-production-v3-q4_0.gguf 导入（4-LoRA delta，Σw=1.0；旧 peft_linear 坏件已隔离）",
        {"family": "qwen3"},
    )

    with open(ARMS, "w", encoding="utf-8") as f:
        json.dump(arms, f, ensure_ascii=False, indent=2)

    print("arms:")
    for key, spec in arms.items():
        p = spec.get("model_path") or spec.get("base_url")
        ok = ""
        if spec.get("kind") == "hf_local":
            ok = "OK" if os.path.exists(spec["model_path"]) else "MISSING"
            if spec.get("adapter_path"):
                ok += "/" + ("OK" if os.path.exists(spec["adapter_path"]) else "MISSING")
        print(f"  {key:28s} {spec['kind']:14s} {p}  {ok}")
    print("\npath repairs:")
    for k, f_, p, e in fixed:
        print(f"  {k}.{f_} -> {p}  exists={e}")


if __name__ == "__main__":
    main()
