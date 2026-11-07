#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_local_sft.py — 本地部署云端训好的边界强化 LoRA（Virtu CAD/CAM）

目标：把云端训出的 PEFT LoRA adapter 落到本机 Ollama，让现有桥
(virtu-cad-cam-10b 别名) 在保留旧模型的前提下灰度切到 SFT 模型，并重评测。

真实链路（已核对源码）：
  * 桥 workbuddy_virtu_bridge.py 把 MODEL_ID="virtu-cad-cam-10b" 仅作对外别名；
    真正模型由 virtu_real_backend.VirtuRealModel 决定，默认自动发现 Ollama 的 qwen3:8b。
  * 灰度切 = 设环境变量 VIRTU_OLLAMA_MODEL=<新模型> 后重启桥；旧 qwen3:8b 完全保留。
  * 本机 GPU 为 RTX 4050 6GB，跑不动 fp16 全模(~16G)，只能走 Ollama 量化路径。
    => 默认 adapter 模式：把 LoRA 转 lora.gguf，用 Ollama ADAPTER 挂到 qwen3:8b，
       仅几十 MB，零额外显存。merge 模式会产出整模 GGUF（q8_0 ~8.5G，需再量化成 q4 才能塞进 6G）。

用法：
  # 1) 只构建（转换 + 注册 Ollama），不切桥
  python scripts/deploy_local_sft.py --adapter-dir checkpoints/cad_cam_boundary_lora

  # 2) 构建 + 切桥（推荐全流程）
  python scripts/deploy_local_sft.py --adapter-dir checkpoints/cad_cam_boundary_lora --switch

  # 3) 仅切/回滚桥（构建已完成）
  python scripts/deploy_local_sft.py --switch-only --new-model virtu-cad-cam-10b-sft
  python scripts/deploy_local_sft.py --rollback            # 切回 qwen3:8b

  # 4) 跑完构建+切桥后，重跑 240 例评测对比（默认关，耗时约 2h）
  python scripts/deploy_local_sft.py --switch --run-eval
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
HF_MIRROR = "https://hf-mirror.com"
OLLAMA_BASE = "qwen3:8b"          # 当前线上实际服务的 Ollama 模型
NEW_MODEL = "virtu-cad-cam-10b-sft"
HEALTH_URL = "http://127.0.0.1:8000/v1/models"
VENV_PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")


def log(*a):
    print("[deploy]", *a, flush=True)


def run(cmd, **kw):
    log("+", " ".join(str(c) for c in cmd))
    kw.setdefault("cwd", ROOT)
    return subprocess.run(cmd, **kw)


def py():
    return VENV_PY if os.path.exists(VENV_PY) else sys.executable


def _locate_tooling(clone_dir: str):
    """在克隆目录里定位 conversion 包与 gguf 包，返回它们各自的父目录
    （import 需要父目录在 sys.path）。布局随版本变化，故自动搜索。"""
    conv_parent = None
    gguf_parent = None
    for root, dirs, files in os.walk(clone_dir):
        if "conversion" in dirs and os.path.exists(
                os.path.join(root, "conversion", "__init__.py")):
            conv_parent = root
        if "gguf" in dirs and os.path.exists(
                os.path.join(root, "gguf", "__init__.py")):
            gguf_parent = root
        if conv_parent and gguf_parent:
            break
    return conv_parent, gguf_parent


def ensure_llama_cpp_tools(tools_dir: str):
    """确保 llama.cpp 的 conversion/ + gguf 包可用（convert_lora_to_gguf /
    convert_hf_to_gguf 都需要）。优先复用已存在；否则从镜像稀疏克隆。
    返回 (conv_parent, gguf_parent) 两个需加入 PYTHONPATH 的目录。"""
    clone_dir = os.path.join(tools_dir, "llama.cpp")
    conv_parent, gguf_parent = _locate_tooling(clone_dir)
    if conv_parent and gguf_parent:
        log("llama.cpp conversion tooling: available at", clone_dir)
        return conv_parent, gguf_parent
    log("llama.cpp conversion tooling: missing, attempting clone ...")
    os.makedirs(tools_dir, exist_ok=True)
    if os.path.isdir(clone_dir):
        import shutil as _sh
        _sh.rmtree(clone_dir)
    mirrors = [
        "https://ghfast.top/https://github.com/ggerganov/llama.cpp.git",
        "https://kgithub.com/ggerganov/llama.cpp.git",
        "https://github.com/ggerganov/llama.cpp.git",
    ]
    cloned = False
    for url in mirrors:
        log("  cloning from", url)
        if run(["git", "clone", "--depth", "1", "--filter=blob:none",
                "--sparse", url, clone_dir]).returncode == 0:
            cloned = True
            break
    if not cloned:
        raise SystemExit(
            "[FATAL] 无法克隆 llama.cpp。请手动克隆后重跑，或加 --skip-convert-tools。")
    # conversion/ 与 gguf-py/ 在不同版本可能位于根目录或 convert/ 子目录，逐一尝试
    for sset in (["conversion", "gguf-py", "convert.py"], ["convert"]):
        run(["git", "-C", clone_dir, "sparse-checkout", "set", *sset])
        conv_parent, gguf_parent = _locate_tooling(clone_dir)
        if conv_parent and gguf_parent:
            break
    if not (conv_parent and gguf_parent):
        raise SystemExit(
            "[FATAL] 克隆完成但找不到 conversion/ 或 gguf 包。\n"
            "请检查 scripts/llama_cpp_tools/llama.cpp 目录结构。")
    log("  located conversion@%s  gguf@%s" % (conv_parent, gguf_parent))
    return conv_parent, gguf_parent


