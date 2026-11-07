#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start_virtu_bridge.py — Virtu-CAD-CAM 一键启动器

自动完成：依赖检查/安装 -> 设置环境变量 -> 校验真后端 -> 启动桥(端口 8000)

用法:
  python start_virtu_bridge.py                          # 按 DEFAULTS 自动选择后端
  python start_virtu_bridge.py --check                  # 只做诊断，不启动服务
  python start_virtu_bridge.py --backend llamacpp --gguf D:/models/q3-8b.Q4_K_M.gguf
  python start_virtu_bridge.py --backend transformers --model /path/Qwen3-8B
  python start_virtu_bridge.py --backend vllm_http --vllm http://127.0.0.1:11434/v1

后端自动优先级:
  1. 本地合并产物 + 本机 Ollama 已有 virtu-omni-8b -> vllm_http 指向 Ollama
     （Ollama 加载标准 GGUF，不依赖 MLX；本机无 torch 时唯一能跑的路径）
  2. 本地 HF 合并目录 + 有 torch -> transformers
  3. 本地 GGUF + 有 llama_cpp -> llamacpp
  4. 都没有 -> cloud 转发

说明:
  - 依赖仅在缺失时尝试 pip 安装；离线/受限网络请先手动 pip install。
  - 真后端不可用时，聊天接口返回明确的非成功错误，不伪造模型回答。
  - 本机 CAD/CAM 与桌面执行路由需要本地 Bearer Token，启动器会安全配置 WorkBuddy。
  - 想用你的对话/CAD LoRA，base 必须是 Qwen3-8B（与 LoRA 基底同版本）。
"""

import os
import sys
import json
import argparse
import importlib.util
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(ROOT, "scripts", "workbuddy_virtu_bridge.py")


def _ensure_stdio():
    """pythonw.exe has no std handles; attach a persistent log before printing."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir = os.path.join(ROOT, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log = open(os.path.join(log_dir, "bridge_service.log"), "a",
               encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log


_ensure_stdio()

DEFAULTS = {
    "backend": "auto",
    "model_path": "",
    "gguf_path": "",
    "vllm_url": "",
    "vllm_model": "virtu-comprehensive",
    "tool_model": "virtu-comprehensive",
    "conv_lora": os.path.join(ROOT, "checkpoints", "turing_conversational_lora"),
    "cad_lora": os.path.join(ROOT, "checkpoints", "cad_cam_six_software_lora"),
    "device": "auto",
    "max_tokens": "1024",
    # Qwen3 base + 对话 LoRA 在 temperature>=0.7 时会出现语义断裂/刷屏，
    # 实测 0.1~0.3 输出正常，故默认下调。
    "temperature": "0.3",
}

# 顺序即优先级：已训练且通过 30 例验证的 TIES 件领跑。``virtu-comprehensive``
# 在不同会话里被反复重建过（层哈希漂移），不能排在它前面冒充「已验证产物」。
VIRTU_ARTIFACT_PRIORITY = ("virtu-ties-v1", "virtu-comprehensive", "virtu-toolcall")

# 各后端所需依赖（pip 包名 -> import 名）
DEPS = {
    "transformers": [("torch", "torch"), ("transformers", "transformers"),
                     ("peft", "peft"), ("accelerate", "accelerate")],
    "llamacpp": [("llama-cpp-python", "llama_cpp")],
    "vllm_http": [],
    "cloud": [],  # 云端转发，仅用标准库，无需额外 pip 包
}


