#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
worldmodel_infer.py — 世界模型「生成侧输出层」标准封装（带推理时护栏）
========================================================================
把「调用模型生成 world_state + 护栏后处理」封装成一个可复用的标准入口。
任何上游（对话桥、agent 执行链、评测、批量蒸馏）都应通过本模块拿到
「已纠正/已拦截」的 world_state，而不是裸调 ollama 再自己判分。

接入示例（替换旧的「只判分」用法）：
  from worldmodel_infer import generate_world_state
  res = generate_world_state(
      model="virtu-wm-v3",
      prompt=user_prompt,
      scenario={"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}},
  )
  world_state = res["world_state"]          # 已是护栏纠正后的 dict
  if res["guard"]["action"] in ("rejected", "escalate"):
      # 走重生成 / 人工兜底
      ...

CLI（便于单独验证 / 管道调用）：
  python scripts/worldmodel_infer.py --model virtu-wm-v3 --prompt "..." --scenario-json '{"task":"roughness","inputs":{"f":0.12,"r_eps":0.8}}'
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import subprocess
from typing import Any, Dict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from guard_hooks import apply_guard  # noqa: E402

DEFAULT_HOST = "127.0.0.1:11434"
DEFAULT_TOL_REL = 0.08


def call_ollama(model: str, prompt: str, system: str = "",
                host: str = DEFAULT_HOST, timeout: int = 120) -> str:
    """调用本地 ollama /generate（与 eval_worldmodel.call_ollama 同口径：
    think=false + temperature=0 + num_predict 上限 + format=json + UTF-8 解码）。
    返回 response 字符串。"""
    payload = json.dumps({
        "model": model, "prompt": prompt, "system": system,
        "stream": False, "think": False, "format": "json",
        "options": {"temperature": 0, "num_predict": 1024},
    })
    try:
        # Windows 下 text=True 默认按 locale(GBK) 解码，ollama 返回 UTF-8 中文
        # 会抛 UnicodeDecodeError → 整题误记生成失败（eval 侧已修，此处曾漏）。
        p = subprocess.run(
            ["curl", "-s", f"http://{host}/api/generate", "-d", payload],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return json.loads(p.stdout)["response"]
    except Exception as e:  # noqa: BLE001 - 生成失败必须显式暴露，不伪造
        return f"<generate-fail:{e}>"


def generate_world_state(
    model: str,
    prompt: str,
    scenario: dict,
    system: str = "",
    tol_rel: float = DEFAULT_TOL_REL,
    host: str = DEFAULT_HOST,
    require_evidence: bool = True,
    execution_receipt: str = None,
) -> Dict[str, Any]:
    """标准生成侧输出层：生成 -> 护栏后处理 -> 返回结构化结果。"""
    raw = call_ollama(model, prompt, system, host)
    if raw.startswith("<generate-fail:"):
        return {
            "world_state": None,
            "raw": raw,
            "guard": {"action": "escalate", "issues": [raw], "layers_hit": [],
                      "provenance": "none", "final_world_state": None, "binding_risk": None},
        }
    g = apply_guard(raw, prompt=prompt, scenario=scenario, tol_rel=tol_rel,
                    require_evidence=require_evidence, execution_receipt=execution_receipt)
    return {
        "world_state": g["final_world_state"],
        "raw": raw,
        "guard": g,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--scenario-json", default="{}", help='{"task":..., "inputs":{...}}')
    ap.add_argument("--system", default="")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--tol-rel", type=float, default=DEFAULT_TOL_REL)
    args = ap.parse_args()

    scenario = json.loads(args.scenario_json) if args.scenario_json else {}
    res = generate_world_state(args.model, args.prompt, scenario,
                               system=args.system, tol_rel=args.tol_rel, host=args.host)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
