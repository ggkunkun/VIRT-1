#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deploy_tool_lora_to_ollama.py — GPU 机回传 LoRA 后，本机一键完成全部落地工作

【为什么需要这个脚本】
本机（RTX4050 6GB / 内存 16.9GB）跑不了 8B QLoRA 训练，但能跑纯 numpy 的
流式合并与 GGUF 转换（峰值内存 <1GB）。所以分工是：
    GPU 机：只训练，产出 LoRA adapter（~350MB）
    本机  ：合并 → 量化 → 导入 Ollama → 端到端验证 → 切换模型
整个后半程一条命令跑完，任何一步失败都能回滚到原 virtu-omni-8b。

用法：
  python scripts/deploy_tool_lora_to_ollama.py \
      --lora checkpoints/virtu_toolcall_lora --ollama-name virtu-omni-8b-v2

  # 只验证不切换（推荐先跑这个）
  python scripts/deploy_tool_lora_to_ollama.py --lora checkpoints/xxx --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLLAMA = "http://127.0.0.1:11434"


def log(step, msg):
    print(f"[{step}] {msg}", flush=True)


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ollama_available():
    try:
        with _opener().open(OLLAMA + "/api/version", timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def ollama_list():
    with _opener().open(OLLAMA + "/api/tags", timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
    return {m["name"]: m.get("size", 0) for m in d.get("models", [])}


def run(cmd, **kw):
    print("   $", " ".join(str(c) for c in cmd)[:180], flush=True)
    p = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace",
                       capture_output=True, **kw)
    if p.stdout:
        print(p.stdout[-3000:])
    if p.returncode != 0:
        print(p.stderr[-2500:], file=sys.stderr)
        raise SystemExit(f"[FATAL] 命令失败 rc={p.returncode}")
    return p


def stage_merge(args):
    log("1/5", "合并 LoRA → HF 目录（纯 numpy 流式，峰值内存 <1GB）")
    out = os.path.abspath(args.merged_dir)
    cmd = [sys.executable, os.path.join(HERE, "merge_numpy.py"),
           "--base", args.base,
           "--out", out,
           "--mode", args.mode]
    if args.append_default:
        cmd += ["--append-lora", "--lora", args.lora, "--weight", str(args.weight)]
    else:
        cmd += ["--lora", args.lora, "--weight", str(args.weight)]
    cmd += ["--verify-samples", str(args.verify_samples)]
    if args.resume:
        cmd += ["--resume"]
    run(cmd, cwd=ROOT)
    log("1/5", f"合并完成 -> {out}")
    return out


def stage_gguf(args, merged_dir):
    log("2/5", "转换 GGUF Q4_0（纯 numpy）")
    out = os.path.abspath(args.gguf)
    run([sys.executable, os.path.join(HERE, "hf_to_gguf_numpy.py"),
         "--model", merged_dir, "--out", out], cwd=ROOT)
    size = os.path.getsize(out) / 1e9
    log("2/5", f"GGUF 完成 -> {out} ({size:.2f}GB)")
    return out


def stage_import(args, gguf_path):
    log("3/5", f"导入 Ollama: {args.ollama_name}")
    mf = os.path.join(args.work, "Modelfile.deploy")
    os.makedirs(args.work, exist_ok=True)
    # FROM 必须是绝对路径：相对路径会被 Ollama 当成 registry 模型名去远程拉取
    gguf_abs = os.path.abspath(gguf_path).replace("\\", "/")
    with open(mf, "w", encoding="utf-8") as f:
        f.write(f"FROM {gguf_abs}\n")
        f.write("PARAMETER num_ctx 4096\n")
        f.write("PARAMETER temperature 0.3\n")
        f.write("PARAMETER top_p 0.9\n")
    log("3/5", f"Modelfile: FROM {gguf_abs}")
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
              "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    # 覆盖式导入（模型不存在是正常情况，忽略 rm 的失败）
    rm = subprocess.run(["ollama", "rm", args.ollama_name], env=env, text=True,
                        capture_output=True, encoding="utf-8", errors="replace")
    if rm.returncode != 0:
        log("3/5", f"（原有同名模型不存在或已移除，继续创建）")
    run(["ollama", "create", args.ollama_name, "-f", mf], env=env)
    models = ollama_list()
    size = models.get(args.ollama_name, 0) / 1e9
    log("3/5", f"导入完成，模型库占用 {size:.2f}GB")
    return args.ollama_name


def stage_verify(args):
    log("4/5", "端到端验证：普通对话 + 工具调用")
    results = {}

    # 4a 普通对话
    payload = json.dumps({
        "model": args.ollama_name,
        "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
        "stream": False, "think": False,
        "options": {"num_predict": 80, "temperature": 0.1},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    with _opener().open(req, timeout=240) as r:
        d = json.loads(r.read().decode("utf-8"))
    content = d.get("message", {}).get("content", "")
    results["chat_ok"] = bool(content)
    results["chat_preview"] = content[:200]
    log("4/5", f"  对话: {content[:120]!r}")

    # 4b 工具调用
    tools = [{
        "type": "function",
        "function": {
            "name": "cad.parse_wish_intent",
            "description": "将自然语言制造意图解析为结构化参数化 spec",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {"type": "string"},
                    "material": {"type": "string"},
                    "d_outer": {"type": "number"},
                    "d_inner": {"type": "number"},
                },
                "required": ["wish", "material", "d_outer", "d_inner"],
            },
        },
    }]
    payload = json.dumps({
        "model": args.ollama_name,
        "messages": [{"role": "user",
                      "content": "用SOLIDWORKS生成一个外径110mm、内孔30mm、总长30mm的SS304套筒。"}],
        "tools": tools,
        "stream": False, "think": False,
        "options": {"num_predict": 240, "temperature": 0.1},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with _opener().open(req, timeout=300) as r:
            d = json.loads(r.read().decode("utf-8"))
        m = d.get("message", {})
        tc = m.get("tool_calls")
        results["tool_calls"] = tc
        results["tool_call_count"] = len(tc) if tc else 0
        results["tool_content_preview"] = (m.get("content") or "")[:300]
        if tc:
            fn = tc[0].get("function", {})
            log("4/5", f"  工具调用 ✓ name={fn.get('name')} "
                       f"args={str(fn.get('arguments'))[:150]}")
        else:
            log("4/5", f"  工具调用 ✗ 未返回结构化 tool_calls")
            log("4/5", f"    content: {results['tool_content_preview'][:200]!r}")
    except urllib.error.HTTPError as e:
        results["tool_error"] = f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}"
        log("4/5", f"  工具调用 ✗ {results['tool_error']}")
    return results


def stage_switch(args):
    log("5/5", "切换 WorkBuddy 桥接模型名")
    target = args.ollama_name
    note = os.path.join(ROOT, "data", "virtu_ollama_model.txt")
    os.makedirs(os.path.dirname(note), exist_ok=True)
    with open(note, "w", encoding="utf-8") as f:
        f.write(target + "\n")
    log("5/5", f"当前 Ollama 模型名写入 {note}")
    log("5/5", f"启动桥：python start_virtu_bridge.py "
               f"(需设 VIRTU_VLLM_MODEL={target})")


def main():
    p = argparse.ArgumentParser(description="LoRA 回传后本机一键落地")
    p.add_argument("--lora", required=True, help="回传的 LoRA 目录")
    p.add_argument("--base", default=os.path.join(ROOT, "checkpoints", "_base_qwen3_8b"))
    p.add_argument("--merged-dir", default=os.path.join(ROOT, "checkpoints", "virtu_merged_v2"))
    p.add_argument("--gguf", default=os.path.join(ROOT, "checkpoints", "virtu-q4_0-v2.gguf"))
    p.add_argument("--ollama-name", default="virtu-omni-8b-v2")
    p.add_argument("--work", default=os.path.join(ROOT, "tmp_deploy"))
    p.add_argument("--mode", default="peft_linear", choices=["peft_linear", "delta"])
    p.add_argument("--weight", type=float, default=1.0)
    p.add_argument("--append-default", action="store_true",
                   help="在默认 4 个 LoRA 基础上追加（推荐）")
    p.add_argument("--verify-samples", type=int, default=2)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="只做合并+量化+导入+验证，不切换")
    args = p.parse_args()

    print("=" * 70)
    print(" Virtu tool-call LoRA 本机落地流水线")
    print(f" LoRA    : {args.lora}")
    print(f" 合并产物: {args.merged_dir}")
    print(f" GGUF    : {args.gguf}")
    print(f" Ollama  : {args.ollama_name}")
    print(f" 模式    : {args.mode}  weight={args.weight} "
          f"append_default={args.append_default}")
    print("=" * 70)

    ver = ollama_available()
    if not ver:
        raise SystemExit("[FATAL] Ollama 未运行。请先启动 Ollama 服务。")
    log("0/5", f"Ollama {ver.get('version')} 就绪")

    if not os.path.exists(os.path.join(args.lora, "adapter_config.json")):
        raise SystemExit(f"[FATAL] LoRA 目录不完整: {args.lora}")
    with open(os.path.join(args.lora, "adapter_config.json"), encoding="utf-8") as f:
        ac = json.load(f)
    log("0/5", f"LoRA: r={ac.get('r')} alpha={ac.get('lora_alpha')} "
              f"targets={len(ac.get('target_modules') or [])}")
    if ac.get("r") != 32:
        log("0/5", f"[WARN] rank={ac.get('r')}，与既有 r=32 LoRA 不一致，"
                  f"peft_linear 模式会拒绝合并")

    t0 = time.time()
    merged = stage_merge(args)
    gguf = stage_gguf(args, merged)
    stage_import(args, gguf)
    results = stage_verify(args)

    report = {
        "ollama_model": args.ollama_name,
        "merged_dir": merged,
        "gguf": gguf,
        "results": results,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    os.makedirs(args.work, exist_ok=True)
    with open(os.path.join(args.work, "deploy_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    ok_chat = results.get("chat_ok")
    n_tc = results.get("tool_call_count", 0)
    print(f"[结果] 普通对话: {'PASS' if ok_chat else 'FAIL'}")
    print(f"[结果] 工具调用: {'PASS' if n_tc else 'FAIL'}  (结构化 tool_calls {n_tc} 个)")
    if not n_tc:
        print("       提示：若对话正常但工具调用失败，说明 LoRA 未真正学到")
        print("             tool_call 格式，检查训练数据是否走了官方 template。")
    if not args.dry_run:
        stage_switch(args)
    else:
        log("5/5", "--dry-run：未切换，验证通过后去掉该参数重跑")
    print(f"[report] {os.path.join(args.work, 'deploy_report.json')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