def parse_args():
    p = argparse.ArgumentParser(description="Virtu-CAD-CAM 一键启动器")
    p.add_argument("--check", action="store_true", help="只做诊断，不启动桥")
    p.add_argument("--backend", default=None, help="auto|transformers|llamacpp|vllm_http|cloud")
    p.add_argument("--model", dest="model_path", default=None, help="transformers 基座目录(Qwen3-8B)")
    p.add_argument("--gguf", dest="gguf_path", default=None, help="llamacpp 的 GGUF 路径")
    p.add_argument("--vllm", dest="vllm_url", default=None, help="vLLM/OpenAI 端点, 如 http://x:8001/v1")
    p.add_argument("--vllm-model", dest="vllm_model", default=None, help="通用文本模型名, 默认 virtu-ties-v1（已训练白名单，不再默认未训练基座）")
    p.add_argument("--tool-model", dest="tool_model", default=None, help="工具调用专用模型名, 默认 virtu-toolcall")
    p.add_argument("--conv-lora", dest="conv_lora", default=None)
    p.add_argument("--cad-lora", dest="cad_lora", default=None)
    p.add_argument("--device", default=None)
    p.add_argument("--max-tokens", dest="max_tokens", default=None)
    p.add_argument("--temperature", default=None)
    return p.parse_args()


def resolve_config(args):
    cfg = dict(DEFAULTS)
    # 记录用户「显式指定」的字段：CLI 参数或环境变量（区别于 DEFAULTS 自动带出）。
    # 用于 resolve_plan 在检测到合并产物时，安全清空非显式的运行时 LoRA，
    # 而不依赖脆弱的路径字符串相等判断。
    explicit = set()
    for k, v in vars(args).items():
        if k == "check":
            continue
        if v is not None:
            cfg[k] = v
            explicit.add(k)
    # 已存在的环境变量优先（允许用户在外面覆盖）
    for key in ("model_path", "gguf_path", "vllm_url", "vllm_model", "tool_model", "conv_lora", "cad_lora",
                "device", "max_tokens", "temperature"):
        env = os.environ.get("VIRTU_" + key.upper())
        if env:
            cfg[key] = env
            explicit.add(key)
    cfg["_explicit"] = explicit
    return cfg


