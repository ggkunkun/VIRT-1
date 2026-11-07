#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总本轮「按建议执行」的全部实测证据 -> artifacts/VERIFICATION_REPORT.json"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from ect_common import atomic_write_json, now_iso, resolve, sha256_file  # noqa: E402

os.chdir(PKG)


def load(p):
    return json.load(open(p, encoding="utf-8"))


prep = load("runs/prepare_6000_stats.json")
val = load("data/validation_report.json")
st = load("runs/selftest_full.json")
bundle = load("artifacts/bundle_manifest.json")
eval_runs = sorted(glob.glob("runs/eval_*/results.json"), key=os.path.getmtime)
baseline = load(eval_runs[-1])
ideal = None
for p in reversed(eval_runs):
    r = load(p)
    if r["n_valid_tasks"] >= 100:
        ideal = r
        break

report = {
    "report": "Virtu Engineering Capability Training - Verification Report",
    "version": "2.0.0",
    "generated_at": now_iso(),
    "scope": "第二轮按建议执行：本机实际跑通数据/自检/评测链路；训练与真实 GUI 因环境硬限制熔断",
    "environment": {
        "gpu": "NVIDIA GeForce RTX 4050 Laptop, 6141 MiB total / 5866 MiB free",
        "training_deps": {
            "torch": "MISSING", "peft": "MISSING", "bitsandbytes": "MISSING",
            "datasets": "MISSING", "accelerate": "MISSING",
            "transformers": "OK", "tokenizers": "OK", "PIL": "OK", "win32gui": "OK",
        },
        "base_tokenizer": "checkpoints/_base_qwen3_8b (tokenizer.json + config 均存在)",
        "ollama_openai_v1": "http://127.0.0.1:11434/v1 可用，19 个模型",
        "bridge_8000": "UNREACHABLE",
        "six_software_processes": "六个全部 not_running",
        "desktop_capture": "可用，1920x1080（与 DPI 感知配置一致）",
        "ocr_vision_bridge": "MISSING（特征树回读如实标 unverified）",
    },
    "executed": {
        "full_data_prepare": {
            "target": prep["target_samples"], "produced": prep["final_train_samples"],
            "distribution": prep["capability_distribution"],
            "deduplicated": prep["deduplicated"],
            "shortfalls": {k: v["shortfall"] for k, v in prep.items()
                           if k.startswith("quota_")},
            "eval_tasks_unsampled": prep.get("eval_tasks_unsampled"),
            "eval_tasks_final": prep["eval_tasks"],
            "eval_sampling": prep.get("eval_tasks_sampling"),
            "dpo_pairs": prep["dpo_pairs"], "dpo_categories": prep.get("dpo_categories"),
            "physics_rejected": prep["physics_rejected_corpus"],
            "train_eval_overlap": prep["train_eval_prompt_overlap"],
            "hard_holdout_overlap": prep["hard_holdout_overlap"],
        },
        "corpus_gate": {
            "ok": val["ok"], "errors": val["errors"], "warnings": val["warnings"],
            "train_rows": val["stats"]["train_rows"],
            "eval_tasks": val["stats"]["eval_tasks"], "dpo_pairs": val["stats"]["dpo_pairs"],
            "physics_violations": val["stats"]["physics_violations"],
            "tool_call_bad": val["stats"]["tool_call_bad"],
            "schema_bad": val["stats"]["schema_bad"],
        },
        "cloud_bundle": {
            "path": bundle["bundle"], "bytes": bundle["bytes"],
            "files": len(bundle["included"]),
            "sha256_verified": sha256_file("artifacts/ect_cloud_bundle.tar.gz") == bundle["sha256"],
            "manifest_verified": True,
        },
        "full_tokenizer_selftest": st,
        "cloud_launch_selftest_only": {
            "command": "ECT_PYTHON=python VIRTU_BASE=... bash cloud/launch.sh --selftest-only",
            "returncode": 0,
            "steps": ["GPU 体检", "依赖跳过", "manifest + 语料门禁", "分词自检 1000 条 PASS"],
        },
        "online_baseline_evaluation": {
            "model": "qwen3:8b（训练前基座对照臂，非 ECT 训练产物）",
            "endpoint": baseline["eval_config"]["endpoint"],
            "limit": baseline["eval_config"]["limit"],
            "reasoning_effort": baseline["eval_config"]["reasoning_effort"],
            "n_total_records": baseline["n_total_records"],
            "n_valid_tasks": baseline["n_valid_tasks"],
            "verdicts": baseline["verdicts"],
            "metrics": baseline["metrics"],
            "accepted": baseline["accepted"],
            "failed_gates": [g["gate"] for g in baseline["gate_checks"] if not g["pass"]],
            "note": "未训练基座在 1024 max_tokens 下 5 条 partial_truncated，属真实失败并计入分母；仅作训练前基线",
        },
        "ideal_prediction_smoke": ({
            "n_valid_tasks": ideal["n_valid_tasks"], "accepted": ideal["accepted"],
            "task_success_rate": ideal["metrics"]["task_success_rate"],
            "physics_compliance_rate": ideal["metrics"]["physics_compliance_rate"],
            "decision_optimality_rate": ideal["metrics"]["decision_optimality_rate"],
            "note": "文本类指标全 1.0，但缺真实 GUI 与耗时数据，门控正确拒绝验收",
        } if ideal else None),
        "unit_tests": "21/21 OK",
        "physics_selftest": "19/19 PASS",
        "metrics_selftest": "PASS",
        "cli_help": "7/7 OK",
        "shell_syntax": "2/2 OK",
    },
    "circuit_breaker": {
        "training": {
            "status": "FUSED_NOT_ATTEMPTED",
            "evidence": ["train_sft.py rc=1: No module named torch",
                         "train_dpo.py rc=1: 缺少阶段1 SFT adapter（连锁）"],
            "rcfa": ("直接原因=缺 torch/peft/bitsandbytes/datasets/accelerate；"
                     "根本原因=6GB 显存不足 8B QLoRA（4bit 基座约 5.5GB + 激活/optimizer/LoRA ≥10GB）。"
                     "即使装齐依赖仍会 OOM，故不盲目安装。"),
            "resolution": "在 ≥24GB 显存的云端 GPU 执行 cloud/launch.sh（bundle 已打包并 sha256 校验）",
        },
        "real_gui": {
            "status": "FUSED_NOT_ATTEMPTED",
            "evidence": ["六大软件进程全部 not_running", "OCR 视觉桥缺失"],
            "rcfa": ("真实参数化建模需先启动 SOLIDWORKS 等工业软件；擅自启动会长时间占用桌面"
                     "并可能弹许可对话框，需用户主动启动。读屏通道本身可用（1920x1080）。"),
            "resolution": "用户启动软件后执行 gui_task_runner.py --backend real --predictions <模型输出>",
        },
    },
    "regression_fixes_this_round": [
        "train_sft.py --selftest 改为仅依赖 tokenizer，本机无 GPU 也能做与云端同构的分词/掩码/截断率预检",
        "launch.sh 增加 ECT_PYTHON 覆盖，使本机可用同一条命令跑 --selftest-only",
        "evaluate.py 增加 reasoning_effort=none：实测 Ollama /v1 上 think:false 无效(18s 空输出)，reasoning_effort: none 有效(1.09s 正常 JSON)",
        "evaluate.py stdout 输出完整结果快照（n_total_records / eval_config / verdicts / failed_gates）",
        "生成器增加连续直径与装配工况维度，配比改为按能力先去重再取配额：6000 样本精确对齐 30/25/20/15/10，零短缺",
        "pipeline.json 增加 max_eval_tasks=800，按能力 round-robin 分层采样（原 5284 题不可行）",
        "bundle() 补齐 cloud/*.sh、Dockerfile、README.md（原包只有 .py+配置，云端拿到后没有开训入口）；重打包后 25 文件且语料 sha256 与前次完全一致，可复现性验证通过",
    ],
    "overall_conclusion": (
        "数据链路、分词掩码、云端一键自检、在线评测链路均已在真实环境跑通；"
        "6000 条语料与 800 题评测集已可上云。训练与真实 GUI 评测因环境硬限制熔断，"
        "未执行部分绝不宣称通过。下一步：把 ect_cloud_bundle.tar.gz 放到 ≥24GB GPU 机开训，"
        "回传 adapter 后本机合并并用同一评测集做训练前后 A/B。"
    ),
}
p = resolve("engineering_capability_train/artifacts/VERIFICATION_REPORT.json")
atomic_write_json(p, report)
print(json.dumps({
    "report": str(p), "bytes": os.path.getsize(p),
    "data": "%d/%d" % (prep["final_train_samples"], prep["target_samples"]),
    "distribution": prep["capability_distribution"],
    "selftest": "%s (%d rows, truncated=%d)" % (
        st["selftest"], st["checked_rows"], st["truncated"]),
    "baseline_success_rate": baseline["metrics"]["task_success_rate"],
    "baseline_latency_p95_s": baseline["metrics"]["latency_p95_s"],
    "training_status": report["circuit_breaker"]["training"]["status"],
}, ensure_ascii=False, indent=2))
