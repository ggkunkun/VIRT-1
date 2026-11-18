#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""推理侧接地层的真机复测：裸模型 vs 接地层，同题、同判分器、按 digest 归属。

    .venv/Scripts/python.exe scripts/grounded_reprobe.py --tag virtu-six-software:v3

测量纪律（AGENTS.md §8 / 测评法律）：
  - 起腿前检查测量链独占：发现 run_full_repair_* / train_* 进程或 `ollama ps` 有他人加载的模型 ⇒
    拒跑（--force 也只把结果标 basis=partial，不标 measured）。
  - RunIdentity 记录模型 digest、判分器与本模块 sha256；收腿 drift() 非空 ⇒ 腿作废。
  - 报告把 **裸模型通过** 与 **接地层最终通过** 分开写；确定性兜底计入 `fallback`，
    绝不计入模型能力。传输错误单列，不当 0 分。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
sys.path.insert(0, str(ROOT / "scripts"))

from virtu_eval.provenance import RunIdentity  # noqa: E402
from virtu_omni.agent.grounded_inference import (  # noqa: E402
    GroundedResponder, check_lame_answer, lame_thick_cylinder, parse_g71_request,
    parse_lame_request, validate_g71_against_spec,
)
import deploy_trained_adapter as official_grader  # noqa: E402
from g71_semantic_check import check_g71_step_shaft  # noqa: E402

CASES = [
    ("lame_official", "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"),
    ("lame_gen_50_100_24", "按 Lamé 厚壁圆筒理论：内径 Di=50 mm，外径 Do=100 mm，内压 Pi=24 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"),
    ("lame_gen_40_100_15", "按 Lamé 厚壁圆筒理论：内径 Di=40 mm，外径 Do=100 mm，内压 Pi=15 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"),
    ("g71_official", "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"),
    ("g71_gen_80_46_25_60", "用 FANUC ISO/G 格式为 Ø80 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø46 长 25 mm，总长 60 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"),
    ("g71_gen_50_30_15_40", "用 FANUC ISO/G 格式为 Ø50 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø30 长 15 mm，总长 40 mm），含 G50 S2000、G96 S180 M03、T0101、F0.2 与 M30，只输出程序。"),
]

RULER = ("virtu_omni/agent/grounded_inference.py", "cloud_train_pack/deploy_trained_adapter.py",
         "scripts/g71_semantic_check.py", "scripts/grounded_reprobe.py")


def _ollama(path: str, payload: dict | None = None, timeout: int = 240) -> dict:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "http://127.0.0.1:11434" + path
    if payload is None:
        with op.open(url, timeout=timeout) as r:
            return json.loads(r.read())
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with op.open(req, timeout=timeout) as r:
        return json.loads(r.read())


def chain_busy(tag: str) -> list[str]:
    reasons = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { $_.CommandLine }"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, text=True,
            encoding="utf-8", errors="replace").stdout or ""
        for line in out.splitlines():
            if any(k in line for k in ("run_full_repair", "train_", "--verify-only", "virtu_eval.runner")):
                reasons.append(f"foreign_runner: {line.strip()[:140]}")
    except Exception as exc:
        reasons.append(f"process_probe_failed: {exc}")
    try:
        loaded = [m.get("name") for m in _ollama("/api/ps", timeout=15).get("models", [])]
        others = [m for m in loaded if m != tag]
        if others:
            reasons.append(f"ollama_has_other_models_loaded: {others}")
    except Exception as exc:
        reasons.append(f"ollama_unreachable: {exc}")
    return reasons


def make_caller(tag: str, transport_log: list):
    def call(messages):
        try:
            r = _ollama("/api/chat", {"model": tag, "messages": messages, "stream": False, "think": False,
                                      "keep_alive": "180s",
                                      "options": {"num_predict": 520, "temperature": 0}})
        except Exception as exc:
            transport_log.append(str(exc)[:200])
            return None
        txt = str((r.get("message") or {}).get("content", "")).strip()
        if not txt:
            transport_log.append("empty_response")
            return None
        return txt
    return call


def bare_verdict(case_prompt: str, text: str | None) -> dict:
    if text is None:
        return {"passed": None, "verdict": "transport_error_or_empty"}
    spec = parse_g71_request(case_prompt)
    if spec is not None:
        v = validate_g71_against_spec(text, spec)
    else:
        p = parse_lame_request(case_prompt)
        v = check_lame_answer(text, p, lame_thick_cylinder(**p))
    return {"passed": v["passed"], "violations": v["violations"]}


