# -*- coding: utf-8 -*-
"""让 Virtu 13.63B 通过工具调用环真正驱动装配全流程。

流程：模型自主选择 cadcam_step_reverse(bom) 理解结构，再选
cadcam_assembly_build(full_mated) 在 SolidWorks 里完成 拆件->装配->工程图。
证据：完整对话、工具调用参数、执行结果、最终 verification.json。

用法：python scripts/model_drives_assembly.py --step <path> [--model TAG]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call  # noqa: E402

OLLAMA = os.environ.get("VIRTU_OLLAMA", "http://127.0.0.1:11434")


def _tags() -> list:
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def _pick_model(pref: str = "") -> str:
    tags = _tags()
    if pref and pref in tags:
        return pref
    for cand in ("virtu-moe-14b:fast", "virtu-moe-14b:latest", "virtu-moe-14b:01068725"):
        if cand in tags:
            return cand
    raise SystemExit("no virtu-moe-14b tag available; tags=%s" % tags)


def _chat(model: str, messages: list, tools: list) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": tools,
                       "stream": False, "options": {"temperature": 0, "num_ctx": 8192}},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def _tool_schema(names) -> list:
    defs = get_cadcam_tool_definitions()
    return [d for d in defs if d.get("function", {}).get("name") in names]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default=os.path.join(ROOT, "assets", "wheel_mold_P0.step"))
    ap.add_argument("--model", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--max-rounds", type=int, default=6)
    args = ap.parse_args(argv)
    step = os.path.abspath(args.step)
    out_dir = os.path.abspath(args.out or os.path.join(
        ROOT, "runs", "model_drive_" + time.strftime("%Y%m%d_%H%M%S")))
    os.makedirs(out_dir, exist_ok=True)
    model = _pick_model(args.model)
    tools = _tool_schema({"cadcam_step_reverse", "cadcam_assembly_build"})
    system = ("你是 Virtu 工业智能体。必须用工具完成用户目标，不要空谈。"
              "理解装配体用 cadcam_step_reverse(action=\"bom\")；"
              "在 SolidWorks 里真实拼装并出图用 cadcam_assembly_build(action=\"full_mated\")。"
              "工具返回的 status/门禁是唯一成功依据；失败要如实报告。")
    user = ("目标：理解这份 STEP 装配体（零件树/位姿/接触配合），并在 SolidWorks 里完成"
            "拆件建模→真实配合装配→GB 工程图全流程。\n"
            "STEP 路径：%s\n产物目录：%s\n"
            "请先调用 cadcam_step_reverse 的 bom 动作理解结构，再调用 "
            "cadcam_assembly_build 的 full_mated 动作完成装配与出图。" % (step, out_dir))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    transcript = {"model": model, "endpoint": OLLAMA, "step": step, "out_dir": out_dir,
                  "tools": [t["function"]["name"] for t in tools], "rounds": []}
    driver = "model"
    final = None
    for rnd in range(args.max_rounds):
        t0 = time.time()
        resp = _chat(model, messages, tools)
        msg = resp.get("message") or {}
        rec = {"round": rnd + 1, "elapsed_s": round(time.time() - t0, 2),
               "served_model": resp.get("model"), "content": (msg.get("content") or "")[:2000],
               "tool_calls": []}
        transcript["rounds"].append(rec)
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": msg.get("tool_calls") or []})
        calls = msg.get("tool_calls") or []
        if not calls:
            if rnd == 0:
                messages.append({"role": "user", "content":
                                 "请现在调用工具：先 cadcam_step_reverse(action=\"bom\")，"
                                 "再 cadcam_assembly_build(action=\"full_mated\")。"})
                continue
            break
        for call in calls:
            fn = call.get("function") or {}
            name, raw_args = fn.get("name", ""), fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}
            rec["tool_calls"].append({"name": name, "arguments": raw_args})
            try:
                result = execute_tool_call(name, raw_args)
            except Exception as e:  # noqa: BLE001
                result = {"status": "error", "message": type(e).__name__ + ": " + str(e)[:300]}
            brief = {k: result.get(k) for k in ("status", "message", "failed_gates", "gates")
                     if k in result}
            if name == "cadcam_assembly_build" and result.get("steps"):
                brief["verification_json"] = os.path.join(out_dir, "verification.json")
                final = result
            rec["tool_calls"][-1]["result_brief"] = brief
            messages.append({"role": "tool", "content":
                             json.dumps(result, ensure_ascii=False)[:60000]})
        if final is not None:
            break
    transcript["driver"] = driver
    transcript["final_status"] = (final or {}).get("status")
    transcript["verification_json"] = os.path.join(out_dir, "verification.json") \
        if os.path.exists(os.path.join(out_dir, "verification.json")) else None
    with open(os.path.join(out_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)
    print(json.dumps({"model": model, "driver": driver,
                      "final_status": transcript["final_status"],
                      "verification_json": transcript["verification_json"],
                      "transcript": os.path.join(out_dir, "transcript.json")},
                     ensure_ascii=False, indent=2))
    return 0 if transcript["final_status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
