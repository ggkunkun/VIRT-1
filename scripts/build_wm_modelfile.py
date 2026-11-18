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

# 训练编码（train_turnkey*.py）逐字拼 ChatML，serving 模板必须同源，
# 否则模型在推理时看到的格式与训练分布不一致（旧纯文本三段模板是格式错配缺陷）。
TEMPLATE = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}"""


def render_modelfile(gguf: str, fewshot: bool = True, num_ctx: int = 8192,
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
        "PARAMETER repeat_penalty 1.15",
        "",
    ]
    return "\n".join(lines)


def resolve_from_tag(tag: str) -> str | None:
    """从已注册的 ollama 模型反查其 FROM 权重（blob 或本地 gguf 路径）。

    存在的意义：DEFAULT_GGUF 指向的权重曾从磁盘上消失（只留在 ollama
    blob 里），导致源码级重建路径整条断掉。有了这个后门，只要现网模型
    还在，就永远能从它身上把权重找回来再重建，不必靠记忆或猜测。
    """
    try:
        p = subprocess.run(["ollama", "show", "--modelfile", tag],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except Exception as e:  # ollama 不存在 / 超时
        print(f"[WARN] 无法执行 ollama show: {e}")
        return None
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if line.upper().startswith("FROM "):
            cand = line[5:].strip()
            # blob 形式为 sha256-xxx，ollama 自己也存成绝对路径时原样返回
            if os.path.exists(cand):
                return cand
            print(f"[WARN] {tag} 的 FROM 指向的文件不在磁盘上: {cand}")
            return None
    print(f"[WARN] 未能从 {tag} 的 Modelfile 中解析出 FROM 行")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", default=None,
                    help=f"权重路径；缺省为 {DEFAULT_GGUF}")
    ap.add_argument("--from-tag", default=None,
                    help="从已注册的 ollama 模型反查权重（DEFAULT_GGUF 缺失时的逃生口）")
    ap.add_argument("--name", default="virtu")
    ap.add_argument("--out", default=os.path.join(ROOT, "checkpoints", "virtu-router.Modelfile"))
    ap.add_argument("--mode", choices=("router", "world"), default="router",
                    help="router=通用工业助手（默认）；world=仅世界模型契约")
    ap.add_argument("--no-fewshot", action="store_true")
    ap.add_argument("--create", action="store_true", help="生成后立即 ollama create")
    ap.add_argument("--check", action="store_true", help="只做契约自测（键名/枚举/invalid 规则齐全）")
    args = ap.parse_args()

    if args.check:
        import wm_schema as S
        sysm = C.build_router_system(True)
        sysw = C.build_system(True)
        # 旧口径只扫 numeric，且打印「8 族」：契约早已扩到 12 族，texts/bools/
        # gates/nested 的漂移在 --check 下完全查不出来，形成「闸门空转」。
        miss = [f"{fam}:{k}" for fam in C.KEY_SCHEMA
                for k in C.schema_keys(fam) if k not in sysm or k not in sysw]
        assert not miss, f"键名缺失: {miss}"
        assert "键名词表" in sysm and "invalid" in sysw and "reason" in sysw
        assert C.normalize_gate("fos_gate", "FOS>=1.5_pass") == "pass"
        no_card = [f for f in C.KEY_SCHEMA if f != "invalid" and not S.FAMILY_CARD.get(f)]
        assert not no_card, f"定律卡缺族: {no_card}"
        cross = [f for f in C.KEY_SCHEMA
                 if set(C.schema_keys(f)) != set(S.FAMILY_FIELDS.get(f, []))]
        assert not cross, f"契约/解码 schema 不同源: {cross}"
        print(f"[check] ALL PASS: {len(C.KEY_SCHEMA)} 族数值/闸门/文本/布尔键名、"
              "枚举、定律卡与 invalid 规则齐全，契约↔解码同源，闸门归一一致")
        return 0

    # 权重来源优先级：显式 --gguf > --from-tag 反查 > DEFAULT_GGUF。
    # 不做「默认路径缺失就静默换别的权重」——权重一换，Modelfile 的 FROM 就
    # 指向了另一个模型，产物和现网对不上却看不出来。宁可报错，也不猜。
    if args.gguf is None:
        if args.from_tag:
            args.gguf = resolve_from_tag(args.from_tag)
            if not args.gguf:
                print(f"[ERROR] --from-tag {args.from_tag} 未能反查到可用权重")
                return 2
            print(f"[OK] 权重来自 {args.from_tag} 的 FROM: {args.gguf}")
            if ".ollama" in args.gguf.replace("\\", "/") and "blobs" in args.gguf:
                # blob 是不可移植路径：产物换台机器/清空 ollama 就失效。
                print("[WARN] 权重来自 ollama blob，产出的 Modelfile 跨机不可移植；"
                      "建议先把该文件复制回 checkpoints/ 再用 --gguf 重建，产物才可入库。")
        else:
            args.gguf = DEFAULT_GGUF

    # 坑：ollama create 对 Windows 相对路径（含反斜杠）解析不稳，会卡在
    # "gathering model components" 而不报错；统一归一为绝对路径。
    # 再用正斜杠：Modelfile 的 FROM 行里 `C:\path\to.gguf` 会被当成转义/被
    # 解析器截断，且生成物落到别的机器就完全不可用。落盘的 Modelfile 因此
    # 用 POSIX 风格绝对路径，不再出现反斜杠。
    args.gguf = os.path.abspath(args.gguf).replace(os.sep, "/")

    if not os.path.exists(args.gguf):
        print(f"[ERROR] GGUF 不存在: {args.gguf}")
        # 源码级重建不该因为一份权重文件丢失就彻底断掉，给出可直接复制的出路
        print(f"[HINT] 若该模型仍在 ollama 中，用 --from-tag 反查权重：")
        print(f"       python scripts/build_wm_modelfile.py --mode world "
              f"--name virtu-wm-v3 --from-tag virtu-wm-v3:latest")
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
