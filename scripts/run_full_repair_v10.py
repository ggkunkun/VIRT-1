#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical v10 local QLoRA orchestrator on top of v7-repair (2026-11-18).

Exclusive GPU & commit guard -> rematerialize v7-repair merged_hf if needed
-> train v10 (163 balanced gate-clean rows, lr=5e-5, 1 epoch) -> merge + Q4_0 GGUF
-> Ollama create virtu-six-software:v10-repair -> 3 consecutive exclusive verify
rounds + G71 semantic gate + 2 generalization probes -> FULL_REPAIR_V10_2026-11-18.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))

import run_full_repair_v9 as v9  # noqa: E402
import deploy_trained_adapter as grader  # noqa: E402
from g71_semantic_check import check_g71_step_shaft  # noqa: E402

LOG = ROOT / "runs" / "full_repair_v10_20261118"
LOG.mkdir(parents=True, exist_ok=True)
v9.LOG = LOG

V3_BASE = ROOT / "checkpoints" / "_deploy_six_software_v3" / "merged_hf"
V7_LORA = ROOT / "checkpoints" / "six_software_v7_repair_lora"
V7_BASE = ROOT / "checkpoints" / "_deploy_six_v7_repair" / "merged_hf"
DATA = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v10_repair_sft.jsonl"
OUT_LORA = ROOT / "checkpoints" / "six_software_v10_repair_lora"
DEPLOY_DIR = ROOT / "checkpoints" / "_deploy_six_v10_repair"
GGUF = DEPLOY_DIR / "virtu-six-software_v10.q4_0.gguf"
TAG = "virtu-six-software:v10-repair"