def _ollama_tag_digest(tag: str) -> str | None:
    try:
        for m in _ollama("/api/tags", timeout=15).get("models", []):
            if m.get("name") == tag:
                return m.get("digest")
    except Exception:
        return None
    return None


def _official_cross_check(cid: str, text: str | None) -> dict | None:
    if not text:
        return None
    if cid == "lame_official":
        r = official_grader.evaluate_lame_stress_probe(text)
        return {"probe": "lame_stress_probe", "passed": bool(r.get("passed")), "reason": r.get("reason")}
    if cid == "g71_official":
        tok = official_grader.evaluate_fanuc_g71_safety_probe(text)
        sem = check_g71_step_shaft(text)
        return {
            "probe": "fanuc_g71_safety_probe+g71_semantic_check",
            "token_passed": bool(tok.get("passed")),
            "token_reason": tok.get("reason"),
            "semantic_passed": bool(sem.get("passed")),
            "semantic_violations": sem.get("violations"),
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="virtu-six-software:v3")
    ap.add_argument("--max-repairs", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="链被占用仍跑；结果只标 basis=partial")
    args = ap.parse_args()

    busy = chain_busy(args.tag)
    if busy and not args.force:
        print("[REFUSE] 测量链非独占（AGENTS.md §8.6 / 测评法律第六条）：")
        for b in busy:
            print("   -", b)
        return 2

    out_dir = ROOT / "runs" / "grounded_reprobe" / time.strftime("%Y%m%d_%H%M%S")
    tag_digest_before = _ollama_tag_digest(args.tag)
    ident = RunIdentity.capture(model_ids=[args.tag], ruler_files=RULER,
                                extra={"cases": [c[0] for c in CASES], "max_repairs": args.max_repairs})
    ident.write(out_dir / "identity.json")

    transport: list = []
    caller = make_caller(args.tag, transport)
    rows = []
    for cid, prompt in CASES:
        msgs = [{"role": "user", "content": prompt}]
        bare_txt = caller(msgs)
        grounded = GroundedResponder(caller, max_repairs=args.max_repairs).respond(msgs)
        g = grounded["grounding"]
        final_ok = bool(grounded["content"]) and (
            g.get("model_passed") or (g.get("fallback_gate") or {}).get("passed", False))
        rows.append({
            "id": cid,
            "bare": bare_verdict(prompt, bare_txt),
            "bare_official": _official_cross_check(cid, bare_txt),
            "bare_text": bare_txt,
            "grounded_source": g.get("source"),
            "grounded_model_passed": g.get("model_passed"),
            "grounded_final_passed": final_ok,
            "grounded_official": _official_cross_check(cid, grounded["content"]),
            "attempts": g.get("attempts"),
            "grounded_content": grounded["content"],
        })
        print(f"{cid:22s} bare={rows[-1]['bare'].get('passed')} grounded={g.get('source')} final={final_ok}")

    drift = ident.drift()
    tag_digest_after = _ollama_tag_digest(args.tag)
    if tag_digest_before and tag_digest_after and tag_digest_before != tag_digest_after:
        drift.append(f"/api/tags digest moved: {tag_digest_before[:12]} -> {tag_digest_after[:12]}")
    n = len(rows)
    n_valid_bare = sum(1 for r in rows if r["bare"]["passed"] is not None)
    basis = "measured"
    if busy:
        basis = "partial"
    if drift:
        basis = "voided"
    if n_valid_bare < n or len(transport) > 0.05 * max(1, n * (args.max_repairs + 2)):
        basis = "partial" if basis == "measured" else basis
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": ident.run_id,
        "tag": args.tag,
        "ollama_tags_digest": tag_digest_after,
        "official_grader_sha256": getattr(official_grader, "GRADER_SHA256", None),
        "official_measurement_version": getattr(official_grader, "MEASUREMENT_VERSION", None),
        "artifact": ident.artifacts.get(args.tag),
        "ruler": ident.ruler,
        "basis": basis,
        "chain_busy_at_start": busy,
        "drift": drift,
        "transport_errors": transport,
        "n": n,
        "summary": {
            "bare_model_passed": sum(1 for r in rows if r["bare"]["passed"]),
            "bare_n_valid": n_valid_bare,
            "grounded_model_passed": sum(1 for r in rows if r["grounded_model_passed"]),
            "grounded_fallback_used": sum(1 for r in rows if r["grounded_source"] not in ("model", None)),
            "grounded_final_passed": sum(1 for r in rows if r["grounded_final_passed"]),
            "note": "fallback 是确定性兜底，不计入模型能力（测评法律第四条）",
        },
        "rows": rows,
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False), "basis=", basis, "->", out_dir / "report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
