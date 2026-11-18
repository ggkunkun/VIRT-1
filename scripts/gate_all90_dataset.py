#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/gate_all90_dataset.py — Virtu All-90 训练数据 8 道硬门禁与可证伪变异探针

8 道自动化门禁：
  Gate 1: Schema & 真实工具面 Lint (CADCAM_TOOLS_DEFINITION + desktop_* / corpus_tool_map)
  Gate 2: System Prompt 字节预算 <= 702B 且禁止答案/数值作弊泄题
  Gate 3: Benchmark 去污染审计 (virtu_eval.contamination_check.assert_no_leak + extra holdout)
  Gate 4: 物理量纲单位审计 (scripts.corpus_unit_audit.assert_units_clean)
  Gate 5: 权威物理/几何公式重算校验 (scripts.wm_verifier.recompute & 文本自洽检查)
  Gate 6: 六大软件覆盖均衡性与派生溯源凭证校验 (source_run_id / evidence_sha256 / 派生倍数<=3)
  Gate 7: SHA256 Ledger 账本签发与比对
  Gate 8: 可证伪 +5% 数值变异探针 (植入坏样本必须拦截，禁止空转放行)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from virtu_eval.contamination_check import assert_no_leak, scan_corpus
from virtu_eval.tool_schema import runtime_tool_names, runtime_tools
from corpus_unit_audit import assert_units_clean
from wm_verifier import recompute as wm_recompute

SIX_SOFTWARES = ("solidworks", "nx", "autocad", "cimco", "vericut", "sscnc")
SYSTEM_PROMPT_MAX_BYTES = 702
NUMERIC_TOL_REL = 0.02
NUMERIC_TOL_ABS = 1e-3

ANSWER_LEAK_PATTERNS = (
    re.compile(r"(?i)\b(?:ground_truth|expected_answer|gold_output)\b\s*[:=]"),
    re.compile(r"(?i)<answer>\s*\{.*?\}\s*</answer>"),
)

_TOOL_CALL_TAG_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_known_tool_names() -> Set[str]:
    names: Set[str] = set(runtime_tool_names())
    try:
        from bridges.tool_calling_specs import get_cadcam_tool_definitions
        for t in get_cadcam_tool_definitions():
            fn = (t.get("function") or {}).get("name") if isinstance(t, dict) else None
            if fn:
                names.add(fn)
    except Exception:
        pass
    return names


def _extract_tool_invocations(rec: Dict[str, Any]) -> List[Tuple[str, Any]]:
    invocations: List[Tuple[str, Any]] = []
    for t in rec.get("tools") or []:
        if isinstance(t, dict):
            fn = t.get("function") if "function" in t else t
            if isinstance(fn, dict) and fn.get("name"):
                invocations.append((str(fn["name"]), fn.get("parameters", {})))
    for msg in rec.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        for tc in msg.get("tool_calls") or []:
            if isinstance(tc, dict):
                fn = tc.get("function") if "function" in tc else tc
                name = fn.get("name") if isinstance(fn, dict) else None
                args = fn.get("arguments") if isinstance(fn, dict) else None
                if name:
                    invocations.append((str(name), args))
        content = str(msg.get("content") or "")
        for m in _TOOL_CALL_TAG_RE.finditer(content):
            raw_json = m.group(1)
            try:
                obj = json.loads(raw_json)
            except Exception as exc:
                invocations.append(("__INVALID_TOOL_JSON__", str(exc)))
                continue
            if isinstance(obj, dict) and obj.get("name"):
                invocations.append((str(obj["name"]), obj.get("arguments", {})))
            else:
                invocations.append(("__MISSING_TOOL_NAME__", raw_json))
    return invocations