def probe_ollama(model_name: str, host: str = "127.0.0.1:11434", timeout: float = 1.5) -> bool:
    """探测本机 Ollama 是否已有目标模型。

    用 ProxyHandler({}) 绕过本机透明代理（HTTP_PROXY=127.0.0.1:53004 会拦截
    localhost 请求）。超时 1.5s，探测失败不影响启动器。
    """
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://{host}/api/tags")
        with opener.open(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        models = [m.get("name", "") for m in d.get("models", [])]
        # Accept both an exact tagged name (qwen3:8b) and an untagged alias
        # (virtu-toolcall -> virtu-toolcall:latest). Splitting the requested
        # name as well silently rejected qwen3:8b and fell through to the old
        # merged model.
        return any(name == model_name or name.split(":")[0] == model_name
                   for name in models)
    except Exception:
        return False


def resolve_plan(cfg, cli_backend):
    if cli_backend and cli_backend != "auto":
        return cli_backend

    # 自动探测本地合并产物：GPU 机合并出的模型一落地，就自动从 cloud 转发
    # 切到本地真模型，无需手动设置 VIRTU_MODEL_PATH / VIRTU_GGUF_PATH。
    # 显式指定 --backend 时跳过探测（尊重用户覆盖）。
    if not cfg["model_path"] and not cfg["gguf_path"] and not cfg["vllm_url"]:
        merged_candidates = [
            os.path.join(ROOT, "checkpoints", "virtu_master_v4_merged"),
            os.path.join(ROOT, "checkpoints", "virtu_cad_cam_merged_v3"),
            os.path.join(ROOT, "checkpoints", "virtu_merged"),
        ]
        def validated_merged(path):
            report_path = os.path.join(path, "validation_report.json")
            try:
                with open(report_path, encoding="utf-8") as report_file:
                    report = json.load(report_file)
                receipt_path = os.path.join(path, "merge_receipt.json")
                with open(receipt_path, encoding="utf-8") as receipt_file:
                    receipt = json.load(receipt_file)
                return (report.get("status") == "PASS" and not report.get("errors")
                        and receipt.get("status") in {"COMPLETED", "PASS"}
                        and os.path.isfile(os.path.join(path, "config.json")))
            except (OSError, ValueError, TypeError):
                return False

        merged = next((m for m in merged_candidates if validated_merged(m)), "")
        gguf_candidates = [
            # 只列 delta/TIES 世系的合并件。virtu-production-v3-q4_0.gguf 由
            # peft_linear 时代的 virtu_cad_cam_merged_v3 转出，实测输出乱码
            # （benchmarks/VIRTU_CAPABILITY_REPORT.md §0/§3.1），不得进自动路径；
            # validated_gguf 只核对收据与字节数，拦不住「语法正确但权重已坏」。
            os.path.join(ROOT, "checkpoints", "virtu-master-v4-q4_0.gguf"),
            os.path.join(ROOT, "checkpoints", "virtu-ties-v1-q4_0.gguf"),
        ]
        def validated_gguf(path):
            receipt_path = path + ".receipt.json"
            try:
                with open(receipt_path, encoding="utf-8") as receipt_file:
                    receipt = json.load(receipt_file)
                return (receipt.get("status") == "ok" and not receipt.get("unmapped")
                        and os.path.isfile(path)
                        and receipt.get("file_bytes") == os.path.getsize(path))
            except (OSError, ValueError, TypeError):
                return False

        gguf = next((g for g in gguf_candidates if validated_gguf(g)), "")
        has_merged = bool(merged)
        has_gguf = bool(gguf)
        explicit = cfg.get("_explicit", set())

        # 本机显存有限时（如 6GB），transformers 直接跑 8B bf16 会触发内存颠簸。
        # 若 Ollama 已导入受控合并 GGUF，优先走 Ollama OpenAI 兼容端点（vllm_http）。
        if has_merged or has_gguf:
            # 顺序即优先级：显式指定 > 已训练 Virtu 产物。未训练基座绝不自动入选。
            candidates = (([cfg.get("vllm_model")] if "vllm_model" in explicit else [])
                          + list(VIRTU_ARTIFACT_PRIORITY))
            found_model = next((c for c in candidates if c and probe_ollama(c)), None)
            if found_model:
                cfg["vllm_url"] = "http://127.0.0.1:11434/v1"
                cfg["vllm_model"] = found_model
                # 权重已烘焙进基座，清掉运行时 LoRA 避免双重叠加
                if "conv_lora" not in explicit:
                    cfg["conv_lora"] = ""
                if "cad_lora" not in explicit:
                    cfg["cad_lora"] = ""
                if found_model not in VIRTU_ARTIFACT_PRIORITY:
                    print(f"[launcher] 注意: 正在服务 {found_model}，它不是已训练的 Virtu 产物；"
                          "对外模型 id 仍是 virtu-cad-cam-10b，测评结论不能归因给 Virtu 权重。")
                print(f"[launcher] 检测到本地 Ollama 模型 {found_model}，"
                      f"自动启用端点: {cfg['vllm_url']}")
                return "vllm_http"
            print("[launcher] 本机 Ollama 未导入任何已训练的 Virtu 产物 "
                  f"{list(VIRTU_ARTIFACT_PRIORITY)}；不自动退回未训练基座 qwen3:8b —— "
                  "那样评测与体感测的都是基座，却仍对外声明 virtu-cad-cam-10b。"
                  "请先 ollama create 一个训练产物；确要跑基座请显式 --vllm-model qwen3:8b。")

        if has_merged:
            cfg["model_path"] = merged
            # 权重已烘焙进基座，必须清掉运行时 LoRA，否则 _load_transformers
            # 会把 turing/six_software 再挂一层 => 双重叠加、能力失真。
            # 只清空「非用户显式指定」的：用户若真想额外挂别的适配器，
            # 显式 --conv-lora/--cad-lora 或对应环境变量会被保留。
            if "conv_lora" not in explicit:
                cfg["conv_lora"] = ""
            if "cad_lora" not in explicit:
                cfg["cad_lora"] = ""
            print(f"[launcher] 检测到本地合并模型，自动启用: {merged}"
                  f"  (conv_lora={cfg['conv_lora'] or 'None'}, cad_lora={cfg['cad_lora'] or 'None'})")
        elif has_gguf:
            cfg["gguf_path"] = gguf
            # GGUF 同样已烘焙，llamacpp 不用 LoRA，一并清掉避免误导
            if "conv_lora" not in explicit:
                cfg["conv_lora"] = ""
            if "cad_lora" not in explicit:
                cfg["cad_lora"] = ""
            print(f"[launcher] 检测到本地 GGUF，自动启用: {gguf}")

    if cfg["vllm_url"]:
        return "vllm_http"
    if cfg["model_path"]:
        return "transformers"
    if cfg["gguf_path"]:
        return "llamacpp"
    return "cloud"  # 默认：无本地权重时，自动用云端真实模型（零本地算力）


def ensure_deps(plan):
    pkgs = DEPS.get(plan, [])
    missing = []
    for pip_name, import_name in pkgs:
        if importlib.util.find_spec(import_name) is None:
            missing.append(pip_name)
    if not missing:
        print(f"[launcher] 依赖已就绪 ({plan})")
        return True
    print(f"[launcher] 缺失依赖 {missing}，尝试 pip 安装...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        return True
    except Exception as e:
        print(f"[launcher] 自动安装失败: {e}")
        print(f"[launcher] 请手动执行: pip install {' '.join(missing)}")
        return False


def apply_env(cfg):
    mapping = {
        "backend": "VIRTU_BACKEND",
        "model_path": "VIRTU_MODEL_PATH",
        "gguf_path": "VIRTU_GGUF_PATH",
        "vllm_url": "VIRTU_VLLM_URL",
        "vllm_model": "VIRTU_VLLM_MODEL",
        "tool_model": "VIRTU_TOOL_MODEL",
        "conv_lora": "VIRTU_CONV_LORA",
        "cad_lora": "VIRTU_CAD_LORA",
        "device": "VIRTU_DEVICE",
        "max_tokens": "VIRTU_MAX_TOKENS",
        "temperature": "VIRTU_TEMPERATURE",
    }
    for k, env in mapping.items():
        v = cfg[k]
        if v:
            os.environ[env] = str(v)


def diagnose(plan):
    print("\n=== Virtu 真后端诊断 ===")
    print(f"resolved backend plan : {plan}")
    try:
        sys.path.insert(0, ROOT)
        from virtu_real_backend import get_backend
        b = get_backend()
        print(f"backend available    : {b.available}")
        print(f"resolved backend     : {b._resolved}")
        if not b.available:
            print(f"unavailable reason   : {b.error}")
        print(f"CAD intent keywords  : {len(__import__('virtu_real_backend').CAD_KEYWORDS)} 个")
    except Exception as e:
        print(f"diagnose error: {type(e).__name__}: {e}")
    print("========================\n")


def main():
    args = parse_args()
    cfg = resolve_config(args)
    plan = resolve_plan(cfg, args.backend)
    print(f"[launcher] 目标后端: {plan}")

    # Authenticate the local bridge and keep the WorkBuddy endpoint in sync.
    sys.path.insert(0, ROOT)
    from bridges.bridge_security import ensure_bridge_token, sync_workbuddy_token
    token = ensure_bridge_token()
    os.environ["VIRTU_BRIDGE_TOKEN"] = token
    try:
        changed = sync_workbuddy_token(token)
    except Exception as exc:
        print(f"[launcher] 本地 WorkBuddy 凭据同步失败，拒绝启动: {type(exc).__name__}: {exc}")
        sys.exit(2)
    print("[launcher] 本机 API 鉴权已启用；WorkBuddy 凭据 "
          + ("已安全更新" if changed else "已是最新") + "（令牌不会显示在终端）")

    if not args.check:
        ensure_deps(plan)

    apply_env(cfg)
    diagnose(plan)

    if args.check:
        print("[launcher] --check 模式：未启动桥。")
        return

    if not os.path.exists(BRIDGE):
        print(f"[launcher] 找不到桥文件: {BRIDGE}")
        sys.exit(1)

    print(f"[launcher] 启动桥: {BRIDGE}  (Ctrl+C 退出)")
    try:
        subprocess.run([sys.executable, BRIDGE], env=os.environ, cwd=ROOT,
                       stdout=sys.stdout, stderr=sys.stderr)
    except KeyboardInterrupt:
        print("\n[launcher] 已停止。")


if __name__ == "__main__":
    main()
