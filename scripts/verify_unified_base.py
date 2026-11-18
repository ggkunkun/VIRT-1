#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端验证统一基座：加载 → 初始化 → 调用（隔离端口，不干扰默认 11434）。

为什么需要独立实例
------------------
本机 Ollama 0.40.15 存在两套存储布局：旧 manifests/ 与新 manifests-v2/。
默认服务重启后可能挂到旧库（列表为空），导致刚创建的 virtu-base:unified 不可见。
本脚本在 127.0.0.1:11435 启动一个指向工作库的临时实例，验证完即退出，
不触碰默认服务、不改任何标签。

用法:
    python scripts/verify_unified_base.py
    python scripts/verify_unified_base.py --store D:\\Virtu模型\\.ollama_store\\models --port 11435
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = str(ROOT / ".ollama_store" / "models")
BASE_FILE = ROOT / "modelfiles" / "BASE" / "virtu-base.Modelfile"
TAG = "virtu-base:unified"


def wait_ready(port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tags", timeout=3) as r:
                r.read()
            return True
        except Exception:
            time.sleep(1.0)
    return False


def chat(port: int, prompt: str, num_predict: int = 64, timeout: float = 420.0, tag: str = TAG) -> dict:
    payload = {
        "model": tag,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.1},
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--port", type=int, default=11435)
    ap.add_argument("--tag", default=TAG, help="要验证的标签；非基座标签跳过真源一致性检查")
    ap.add_argument("--prompt", default="用一句话说明 G00 快速移动的安全底线。")
    args = ap.parse_args(argv)

    tag = args.tag
    verdict: dict = {"tag": tag, "store": args.store, "steps": {}}

    # 0) 基座文件与单一真源一致（仅对基座标签生效）
    sys.path.insert(0, str(BASE_FILE.parent))
    import virtu_base as V  # noqa: E402
    if tag == TAG:
        actual = BASE_FILE.read_text(encoding="utf-8")
        consistent = actual == V.render()
        verdict["steps"]["source_consistent"] = consistent
        verdict["canonical_sha"] = V.canonical_sha(actual)[:16]
        if not consistent:
            verdict["result"] = "FAIL"
            verdict["reason"] = "Modelfile 与单一真源不一致，先运行 virtu_base.py write"
            print(json.dumps(verdict, ensure_ascii=False, indent=2))
            return 1

    # 1) 隔离实例
    env = dict(os.environ)
    env["OLLAMA_MODELS"] = args.store
    env["OLLAMA_HOST"] = f"127.0.0.1:{args.port}"
    log = Path(tempfile.gettempdir()) / f"virtu_base_verify_{args.port}.log"
    fh = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen(["ollama", "serve"], env=env, stdout=fh, stderr=subprocess.STDOUT)
    try:
        ready = wait_ready(args.port)
        verdict["steps"]["server_ready"] = ready
        if not ready:
            verdict["result"] = "FAIL"
            verdict["reason"] = f"隔离服务未就绪，日志 {log}"
            return 2

        # 2) 标签可见（加载前提）
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/tags", timeout=10) as r:
            tags = [m["name"] for m in json.load(r).get("models", [])]
        verdict["visible_tags"] = tags
        verdict["steps"]["tag_visible"] = tag in tags
        if tag not in tags:
            verdict["result"] = "FAIL"
            verdict["reason"] = f"{tag} 不在 {args.store} 视图中；需在该库重建"
            return 3

        # 3) 真实调用（触发权重加载 + 推理）
        started = time.time()
        resp = chat(args.port, args.prompt, tag=tag)
        elapsed = time.time() - started
        content = (resp.get("message", {}).get("content") or "").strip()
        thinking = resp.get("message", {}).get("thinking") or ""
        verdict["steps"]["call_ok"] = bool(content or thinking)
        verdict["call"] = {
            "elapsed_s": round(elapsed, 1),
            "done_reason": resp.get("done_reason"),
            "eval_count": resp.get("eval_count"),
            "prompt_eval_count": resp.get("prompt_eval_count"),
            "content_preview": content[:300],
            "thinking_chars": len(thinking),
        }
        # 4) 行为抽检：回答应体现 G00 安全语义（不校验具体措辞，只看关键概念）
        keywords = ("G00", "快速", "碰撞", "安全", "Z")
        hit = [k for k in keywords if k in content]
        verdict["steps"]["behavior_keywords"] = hit
        _ = hit  # 记录但不作为硬门（模型输出措辞可变）
        verdict["result"] = "PASS" if verdict["steps"]["call_ok"] else "FAIL"
        return 0 if verdict["result"] == "PASS" else 4
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        fh.close()
        print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