def gate_schema_and_tools(rows: List[Dict[str, Any]], known_tools: Optional[Set[str]] = None) -> Dict[str, Any]:
    known = known_tools if known_tools is not None else load_known_tool_names()
    errors: List[str] = []
    valid_roles = {"system", "user", "assistant", "tool"}
    tool_calls_checked = 0

    for idx, rec in enumerate(rows):
        msgs = rec.get("messages")
        if not isinstance(msgs, list) or not msgs:
            errors.append(f"row {idx}: missing/empty messages")
            continue
        has_asst = False
        for m_idx, m in enumerate(msgs):
            if not isinstance(m, dict) or m.get("role") not in valid_roles:
                errors.append(f"row {idx} msg {m_idx}: invalid role {m.get('role') if isinstance(m, dict) else type(m)}")
            elif m.get("role") == "assistant":
                has_asst = True
        if not has_asst:
            errors.append(f"row {idx}: no assistant turn")

        for name, args in _extract_tool_invocations(rec):
            tool_calls_checked += 1
            if name not in known:
                errors.append(f"row {idx}: unknown tool {name!r}")
                continue
            if isinstance(args, str):
                try:
                    json.loads(args)
                except Exception as exc:
                    errors.append(f"row {idx}: invalid JSON args for {name}: {exc}")

    return {
        "gate": "gate_1_schema_and_tools",
        "passed": len(errors) == 0,
        "rows": len(rows),
        "tool_calls_checked": tool_calls_checked,
        "errors": errors[:20],
    }


def gate_system_prompt_budget_and_leak(rows: List[Dict[str, Any]], max_bytes: int = SYSTEM_PROMPT_MAX_BYTES) -> Dict[str, Any]:
    errors: List[str] = []
    max_seen_bytes = 0
    for idx, rec in enumerate(rows):
        for m in rec.get("messages") or []:
            if isinstance(m, dict) and m.get("role") == "system":
                txt = str(m.get("content") or "")
                b = len(txt.encode("utf-8"))
                max_seen_bytes = max(max_seen_bytes, b)
                if b > max_bytes:
                    errors.append(f"row {idx}: system prompt {b}B > {max_bytes}B")
                for pat in ANSWER_LEAK_PATTERNS:
                    if pat.search(txt):
                        errors.append(f"row {idx}: suspicious answer leak pattern {pat.pattern!r} in system prompt")
    return {
        "gate": "gate_2_system_prompt_budget",
        "passed": len(errors) == 0,
        "max_bytes_seen": max_seen_bytes,
        "limit_bytes": max_bytes,
        "errors": errors[:20],
    }


