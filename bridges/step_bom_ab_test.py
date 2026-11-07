# -*- coding: utf-8 -*-
"""A/B 对照实验：原始 STEP 噪声 vs BOM 注入，同一模型、同一问题、等长上下文。

这是「13.63B 读不懂装配体」解法有效性的**可复现实证工具**。
唯一变量 = 上下文的表征方式（原始几何噪声 / 结构化 BOM），
两路 prompt 长度刻意对齐，排除"上下文更长所以答得更好"的干扰。

2026-11-06 首次实跑（model=virtu-moe-14b:fast, wheel_mold_P0.step）：
  A 原始 STEP 片段 2016 字符 → 命中 0/7，答「不确定，信息不足」
  B BOM 注入       1991 字符 → 命中 7/7，精确列出 5 零件 + 4 组摆放坐标
证据存档：reports/step_bom_ab_test.json

用法:
  python3 bridges/step_bom_ab_test.py
  python3 bridges/step_bom_ab_test.py --model virtu-production:latest \
      --step assets/wheel_mold_P0.step --json reports/ab2.json
  python3 bridges/step_bom_ab_test.py --no-llm   # 只生成两路 prompt，不调用模型
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiagent_assembly import AssemblyMultiAgent  # noqa: E402
from step_bom import detect_encoding  # noqa: E402

DEFAULT_QUESTION = (
    "这个装配体一共有几个零件？请逐一列出子零件名称，并给出各自的摆放坐标（mm）。"
    "只回答事实，不要推测。")
# 事实核查关键词：4 个子件名 + 3 个特征坐标数
FACT_KEYS = ["微型机轮模", "微型机夹模", "微型机导模", "微型机夹料模",
             "48", "73", "-113.47"]


def build_prompts(step_path: str, question: str) -> Dict[str, Any]:
    agent = AssemblyMultiAgent(step_path)
    rep = agent.run()
    bom_prompt = rep["synthesis_prompt"]
    enc = rep["facets"][0]["data"]["encoding"]
    raw = open(step_path, "rb").read().decode(enc, errors="replace")
    # A 路：取与 B 路等长的原始 STEP 前缀（几何噪声为主，结构行在文件末尾）
    a = ("下面是该 STEP 文件的原始内容片段，请据此回答问题。\n\n"
         + raw[:len(bom_prompt)] + "\n\n---\n问题：" + question)
    # B 路：结构化 BOM 注入
    b = bom_prompt + "\n\n---\n请直接回答问题：" + question
    return {
        "A_raw_step": a, "B_bom_injected": b,
        "a_chars": len(a), "b_chars": len(b),
        "source": os.path.basename(step_path),
        "source_sha256": rep["source_sha256"],
        "encoding": enc,
    }


def ask_ollama(prompt: str, model: str, endpoint: str, timeout: int) -> Dict[str, Any]:
    payload = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate", data=payload,
        headers={"Content-Type": "application/json"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.perf_counter()
    try:
        with op.open(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return {"status": "ok", "sec": round(time.perf_counter() - t0, 1),
                "eval_count": d.get("eval_count"),
                "response": d.get("response", "").strip()}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "sec": round(time.perf_counter() - t0, 1),
                "error": "%s: %s" % (type(exc).__name__, exc)}


def score(resp: Dict[str, Any], keys) -> int:
    txt = resp.get("response", "")
    return sum(1 for k in keys if k in txt)


def main(argv=None):
    ap = argparse.ArgumentParser(description="STEP BOM 注入有效性 A/B 对照实验")
    ap.add_argument("--step", default="assets/wheel_mold_P0.step")
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--model", default="virtu-moe-14b:fast")
    ap.add_argument("--endpoint", default="http://127.0.0.1:11434")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--keys", nargs="*", default=FACT_KEYS)
    ap.add_argument("--json", default="reports/step_bom_ab_test.json")
    ap.add_argument("--no-llm", action="store_true", help="只生成两路 prompt")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.step):
        print("[!] STEP 不存在: %s" % a.step)
        return 1
    pr = build_prompts(a.step, a.question)
    print("[A/B] model=%s | A=原始STEP(%d字符) B=BOM注入(%d字符) | sha256=%s" %
          (a.model, pr["a_chars"], pr["b_chars"], pr["source_sha256"][:16]), flush=True)

    if a.no_llm:
        # Windows 下 /dev/stdout 不可用，直接 print（跨平台）
        print("--- A (原始 STEP 片段前 1200 字符) ---")
        print(pr["A_raw_step"][:1200])
        print("\n--- B (BOM 注入前 1200 字符) ---")
        print(pr["B_bom_injected"][:1200])
        return 0

    ra = ask_ollama(pr["A_raw_step"], a.model, a.endpoint, a.timeout)
    ra["tag"] = "A_raw_step"
    print("  A 完成: %s %.1fs" % (ra["status"], ra["sec"]), flush=True)
    rb = ask_ollama(pr["B_bom_injected"], a.model, a.endpoint, a.timeout)
    rb["tag"] = "B_bom_injected"
    print("  B 完成: %s %.1fs" % (rb["status"], rb["sec"]), flush=True)

    ra["hit"] = score(ra, a.keys)
    rb["hit"] = score(rb, a.keys)
    verdict = ("BOM 注入命中率更高" if rb["hit"] > ra["hit"] else
               "两者持平" if rb["hit"] == ra["hit"] else "A 更高(需复核)")
    out = {
        "tool": "bridges.step_bom_ab_test", "basis": "measured",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": a.model, "question": a.question,
        "source": pr["source"], "source_sha256": pr["source_sha256"],
        "a_chars": pr["a_chars"], "b_chars": pr["b_chars"],
        "controlled_variable": "仅上下文表征方式不同，两路长度刻意对齐",
        "fact_keys": a.keys, "max_hit": len(a.keys),
        "A_raw_step": ra, "B_bom_injected": rb, "verdict": verdict,
    }
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("[+] 证据存档: %s" % a.json)
    print("\n=== 结果 ===")
    print("  A(原始STEP): hit=%d/%d" % (ra["hit"], len(a.keys)))
    print("  B(BOM注入): hit=%d/%d" % (rb["hit"], len(a.keys)))
    print("  判定: %s" % verdict)
    print("\n--- A 回答 ---\n%s" % ra.get("response", ra.get("error", ""))[:800])
    print("\n--- B 回答 ---\n%s" % rb.get("response", rb.get("error", ""))[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