def _tool_env(conv_parent: str, gguf_parent: str) -> dict:
    env = dict(os.environ, HF_ENDPOINT=HF_MIRROR, NO_LOCAL_GGUF="1")
    paths = os.pathsep.join([conv_parent, gguf_parent, env.get("PYTHONPATH", "")])
    env["PYTHONPATH"] = paths
    return env


def build_adapter_gguf(adapter_dir: str, conv_parent: str, gguf_parent: str) -> str:
    out_gguf = os.path.join(ROOT, "checkpoints", "virtu_boundary_sft_lora.gguf")
    env = _tool_env(conv_parent, gguf_parent)
    # 本地完整 Qwen3-8B 基座（config + 5 个 safetensors 分片 + index 齐全），
    # 用 --base 走本地，避免联网拉基座张量名（huggingface.co 被本机代理拦截、hf-mirror 的
    # resolve 路径返回 403，远程路径在此环境不可达）。
    local_base = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
    cmd = [
        py(), os.path.join(SCRIPTS, "convert_lora_to_gguf.py"),
        adapter_dir,
        "--base", local_base,
        "--outtype", "f16",
        "--outfile", out_gguf,
    ]
    if run(cmd, env=env).returncode != 0:
        raise SystemExit("[FATAL] convert_lora_to_gguf 失败，见上。")
    log("lora.gguf ->", out_gguf)
    return out_gguf


def build_merge_gguf(adapter_dir: str, conv_parent: str, gguf_parent: str) -> str:
    base = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
    merged = os.path.join(ROOT, "checkpoints", "virtu_boundary_sft_merged")
    out_gguf = os.path.join(ROOT, "checkpoints", "virtu_boundary_sft_q8_0.gguf")
    if run([py(), os.path.join(SCRIPTS, "merge_numpy.py"),
            "--base", base, "--out", merged, "--mode", "delta",
            "--lora", adapter_dir]).returncode != 0:
        raise SystemExit("[FATAL] merge_numpy 失败，见上。")
    env = _tool_env(conv_parent, gguf_parent)
    if run([py(), os.path.join(SCRIPTS, "convert_hf_to_gguf.py"), merged,
            "--outtype", "q8_0", "--outfile", out_gguf], env=env).returncode != 0:
        raise SystemExit("[FATAL] convert_hf_to_gguf 失败，见上。")
    log("merged.gguf (q8_0, ~8.5G) ->", out_gguf)
    log("[WARN] q8_0 约 8.5G > 本机 4050 的 6G，需再用 llama-quantize 量化成 q4_K_M；")
    log("       直接 ollama create 会 OOM。建议改用默认 adapter 模式。")
    return out_gguf


def register_ollama(new_model: str, modelfile_body: str) -> None:
    ollama = shutil.which("ollama") or r"C:\Program Files\Ollama\ollama.exe"
    if not os.path.exists(ollama):
        raise SystemExit(f"[FATAL] 找不到 ollama: {ollama}")
    mf_path = os.path.join(ROOT, "checkpoints", f"{new_model}.Modelfile")
    with open(mf_path, "w", encoding="utf-8") as f:
        f.write(modelfile_body)
    log("Modelfile ->", mf_path)
    # 已存在则先删
    run([ollama, "rm", new_model], stderr=subprocess.DEVNULL)
    # Ollama 新版用 ADAPTER，旧版用 LORA；前者失败则回退
    for directive in ("ADAPTER", "LORA"):
        body = modelfile_body.replace("ADAPTER", directive)
        with open(mf_path, "w", encoding="utf-8") as f:
            f.write(body)
        if run([ollama, "create", new_model, "-f", mf_path]).returncode == 0:
            log(f"ollama model registered ({directive}):", new_model)
            return
    raise SystemExit("[FATAL] ollama create 失败（ADAPTER/LORA 均被拒），见上。")


def verify_ollama(new_model: str) -> bool:
    ollama = shutil.which("ollama") or r"C:\Program Files\Ollama\ollama.exe"
    r = run([ollama, "show", new_model], capture_output=True, text=True)
    ok = r.returncode == 0
    log("ollama show:", "OK" if ok else "FAIL")
    if ok:
        # 轻量探针：看是否还能正常吐字（Ollama ADAPTER 兼容性粗验）
        probe = ("只回答：给定切削速度 Vc=100、但没给刀具直径，能否算转速？"
                 "用一句话说明你该怎么做。")
        p = run([ollama, "run", new_model, probe], capture_output=True, text=True,
                timeout=120)
        log("probe output:", (p.stdout or p.stderr).strip()[:200])
    return ok