def gate_eval_contamination(
    dataset_path: str | Path,
    eval_dir: Optional[str | Path] = None,
    holdout_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    try:
        assert_no_leak(str(dataset_path), eval_dir=str(eval_dir) if eval_dir else None)
    except SystemExit as exc:
        errors.append(f"assert_no_leak failed: {exc}")
    except Exception as exc:
        errors.append(f"assert_no_leak error: {exc}")

    if holdout_path and Path(holdout_path).exists():
        # Check exact normalized user query overlap against extra holdout benchmark file
        holdout_prompts: Set[str] = set()
        with open(holdout_path, "r", encoding="utf-8") as hf:
            for line in hf:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                q = str(obj.get("prompt") or obj.get("question") or "").strip().lower()
                if not q and isinstance(obj.get("messages"), list):
                    for m in obj["messages"]:
                        if m.get("role") == "user":
                            q = str(m.get("content") or "").strip().lower()
                            break
                if len(q) >= 12:
                    holdout_prompts.add(re.sub(r"\s+", " ", q))
        with open(dataset_path, "r", encoding="utf-8") as df:
            for idx, line in enumerate(df):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                for m in obj.get("messages") or []:
                    if m.get("role") == "user":
                        uq = re.sub(r"\s+", " ", str(m.get("content") or "").strip().lower())
                        if uq in holdout_prompts:
                            errors.append(f"row {idx}: exact prompt overlap with holdout {holdout_path}")
    return {
        "gate": "gate_3_eval_contamination",
        "passed": len(errors) == 0,
        "errors": errors[:20],
    }


def gate_physical_units(dataset_path: str | Path) -> Dict[str, Any]:
    errors: List[str] = []
    try:
        assert_units_clean(str(dataset_path))
    except SystemExit as exc:
        errors.append(f"assert_units_clean failed: {exc}")
    except Exception as exc:
        errors.append(f"assert_units_clean error: {exc}")
    return {
        "gate": "gate_4_physical_units",
        "passed": len(errors) == 0,
        "errors": errors[:20],
    }


def _extract_claimed_dict(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if isinstance(rec.get("physics_claim"), dict):
        return rec["physics_claim"]
    if isinstance(rec.get("expected"), dict):
        return rec["expected"]
    for m in reversed(rec.get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "assistant":
            txt = str(m.get("content") or "").strip()
            if txt.startswith("{") and txt.endswith("}"):
                try:
                    parsed = json.loads(txt)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
    return None


def _close_enough(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=NUMERIC_TOL_REL, abs_tol=NUMERIC_TOL_ABS)
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return all(_close_enough(a, b) for a, b in zip(actual, expected))
    return actual == expected


def gate_physics_recompute(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    checked = 0

    for idx, rec in enumerate(rows):
        claim = _extract_claimed_dict(rec)
        # 1. Structured wm_verifier spec check
        if isinstance(rec.get("wm_sample"), dict):
            checked += 1
            ref = wm_recompute(rec["wm_sample"])
            if not claim:
                errors.append(f"row {idx}: wm_sample present but assistant/expected claim missing")
                continue
            for k, exp_v in ref.items():
                if k in claim and not _close_enough(claim[k], exp_v):
                    errors.append(f"row {idx}: physics mismatch key={k} actual={claim[k]!r} expected={exp_v!r}")
        elif claim and all(k in claim for k in ("yield_strength_mpa", "peak_von_mises_mpa", "safety_factor")):
            checked += 1
            sy = float(claim["yield_strength_mpa"])
            sig = float(claim["peak_von_mises_mpa"])
            if sig > 0:
                exp_fos = sy / sig
                if not _close_enough(float(claim["safety_factor"]), exp_fos):
                    errors.append(
                        f"row {idx}: safety_factor={claim['safety_factor']} != Sy/sigma={exp_fos:.4f}"
                    )
                if "fos_gate" in claim:
                    exp_gate = "pass" if exp_fos >= 1.5 else "fail"
                    if claim["fos_gate"] != exp_gate:
                        errors.append(f"row {idx}: fos_gate={claim['fos_gate']!r} != expected {exp_gate!r}")

    return {
        "gate": "gate_5_physics_recompute",
        "passed": len(errors) == 0,
        "physics_rows_checked": checked,
        "errors": errors[:20],
    }


def gate_coverage_and_provenance(
    rows: List[Dict[str, Any]],
    min_per_software: int = 0,
    require_provenance: bool = False,
    max_derive_ratio: int = 3,
) -> Dict[str, Any]:
    errors: List[str] = []
    sw_counts: Counter = Counter()
    source_counts: Counter = Counter()

    for idx, rec in enumerate(rows):
        sw = str(rec.get("software") or "").strip().lower()
        if not sw:
            txt = json.dumps(rec, ensure_ascii=False).lower()
            for candidate in SIX_SOFTWARES:
                if candidate in txt:
                    sw = candidate
                    break
        if sw in SIX_SOFTWARES:
            sw_counts[sw] += 1

        if require_provenance:
            prov = rec.get("provenance") if isinstance(rec.get("provenance"), dict) else {}
            src_id = rec.get("source_run_id") or prov.get("source_run_id")
            ev_sha = rec.get("evidence_sha256") or prov.get("evidence_sha256")
            if not src_id or not ev_sha:
                errors.append(f"row {idx}: missing provenance source_run_id/evidence_sha256")
            else:
                source_counts[str(src_id)] += 1

    if min_per_software > 0:
        for sw in SIX_SOFTWARES:
            if sw_counts[sw] < min_per_software:
                errors.append(f"software {sw!r} count={sw_counts[sw]} < min_per_software={min_per_software}")

    if require_provenance and max_derive_ratio > 0:
        for src_id, cnt in source_counts.items():
            # Allow original (1) + up to max_derive_ratio derived variations = max_derive_ratio + 1?
            # Strict plan limit: max_derive_ratio total derived copies (or 3x cap total)
            if cnt > max_derive_ratio:
                errors.append(f"source_run_id {src_id!r} expanded {cnt}x > cap {max_derive_ratio}x")

    return {
        "gate": "gate_6_coverage_and_provenance",
        "passed": len(errors) == 0,
        "software_counts": {sw: sw_counts[sw] for sw in SIX_SOFTWARES},
        "errors": errors[:20],
    }


def gate_sha256_ledger(
    dataset_path: str | Path,
    ledger_path: Optional[str | Path] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    actual_sha = sha256_file(dataset_path)
    out_ledger = Path(ledger_path) if ledger_path else Path(str(dataset_path) + ".ledger.json")
    errors: List[str] = []

    if out_ledger.exists() and not write_ledger:
        existing = json.loads(out_ledger.read_text(encoding="utf-8"))
        exp = existing.get("output_sha256") or existing.get("sha256")
        if exp and exp != actual_sha:
            errors.append(f"ledger mismatch: expected={exp[:16]} actual={actual_sha[:16]}")
    elif write_ledger:
        payload = {
            "output_path": str(dataset_path),
            "output_sha256": actual_sha,
            "sha256": actual_sha,
            "size_bytes": os.path.getsize(dataset_path),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        out_ledger.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "gate": "gate_7_sha256_ledger",
        "passed": len(errors) == 0,
        "sha256": actual_sha,
        "ledger_path": str(out_ledger),
        "errors": errors[:20],
    }


def gate_falsifiable_mutation_probe(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gate 8: 可证伪 +5% 数值变异探针。对样本数值施加 5% 偏移后，Gate 5 必须拦截并报红。"""
    mutated_rows: List[Dict[str, Any]] = []
    for rec in rows:
        claim = _extract_claimed_dict(rec)
        if isinstance(rec.get("wm_sample"), dict) and claim:
            bad = json.loads(json.dumps(rec))
            bad_claim = _extract_claimed_dict(bad)
            if bad_claim:
                for k, v in list(bad_claim.items()):
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
                        bad_claim[k] = float(v) * 1.05
                        break
                if isinstance(bad.get("physics_claim"), dict):
                    bad["physics_claim"] = bad_claim
                elif isinstance(bad.get("expected"), dict):
                    bad["expected"] = bad_claim
                else:
                    for m in reversed(bad["messages"]):
                        if m.get("role") == "assistant":
                            m["content"] = json.dumps(bad_claim, ensure_ascii=False)
                            break
                mutated_rows.append(bad)
                break

    if not mutated_rows:
        # 构造保底的厚壁圆筒 / FOS 变异对，确保门禁逻辑永远可证伪，不因数据集缺失字段而空转
        mutated_rows = [{
            "wm_sample": {"task": "adapt_material", "Sy": 300.0, "sigma": 150.0},
            "physics_claim": {
                "yield_strength_mpa": 300.0,
                "peak_von_mises_mpa": 150.0,
                "safety_factor": 2.0 * 1.05,  # +5% perturbation -> must be caught!
                "fos_gate": "pass",
            },
        }]

    probe_res = gate_physics_recompute(mutated_rows)
    caught = not probe_res["passed"] and len(probe_res["errors"]) > 0
    return {
        "gate": "gate_8_falsifiable_mutation_probe",
        "passed": caught,
        "mutated_probe_caught": caught,
        "probe_errors": probe_res["errors"],
        "errors": [] if caught else ["CRITICAL: +5% numeric mutation slipped past gate_5_physics_recompute!"],
    }


def run_all_gates(
    dataset_path: str | Path,
    *,
    eval_dir: Optional[str | Path] = None,
    holdout_path: Optional[str | Path] = None,
    ledger_path: Optional[str | Path] = None,
    write_ledger: bool = True,
    min_per_software: int = 0,
    require_provenance: bool = False,
    max_derive_ratio: int = 3,
) -> Dict[str, Any]:
    p = Path(dataset_path)
    if not p.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")

    rows: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            rows.append(json.loads(s))

    if not rows:
        raise ValueError(f"dataset is empty: {dataset_path}")

    results = [
        gate_schema_and_tools(rows),
        gate_system_prompt_budget_and_leak(rows),
        gate_eval_contamination(p, eval_dir=eval_dir, holdout_path=holdout_path),
        gate_physical_units(p),
        gate_physics_recompute(rows),
        gate_coverage_and_provenance(
            rows,
            min_per_software=min_per_software,
            require_provenance=require_provenance,
            max_derive_ratio=max_derive_ratio,
        ),
        gate_sha256_ledger(p, ledger_path=ledger_path, write_ledger=write_ledger),
        gate_falsifiable_mutation_probe(rows),
    ]
    all_passed = all(r["passed"] for r in results)
    return {
        "passed": all_passed,
        "dataset": str(p),
        "n_rows": len(rows),
        "gates": {r["gate"]: r for r in results},
    }


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="gate_all90_selftest_") as td:
        td_p = Path(td)
        clean_f = td_p / "clean.jsonl"
        clean_rows = []
        for idx, sw in enumerate(SIX_SOFTWARES):
            clean_rows.append({
                "software": sw,
                "source_run_id": f"run_{sw}_{idx}",
                "evidence_sha256": hashlib.sha256(sw.encode()).hexdigest(),
                "wm_sample": {"task": "adapt_material", "Sy": 300.0, "sigma": 150.0},
                "messages": [
                    {"role": "system", "content": f"你是 Virtu {sw} 工业专家，按 mm 与 FOS>=1.5 校验。"},
                    {"role": "user", "content": f"[{sw}] 计算材料安全系数，屈服 300MPa，应力 150MPa，并调用几何检查工具。"},
                    {
                        "role": "assistant",
                        "content": '<tool_call>\n{"name": "cadcam_universal_geometry", "arguments": {"part": "shaft"}}\n</tool_call>',
                    },
                    {"role": "tool", "content": '{"ok": true}'},
                    {
                        "role": "assistant",
                        "content": json.dumps({
                            "yield_strength_mpa": 300.0,
                            "peak_von_mises_mpa": 150.0,
                            "safety_factor": 2.0,
                            "fos_gate": "pass",
                        }),
                    },
                ],
            })
        clean_f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in clean_rows) + "\n", encoding="utf-8")

        report = run_all_gates(clean_f, min_per_software=1, require_provenance=True)
        assert report["passed"], f"Clean dataset failed gates: {report}"

        # 负向反证 1：伪造工具名必拦
        bad_tool = json.loads(json.dumps(clean_rows[0]))
        bad_tool["messages"][2]["content"] = '<tool_call>\n{"name": "hallucinated_fake_tool", "arguments": {}}\n</tool_call>'
        assert not gate_schema_and_tools([bad_tool])["passed"]

        # 负向反证 2：System prompt > 702 B 必拦
        bad_sys = json.loads(json.dumps(clean_rows[0]))
        bad_sys["messages"][0]["content"] = "X" * 705
        assert not gate_system_prompt_budget_and_leak([bad_sys])["passed"]

        # 负向反证 3：+5% 物理数值篡改必拦
        bad_phys = json.loads(json.dumps(clean_rows[0]))
        bad_phys["messages"][4]["content"] = json.dumps({
            "yield_strength_mpa": 300.0,
            "peak_von_mises_mpa": 150.0,
            "safety_factor": 2.1,
            "fos_gate": "pass",
        })
        assert not gate_physics_recompute([bad_phys])["passed"]

        # 负向反证 4：派生超过 3x 倍数必拦
        assert not gate_coverage_and_provenance(
            [clean_rows[0]] * 4, require_provenance=True, max_derive_ratio=3
        )["passed"]

    print("[SELF-TEST] PASS: gate_all90_dataset (all 8 gates + negative falsification probes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="All-90 数据集 8 道硬门禁")
    parser.add_argument("--data", default=None, help="待审计 SFT JSONL 路径")
    parser.add_argument("--holdout", default=None, help="额外留出测试集 JSONL (交叉去污染)")
    parser.add_argument("--min-per-software", type=int, default=0, help="六大软件每类最少样本数")
    parser.add_argument("--require-provenance", action="store_true", help="强制要求 source_run_id + evidence_sha256")
    parser.add_argument("--max-derive-ratio", type=int, default=3, help="单条真实轨迹最大派生倍增系数")
    parser.add_argument("--out", default=None, help="门禁审计报告 JSON 输出路径")
    parser.add_argument("--self-test", "--selftest", dest="self_test", action="store_true", help="运行零依赖反证自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    if not args.data:
        parser.error("请提供 --data <jsonl> 或 --self-test")

    report = run_all_gates(
        args.data,
        holdout_path=args.holdout,
        min_per_software=args.min_per_software,
        require_provenance=args.require_provenance,
        max_derive_ratio=args.max_derive_ratio,
    )
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"passed": report["passed"], "n_rows": report["n_rows"],
                      "failed_gates": [k for k, v in report["gates"].items() if not v["passed"]]}, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