def main() -> int:
    if not v9.wait_exclusive():
        return 1

    if not (V7_BASE / "config.json").is_file():
        v9.log(f"Materializing v7 base: {V7_BASE}")
        if not (V3_BASE / "config.json").is_file() or not (V7_LORA / "adapter_model.safetensors").is_file():
            v9.log("[FATAL] Missing v3 merged_hf or v7 LoRA adapter")
            return 2
        if not v9.run(
            [str(v9.PY), "scripts/merge_numpy.py", "--base", str(V3_BASE), "--lora", str(V7_LORA), "--weight", "1.0", "--mode", "delta", "--out", str(V7_BASE)],
            "merge_v7_base.log", 3600,
        ):
            v9.log("[FATAL] failed to materialize v7 merged_hf base")
            return 2

    if not v9.free_ollama_ram():
        v9.log("[FATAL] cannot free ollama host RAM before training")
        return 3

    v9.log("=== STEP 2 v10 QLoRA 训练 (base=v7-repair, 163 clean rows, lr=5e-5) ===")
    if not v9.run(
        [
            str(v9.PY), "scripts/train_vericut_local_qlora.py",
            "--base", str(V7_BASE), "--data", str(DATA), "--out", str(OUT_LORA),
            "--epochs", "1", "--max-length", "640", "--grad-accum", "4",
            "--lr", "5e-5", "--save-every", "15", "--dev-max-items", "24", "--resume",
        ],
        "train_v10.log", 7200,
    ):
        v9.log("[FATAL] v10 training failed")
        return 3
    receipt = OUT_LORA / "training_receipt.json"
    if not receipt.is_file() or json.loads(receipt.read_text(encoding="utf-8")).get("status") != "COMPLETED":
        v9.log("[FATAL] v10 training receipt not COMPLETED")
        return 4

    v9.log("=== STEP 3 合并/量化/部署 ===")
    if not v9.run(
        [str(v9.PY), "scripts/merge_numpy.py", "--base", str(V7_BASE), "--lora", str(OUT_LORA), "--mode", "delta", "--out", str(DEPLOY_DIR / "merged_hf")],
        "merge_v10.log", 3600,
    ):
        return 5
    if not v9.run(
        [str(v9.PY), "scripts/hf_to_gguf_numpy.py", "--model", str(DEPLOY_DIR / "merged_hf"), "--out", str(GGUF), "--dtype", "q4_0"],
        "gguf_v10.log", 3600,
    ):
        return 6

    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    modelfile = DEPLOY_DIR / "Modelfile"
    modelfile.write_text(v9.build_modelfile(GGUF), encoding="utf-8")
    if not v9.run(["ollama", "create", TAG, "-f", str(modelfile)], "ollama_create_v10.log", 1800):
        return 7

    import urllib.request
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with op.open("http://127.0.0.1:11434/api/tags", timeout=15) as resp:
        tags = {m["name"]: m["digest"] for m in json.loads(resp.read()).get("models", [])}
    if TAG not in tags:
        v9.log(f"[FATAL] tag {TAG} absent from /api/tags")
        return 7
    v9.log(f"deployed {TAG} digest={tags[TAG][:16]}")

    v9.log("=== STEP 4 v10 独占验收 3 轮 ===")
    for rnd in (1, 2, 3):
        if not v9.verify_capture(TAG, rnd):
            v9.log(f"[FATAL] v10 verify failed r{rnd}")
            return 8
        time.sleep(5)

    v9.log("=== STEP 5 汇总报告 ===")
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tag": TAG,
        "digest": tags[TAG],
        "basis": "measured",
        "corpus_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
        "rounds": [],
    }
    v10_rounds = []
    for p in sorted(LOG.glob("verify_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        g71_full = (d.get("detail") or {}).get("fanuc_g71_safety_probe", {}).get("full_response", "")
        g71_sem = check_g71_step_shaft(g71_full) if g71_full else {"passed": False, "violations": ["no_full_response"]}
        row_out = {
            "tag": d["tag"],
            "round": d["round"],
            "passed": d["passed"],
            "total": d["total"],
            "failed": d["failed"],
            "g71_semantic_passed": bool(g71_sem.get("passed")),
            "g71_semantic_violations": g71_sem.get("violations", []),
        }
        summary["rounds"].append(row_out)
        if d["tag"] == TAG:
            v10_rounds.append(row_out)

    r_lame = grader._probe_chat(
        TAG,
        [{"role": "user", "content": "按 Lamé 厚壁圆筒理论：内径 Di=50 mm，外径 Do=100 mm，内压 Pi=24 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"}],
        num_predict=420, keep_alive="180s", think=False,
    )
    vis_lame = grader._strip_think_blocks(str((r_lame.get("message") or {}).get("content", "")))
    nums_lame = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", vis_lame)]
    gen_lame_ok = any(abs(v - 40.0) <= 0.15 for v in nums_lame) and bool(re.search(r"(?:-|\u2212|\uff0d)\s*24(?:\.0+)?(?!\d|\.\d)", vis_lame))

    r_g71 = grader._probe_chat(
        TAG,
        [{"role": "user", "content": "用 FANUC ISO/G 格式为 Ø80 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø46 长 25 mm，总长 60 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。"}],
        num_predict=420, keep_alive="180s", think=False,
    )
    vis_g71 = grader._strip_think_blocks(str((r_g71.get("message") or {}).get("content", "")))
    tok_g71 = grader.evaluate_fanuc_g71_safety_probe(vis_g71)
    up_g71 = vis_g71.upper()
    gen_g71_ok = bool(tok_g71.get("passed")) and all(
        bool(re.search(pat, up_g71))
        for pat in (r"X\s*46(?:\.0*)?", r"X\s*80(?:\.0*)?", r"Z\s*-25(?:\.0*)?", r"Z\s*-60(?:\.0*)?")
    )

    worst = min(v10_rounds, key=lambda r: (r["passed"], 1 if r["g71_semantic_passed"] else 0)) if v10_rounds else {}
    summary["gate"] = {
        "rule": "连测最差值做门禁 (project §8.2) + G71 语义门",
        "v10_rounds_passed": [r["passed"] for r in v10_rounds],
        "v10_g71_semantic_passed": [r["g71_semantic_passed"] for r in v10_rounds],
        "worst_passed": worst.get("passed"),
        "worst_total": worst.get("total"),
        "worst_round": worst.get("round"),
        "worst_failed": worst.get("failed"),
    }
    summary["generalization"] = {
        "gen_lame_Di50_Do100_Pi24": {"passed": gen_lame_ok, "sample": vis_lame[:220]},
        "gen_g71_D80_d46_L25_T60": {"passed": gen_g71_ok, "token_gate": tok_g71.get("passed"), "sample": vis_g71[:280]},
    }
    out_report = ROOT / "reports" / "FULL_REPAIR_V10_2026-11-18.json"
    out_report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    v9.free_ollama_ram()
    v9.log(f"[DONE] 报告已落盘 {out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