def switch_bridge(new_model: str) -> None:
    """灰度切桥：持久化 VIRTU_OLLAMA_MODEL + 带环境变量重启桥（绕开 explorer 不继承 setx 的坑）。"""
    # 1) 持久化（用户级，重启机器后仍生效，best-effort）
    try:
        run(["setx", "VIRTU_OLLAMA_MODEL", new_model],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("setx VIRTU_OLLAMA_MODEL =", new_model, "(已持久化)")
    except Exception as e:  # noqa: BLE001
        log("[WARN] setx 失败（非致命）:", e)
    # 2) 停旧桥
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "start_bridge_service", os.path.join(SCRIPTS, "start_bridge_service.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        stopped = mod.stop_bridge()
        log("stopped bridge pids:", stopped)
    except Exception as e:  # noqa: BLE001
        log("[WARN] 停桥失败（可能本就未运行）:", e)
    # 3) 带环境变量直接拉起桥（Windows 子进程不随父退出而死的，真机无沙箱回收）
    target = os.path.join(SCRIPTS, "virtu_service_pinned.py")
    env = dict(os.environ, VIRTU_OLLAMA_MODEL=new_model)
    try:
        subprocess.Popen(
            [py(), target], cwd=ROOT, env=env,
            creationflags=0x00000200,  # CREATE_NEW_PROCESS_GROUP
        )
        log("launched bridge with VIRTU_OLLAMA_MODEL =", new_model)
    except Exception as e:  # noqa: BLE001
        log("[WARN] 直接拉起失败，改走 explorer 通道:", e)
        subprocess.Popen(["explorer.exe", os.path.join(ROOT, "VirtuBridgeService.lnk")],
                         cwd=ROOT)
    # 4) 等健康
    _wait_health()


def _wait_health(timeout: float = 150.0) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(HEALTH_URL, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
                log("bridge healthy, models:", data)
                return
        except Exception:
            time.sleep(1)
    log("[WARN] 桥未在超时内就绪，请手动检查 logs/bridge_service.log")


def rollback() -> None:
    switch_bridge(OLLAMA_BASE)
    log("已切回", OLLAMA_BASE)


def run_eval() -> None:
    log("重跑 240 例评测（约 2h）...")
    r = run([py(), "_eval_diag.py"], stdout=subprocess.DEVNULL)
    if r.returncode != 0:
        log("[WARN] 评测启动返回非 0，详见 _eval_full4.log")
        return
    run([py(), os.path.join("virtu_eval", "report.py"),
         "--runs", "virtu:_eval_full4", "--out", "benchmarks/virtu_capability_v1"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter-dir", default=os.path.join(ROOT, "checkpoints",
                        "cad_cam_boundary_lora"))
    ap.add_argument("--mode", choices=["adapter", "merge"], default="adapter")
    ap.add_argument("--new-model", default=NEW_MODEL)
    ap.add_argument("--ollama-base", default=OLLAMA_BASE)
    ap.add_argument("--tools-dir", default=os.path.join(SCRIPTS, "llama_cpp_tools"))
    ap.add_argument("--skip-convert-tools", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--switch", action="store_true")
    ap.add_argument("--switch-only", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--run-eval", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.rollback:
        log("== 回滚 ==")
        rollback()
        return

    if args.switch_only:
        log("== 仅切桥 ==")
        switch_bridge(args.new_model)
        return

    # 1) 校验 adapter
    cfg = os.path.join(args.adapter_dir, "adapter_config.json")
    wts = os.path.join(args.adapter_dir, "adapter_model.safetensors")
    if not args.skip_build and not (os.path.exists(cfg) and os.path.exists(wts)):
        raise SystemExit(f"[FATAL] adapter 不完整（缺 {cfg} 或 {wts}）\n"
                         f"        请把云端 checkpoints/cad_cam_boundary_lora/ 下回来。")

    # 2) 构建
    if not args.skip_build:
        if not args.skip_convert_tools:
            conv_parent, gguf_parent = ensure_llama_cpp_tools(args.tools_dir)
        else:
            conv_parent = os.path.join(args.tools_dir, "llama.cpp")
            gguf_parent = conv_parent
        if args.mode == "adapter":
            gguf = build_adapter_gguf(args.adapter_dir, conv_parent, gguf_parent)
            body = f"FROM {args.ollama_base}\nADAPTER {os.path.abspath(gguf)}\n"
        else:
            gguf = build_merge_gguf(args.adapter_dir, conv_parent, gguf_parent)
            body = f"FROM {os.path.abspath(gguf)}\n"
        register_ollama(args.new_model, body)
        verify_ollama(args.new_model)
    else:
        log("== skip-build：假定", args.new_model, "已注册 ==")

    # 3) 切桥
    if args.switch:
        log("== 灰度切桥 ==")
        switch_bridge(args.new_model)

    # 4) 评测
    if args.run_eval:
        run_eval()

    log("DONE. 当前线上模型：", args.new_model if args.switch else "(未切，仍 qwen3:8b)")
    if not args.switch:
        log("要切桥执行：python scripts/deploy_local_sft.py --switch-only "
            f"--new-model {args.new_model}")


if __name__ == "__main__":
    main()
