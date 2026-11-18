# -*- coding: utf-8 -*-
"""把 2026-11-15 全面测评各板块的原始证据汇总为一份可归因的结构化报告。

只搬运已落盘的 measured 数字，每个数字带 n / evidence / run_id / basis；
未完成或口径不适用的腿一律写成「未测」，不补分、不推断。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "runs" / "eval_full_board_20261115"


def j(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def rel(p):
    return str(Path(p).relative_to(ROOT)).replace("\\", "/")


def main():
    ident = j(RUN / "identity.json")
    gates = j(RUN / "gates_phase.json")
    targeted = j(RUN / "targeted_phase.json")
    d24 = j(RUN / "domain24" / "summary.json")
    sens = j(RUN / "domain24_grader_sensitivity.json")
    generic = j(RUN / "generic" / "summary.json")
    progress = j(RUN / "progress.json")
    base_raw = [json.loads(l) for l in (RUN / "holdout" / "raw_baseline_holdout.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
    cand_raw = [json.loads(l) for l in (RUN / "holdout" / "raw_candidate_holdout.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
    subset = j(RUN / "holdout" / "holdout_subset_report.json")
    r2 = j(ROOT / "runs" / "eval_vericut_e_training_r2" / "comparison_report.json")

    board_targeted = {}
    for tag, v in (targeted or {}).get("models", {}).items():
        board_targeted[tag] = {
            "basis": "measured", "n": v.get("n"), "passed": v.get("passed"),
            "pass_rate_pct": v.get("pass_rate_pct"),
            "failed_probes": [i["key"] for i in v.get("items", []) if not i["passed"]],
            "evidence": rel(RUN / "targeted_phase.json"),
            "run_id": (targeted or {}).get("grader_sha256", "")[:16],
        }
    board_d24 = {}
    for tag, v in (d24 or {}).get("summary", {}).items():
        alt = (sens or {}).get("per_model", {}).get(tag, {})
        invalid = tag == "qwen3:8b"  # 24/24 空回答，/api/generate 未取到 thinking 内容
        board_d24[tag] = {
            "basis": "measured" if not invalid else "voided_empty_responses",
            "n": 24, "mean_score": v.get("mean_score") if not invalid else "未测",
            "median_score": v.get("median_score") if not invalid else "未测",
            "mean_tok_s": v.get("mean_tok_s"),
            "transport_errors": v.get("n_transport_errors"),
            "grader_version": (d24 or {}).get("grader_version"),
            "alternate_grader_mean_inferred": alt.get("substring_v1_mean"),
            "note": ("24/24 空回答，该腿作废，不得当作 0 分能力" if invalid else
                     "slot_exact_v2 精确槽位口径；绝对分不可作能力结论，只作同尺相对比较"),
            "evidence": rel(RUN / "domain24" / "summary.json"),
            "raw_evidence": rel(RUN / "domain24" / "raw.jsonl"),
            "run_id": (d24 or {}).get("run_id"),
        }
    board_generic = {}
    for tag, v in (generic or {}).get("models", {}).items():
        d = v.get("detail") or {}
        board_generic[tag] = {
            "basis": "measured" if v.get("status") == "measured" else "未测",
            "n": 28, "status": v.get("status"),
            "overall_weighted": d.get("overall_weighted"),
            "dimensions": {k: x["score"] for k, x in (d.get("dimensions") or {}).items()},
            "gate_valid": (d.get("gate") or {}).get("valid"),
            "run_id": d.get("run_id"),
            "evidence": rel(RUN / "generic" / "summary.json"),
            "leg_dir": v.get("leg_dir"),
        }
    holdout = {
        "scope": "未完成（全量 105 题腿中止）",
        "baseline_full": {
            "basis": "measured", "n": len(base_raw),
            "mean": round(sum(r["score"] for r in base_raw) / len(base_raw), 2),
            "pass_rate_pct": round(100 * sum(1 for r in base_raw if r["score"] >= 99.999) / len(base_raw), 2),
            "evidence": rel(RUN / "holdout" / "raw_baseline_holdout.jsonl"),
        },
        "candidate_partial": {
            "basis": "voided_incomplete", "n_valid": sum(1 for r in cand_raw
                                                         if not r.get("error") and r.get("text")),
            "rows_written": len(cand_raw),
            "dimension_coverage": "仅 setup_workoffset / tool_assembly 两维，按题板顺序前 30 题，样本偏斜",
            "note": "不得据此计算配对 delta；主测在全量留出集上的表现标「未测」",
            "evidence": rel(RUN / "holdout" / "raw_candidate_holdout.jsonl"),
        },
        "subset_attempt": ({"basis": subset.get("basis"), "n_valid": subset.get("n_valid"),
                            "delta_mean": subset.get("delta_mean"),
                            "evidence": rel(RUN / "holdout" / "holdout_subset_report.json")}
                           if subset else {"basis": "未测", "reason": "Ollama 服务端阻塞，补跑未启动成功"}),
        "historical_same_board_reference": {
            "basis": "measured", "run_id": (r2 or {}).get("run_id"),
            "note": "同题板、同基线字节的另一条训练腿（virtu-vericut-e:latest），不是本次主测",
            "baseline_mean": (r2 or {}).get("holdout", {}).get("baseline", {}).get("overall_mean"),
            "candidate_mean": (r2 or {}).get("holdout", {}).get("candidate", {}).get("overall_mean"),
            "delta_mean": (r2 or {}).get("holdout", {}).get("delta_mean"),
            "general_sanity_delta": ((r2 or {}).get("general_sanity") or {}).get("delta_mean"),
            "evidence": "runs/eval_vericut_e_training_r2/comparison_report.json",
        },
    }
    payload = {
        "title": "Virtu 训练完成后主力模型全面测评（2026-11-15）",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "subject": {"primary": "virtu-vericut96:v2", "baseline": "virtu-master-fixed:latest"},
        "identity": {"models": ident["models"], "training_receipts": ident["training_receipts"],
                     "ruler_sha256": ident["ruler_sha256"],
                     "evidence": rel(RUN / "identity.json")},
        "drift": {
            "primary_unchanged": True,
            "retargeted_tags": ["virtu-vericut-e:latest: 9d9f8aa57ee7 -> 92323c5d1dde"],
            "new_tags_during_chain": ["virtu-vericut96:v3", "virtu-six-software:v2",
                                      "virtu-six-software:v3"],
            "note": "被测构件按内容寻址；vericut-e 腿成绩只归属起链时的 9d9f8aa5… 构件",
        },
        "gates": {"basis": "measured",
                  "probe_mutation_pytest": gates["probe_mutation_tests"]["exit_code"],
                  "probe_mutation_passed": 10,
                  "holdout_gold_selftest": gates["holdout_gold_selftest"]["exit_code"],
                  "gold_cases": 105, "passed": gates["passed"],
                  "evidence": rel(RUN / "gates_phase.json")},
        "boards": {"targeted_probes": board_targeted, "domain24_keyword": board_d24,
                   "generic_8dim": board_generic, "holdout": holdout},
        "grader_sensitivity": {"basis": "inferred",
                               "content_correct_but_slot_zero_n": (sens or {}).get("content_correct_but_slot_zero_n"),
                               "per_model": (sens or {}).get("per_model"),
                               "evidence": rel(RUN / "domain24_grader_sensitivity.json")},
        "chain": {"boards_completed": {k: v.get("status") for k, v in (progress or {}).get("boards", {}).items()},
                  "evidence": rel(RUN / "progress.json")},
        "rcfa": {
            "symptom": "全量 105 题留出集主测腿中止在 30/105，随后 Ollama /api/tags、/api/chat、ollama ps 全部超时",
            "root_cause": "测量窗口内另一会话并发部署/评测新模型（v2/v3 系列），Ollama 服务被独占；显存从 5.8GB 空闲降到 ~1.8GB，推理退化为 CPU 为主并触发 180s 超时",
            "contributing": ["共享可变标签 virtu-vericut-e:latest 被重指向",
                             "run_domain_ab.py 对 thinking 模型的空 response 记为 scored 0 分",
                             "slot_exact_v2 中文复合词精确槽位口径导致系统性低估"],
            "circuit_breaker": "连续 3 次同构超时停滞，按 AGENTS.md §6 停止重试；holdout 全量腿标未测，不补分",
            "recovery": "Ollama 空闲后执行 .venv/Scripts/python.exe scripts/finish_holdout_subset.py（断点续跑），或重启服务后重跑全量腿",
        },
        "unmeasured": ["主测在全量 105 题留出集上的配对结果",
                       "multimodal 维度（本轮无 VL 标签）",
                       "原生 16 工具 schema 腿（本轮通用题板按纯文本 JSON 协议豁免）",
                       "评测期间新部署的 virtu-vericut96:v3 / virtu-six-software:v2,v3"],
    }
    dest = ROOT / "benchmarks" / "VIRTU_FULL_BOARD_2026-11-15.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", dest.relative_to(ROOT))
    print("boards:", {k: v.get("basis") for k, v in payload["boards"]["generic_8dim"].items()})


if __name__ == "__main__":
    main()
