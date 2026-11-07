#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_wm_modelfile.py — 从契约真源生成世界模型专用 ollama Modelfile
=================================================================
不重训、不改权重：用同一份 GGUF（virtu-v3-all90-q4_0）注册一个
system 契约不同的变体 virtu-wm-v3，使其行为从"工具调用器"切换为
"世界状态预测器"。

用法：
  python scripts/build_wm_modelfile.py                 # 只生成 Modelfile
  python scripts/build_wm_modelfile.py --create        # 生成并 ollama create
  python scripts/build_wm_modelfile.py --create --name virtu-wm-v3 --gguf <path>
"""
import os
import sys
import json
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import wm_contract as C

DEFAULT_GGUF = os.path.join(ROOT, "checkpoints", "virtu-v3-all90-q4_0.gguf")

# 与 v3 保持同一 TEMPLATE（纯 system/user/assistant 三段），避免引入模板差异
TEMPLATE = """{{ if .System }}system
{{ .System }}
{{ end }}{{ if .Prompt }}user
{{ .Prompt }}
{{ end }}assistant
{{ .Response }}"""


def render_modelfile(gguf: str, fewshot: bool = True, num_ctx: int = 4096,
                     mode: str = "router") -> str:
    if mode == "world":
        system = C.build_system(with_fewshot=fewshot)
    elif mode == "router":
        system = C.build_router_system(with_fewshot=fewshot)
    else:
        raise ValueError("mode must be 'router' or 'world'")
    if '"""' in system:
        raise ValueError("契约文本包含三引号，无法写入 Modelfile")
    lines = [
        f"FROM {gguf}",
        "",
        'TEMPLATE """' + TEMPLATE + '"""',
        "",
        'SYSTEM """' + system + '"""',
        "",
        f"PARAMETER num_ctx {num_ctx}",
        "PARAMETER temperature 0",
        "PARAMETER top_p 0.9",
        "PARAMETER repeat_penalty 1.05",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", default=DEFAULT_GGUF)
    ap.add_argument("--name", default="virtu")
    ap.add_argument("--out", default=os.path.join(ROOT, "checkpoints", "virtu-router.Modelfile"))
    ap.add_argument("--mode", choices=("router", "world"), default="router",
                    help="router=通用工业助手（默认）；world=仅世界模型契约")
    ap.add_argument("--no-fewshot", action="store_true")
    ap.add_argument("--create", action="store_true", help="生成后立即 ollama create")
    ap.add_argument("--check", action="store_true", help="只做契约自测（键名/枚举/invalid 规则齐全）")
    args = ap.parse_args()

    if args.check:
        sysm = C.build_router_system(True)
        sysw = C.build_system(True)
        miss = [f"{fam}:{k}" for fam, spec in C.KEY_SCHEMA.items()
                for k in spec["numeric"] if k not in sysm or k not in sysw]
        assert not miss, f"键名缺失: {miss}"
        assert "键名词表" in sysm and "invalid" in sysw and "reason" in sysw
        assert C.normalize_gate("fos_gate", "FOS>=1.5_pass") == "pass"
        print("[check] ALL PASS: 8 族键名/枚举/invalid 规则齐全，闸门归一一致")
        return 0

    # 坑：ollama create 对 Windows 相对路径（含反斜杠）解析不稳，会卡在
    # "gathering model components" 而不报错；统一归一为绝对路径。
    args.gguf = os.path.abspath(args.gguf)

    if not os.path.exists(args.gguf):
        print(f"[ERROR] GGUF 不存在: {args.gguf}")
        return 2

    text = render_modelfile(args.gguf, fewshot=not args.no_fewshot, mode=args.mode)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys_len = len(C.build_router_system(not args.no_fewshot) if args.mode == "router"
                  else C.build_system(not args.no_fewshot))
    print(f"[OK] Modelfile -> {args.out}  ({len(text)} bytes)")
    print(f"     mode={args.mode} SYSTEM {sys_len} chars, "
          f"fewshot={'on' if not args.no_fewshot else 'off'}")

    if not args.create:
        print(f"[HINT] 注册：ollama create {args.name} -f \"{args.out}\"")
        return 0

    print(f"[..] ollama create {args.name} ...")
    p = subprocess.run(["ollama", "create", args.name, "-f", args.out],
                       capture_output=True, text=True, timeout=600,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    print(out[-1500:] if out else "")
    if err:
        print("[stderr]", err[-800:])
    if p.returncode != 0:
        print(f"[FAIL] rc={p.returncode}")
        return p.returncode

    # 注册后验证：模型列表里必须出现
    tags = subprocess.run(["curl", "-s", "--max-time", "6",
                           "http://127.0.0.1:11434/api/tags"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout
    try:
        names = [m["name"] for m in json.loads(tags)["models"]]
    except Exception:
        names = []
    ok = any(n.startswith(args.name) for n in names)
    print(f"[{'OK' if ok else 'FAIL'}] 注册验证: {args.name} in ollama list = {ok}")
    print(f"     现有模型: {', '.join(names)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
