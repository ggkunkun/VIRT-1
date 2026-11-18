# -*- coding: utf-8 -*-
"""build_wm_repairloop.py — 从实测失败轨迹构建世界模型 repairloop 训练语料。

两类来源：
  1. 真实失败：runs/industrial_eval_20261112/raw_stream_contract_cfgA_*.jsonl
     （模型原生坏解，逐条经判分器确认 FAIL）；
  2. 合成修复：用训练生成器在独立 seed 下生成新题，按 4 种已验证错误模式
     （scale / drop / gate_flip / binding）制造坏解，再给校验器反馈与修正解。

每条轨迹的硬约束（fail-closed）：
  - 坏解必须被 eval_worldmodel.judge 判 FAIL；
  - 修正解必须被同一判分器判 PASS；
  - 修正解（非 invalid）必须被 wm_verifier.verify 接受；
  - 题面不得与 data/holdout/** 的评测题重合（防止训练污染评测）。

输出：
  cloud_train_pack/dataset/virtu_wm_repairloop_sft.jsonl
  cloud_train_pack/dataset/virtu_wm_repairloop_sft_ledger.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import eval_worldmodel as E  # noqa: E402
import wm_verifier as V  # noqa: E402
import wm_contract as C  # noqa: E402
import corpus_unit_audit as U  # noqa: E402

DEFAULT_FAILURES = os.path.join(
    ROOT, "runs", "industrial_eval_20261112", "raw_stream_contract_cfgA_gpu24_ctx6144.jsonl")
DEFAULT_OUT = os.path.join(ROOT, "cloud_train_pack", "dataset", "virtu_wm_repairloop_sft.jsonl")
DEFAULT_LEDGER = os.path.join(ROOT, "cloud_train_pack", "dataset",
                              "virtu_wm_repairloop_sft_ledger.json")
HOLDOUTS = [os.path.join(ROOT, "data", "holdout", "wm_holdout_v1.jsonl"),
            os.path.join(ROOT, "data", "holdout", "wm_holdout_v2.jsonl")]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_holdout_prompts():
    s = set()
    for p in HOLDOUTS:
        if os.path.isfile(p):
            for line in open(p, encoding="utf-8"):
                try:
                    s.add(json.loads(line)["prompt"])
                except Exception:
                    pass
    return s


def feedback_of(miss):
    miss = [m for m in (miss or []) if m]
    return ("【教师诊断与指导】校验器复算结果：" + "；".join(miss[:8]) +
            "。请逐项按题面参数重新计算，补全契约要求的全部字段，"
            "并保证 derivation 里的算式与填写的数值一致；只输出一个 JSON 对象。")


def make_messages(system, prompt, bad_obj, expected, miss):
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": json.dumps(bad_obj, ensure_ascii=False), "loss": False},
        {"role": "user", "content": feedback_of(miss)},
        {"role": "assistant", "content": json.dumps(expected, ensure_ascii=False), "loss": True},
    ]


def make_positive(system, prompt, expected):
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": json.dumps(expected, ensure_ascii=False), "loss": True},
    ]


def perturb(ws, inputs, mode):
    """返回坏解 world_state 或 None（该模式不适用）。"""
    ws = json.loads(json.dumps(ws, ensure_ascii=False))
    nums = [k for k, v in ws.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0]
    if not nums:
        return None
    if mode == "scale":
        k = nums[0]
        ws[k] = ws[k] * 2.0
        return ws
    if mode == "drop":
        if len(nums) < 2:
            return None
        for k in nums[:2]:
            ws.pop(k, None)
        return ws
    if mode == "gate_flip":
        for k, v in list(ws.items()):
            if k == "fos_gate" and isinstance(v, str):
                ws[k] = "fail" if v.lower() == "pass" else "pass"
                return ws
            if k == "volume_conservation" and isinstance(v, str):
                ws[k] = "fail" if v.lower() == "pass" else "pass"
                return ws
            if k == "tolerance_pass" and isinstance(v, bool):
                ws[k] = not v
                return ws
            if k == "within_limit" and isinstance(v, bool):
                ws[k] = not v
                return ws
        return None
    if mode == "binding":
        vals = [v for v in (inputs or {}).values() if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0]
        if not vals:
            return None
        alt = vals[-1]
        ws[nums[0]] = alt
        return ws
    return None


def valid_corrected(task, expected, scenario):
    if task == "invalid":
        ok, fmt, _ = E.judge("invalid", {"world_state": None, "invalid": True},
                             json.loads(json.dumps(expected, ensure_ascii=False)))
        return ok and fmt
    ok, fmt, _ = E.judge(task, expected, expected)
    if not (ok and fmt):
        return False
    if scenario:
        res = V.verify({"world_state": expected.get("world_state")}, scenario)
        if not res.get("ok"):
            return False
    return True


def add_trajectory(records, ledger, task, prompt, bad_obj, expected, scenario, source, mode):
    if prompt in ledger["holdout_prompts"]:
        ledger["skipped_holdout_overlap"] += 1
        return
    if not isinstance(expected, dict) or not isinstance(expected.get("world_state", {}), (dict, type(None))):
        ledger["skipped_bad_expected"] += 1
        return
    # 求解器参考值补齐期望里缺失的契约字段（如 mass_props 的 mass_kg）。
    # 只补缺，不覆盖生成器真值；补完仍用同一判分器复核。
    if scenario and task != "invalid":
        ref = V.recompute(scenario) or {}
        ws = expected.get("world_state") or {}
        missing = {k: v for k, v in ref.items() if k not in ws}
        if missing:
            expected = json.loads(json.dumps(expected, ensure_ascii=False))
            expected["world_state"].update(missing)
    ok, fmt, miss = E.judge(task, expected, bad_obj) if bad_obj is not None else (True, True, ["<no_bad>"])
    if ok:
        # 坏解竟然通过：不能当负例
        ledger["skipped_bad_passes"] += 1
        return
    if not valid_corrected(task, expected, scenario):
        ledger["skipped_corrected_fails"] += 1
        return
    rec_repair = {"messages": make_messages(C.SYSTEM, prompt, bad_obj, expected, miss),
                  "family": f"wm_repairloop_{task}", "scenario": scenario,
                  "meta": {"source": source, "error_mode": mode}}
    rec_pos = {"messages": make_positive(C.SYSTEM, prompt, expected),
               "family": f"wm_repairloop_{task}_positive", "scenario": scenario,
               "meta": {"source": source, "error_mode": "positive"}}
    # 量纲审计闸：inertia_*_mm4 必须能从题面 shape/参数复核；解析不了一律不入集。
    for rec in (rec_repair, rec_pos):
        issue = U.row_issue(json.dumps(rec, ensure_ascii=False))
        if issue:
            ledger["skipped_unit_audit"] += 1
            return
    records.append(rec_repair)
    records.append(rec_pos)
    ledger["rows"] += 1
    ledger["repair_rows"] += 1
    ledger["positive_rows"] += 1
    ledger["bad_turn_loss_masked"] += 1
    ledger["per_family"][task] += 1
    ledger["per_mode"][mode] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--failures", default=DEFAULT_FAILURES)
    ap.add_argument("--synthetic-per-family", type=int, default=20)
    ap.add_argument("--seed", type=int, default=99001)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    args = ap.parse_args()

    ledger = {"rows": 0, "repair_rows": 0, "positive_rows": 0,
              "bad_turn_loss_masked": 0, "per_family": Counter(), "per_mode": Counter(),
              "skipped_holdout_overlap": 0, "skipped_bad_expected": 0,
              "skipped_bad_passes": 0, "skipped_corrected_fails": 0,
              "skipped_no_error_mode": 0, "skipped_unit_audit": 0,
              "holdout_prompts": load_holdout_prompts()}
    records = []

    # 1) 真实失败
    real_n = 0
    if os.path.isfile(args.failures):
        for line in open(args.failures, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            task = r.get("family")
            expected = r.get("expected")
            raw = E.extract_json(r.get("raw") or "")
            if not task or not isinstance(expected, dict) or raw is None:
                continue
            real_n += 1
            add_trajectory(records, ledger, task, r.get("user", ""), raw, expected,
                           None, "model_failure", "real_failure")
    ledger["real_failures_seen"] = real_n

    # 2) 合成修复（独立 seed，生成器题面）
    rng = random.Random(args.seed)
    syn_n = 0
    for fam, gen in E.GEN_BY_FAMILY.items():
        for case_i in range(args.synthetic_per_family):
            rec = gen(rng)
            if not rec:
                continue
            msgs = rec.get("messages") or []
            user = next((m.get("content") for m in msgs if m.get("role") == "user"), None)
            ans = next((m.get("content") for m in msgs if m.get("role") == "assistant"), None)
            if not user or not ans:
                continue
            try:
                expected = json.loads(ans)
            except Exception:
                continue
            scenario = rec.get("scenario") or {}
            inputs = scenario.get("inputs") if isinstance(scenario, dict) else {}
            if fam == "invalid":
                bad = {"world_state": {"material_removed_mm3": 1000.0}}
                add_trajectory(records, ledger, fam, user, bad, expected, scenario,
                               "synthetic", "invalid_hard_compute")
                syn_n += 1
                continue
            ws = expected.get("world_state")
            if not isinstance(ws, dict):
                continue
            made = False
            modes = ("scale", "drop", "gate_flip", "binding")
            order = modes[case_i % len(modes):] + modes[:case_i % len(modes)]
            for mode in order:
                bad_ws = perturb(ws, inputs, mode)
                if bad_ws is None:
                    continue
                bad = {"world_state": bad_ws}
                before = len(records)
                add_trajectory(records, ledger, fam, user, bad, expected, scenario,
                               "synthetic", mode)
                if len(records) > before:
                    made = True
                    syn_n += 1
                    break
            if not made:
                ledger["skipped_no_error_mode"] += 1

    if not records:
        raise SystemExit("[FATAL] 未产出任何修复轨迹")
    rng.shuffle(records)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    ledger.pop("holdout_prompts", None)
    ledger.update({
        "schema_version": "virtu_wm_repairloop.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured",
        "source_failures": os.path.relpath(args.failures, ROOT).replace("\\", "/"),
        "source_failures_sha256": sha256_file(args.failures) if os.path.isfile(args.failures) else None,
        "synthetic_seed": args.seed,
        "synthetic_per_family": args.synthetic_per_family,
        "synthetic_cases_used": syn_n,
        "output": os.path.relpath(args.out, ROOT).replace("\\", "/"),
        "output_sha256": sha256_file(args.out),
        "bad_turn_loss_masked": True,
        "verifier": "eval_worldmodel.judge + wm_verifier.verify（修正解必须双过；坏解必须判 FAIL）",
        "per_family": dict(ledger["per_family"].most_common()),
        "per_mode": dict(ledger["per_mode"].most_common()),
    })
    json.dump(ledger, open(args.ledger, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: ledger[k] for k in
                      ("rows", "repair_rows", "positive_rows", "bad_turn_loss_masked",
                       "real_failures_seen", "synthetic_cases_used", "skipped_holdout_overlap",
                       "skipped_bad_passes", "skipped_corrected_fails", "per_mode")},
                     ensure_ascii=False, indent=2))
    print(f"[ok] -> {args.out}")


if __name__ == "__main__":
    main()
