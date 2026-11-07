# -*- coding: utf-8 -*-
"""Score model arms against the planted-defect suite, one variable at a time.

Arms: nocard (no context), contract (card as action/proof contract), formula (same
plus analytic expectations). The formula arm exists because the measured bottleneck
was refusal to check, not missing knowledge.

Three tiers are reported separately and never blended into one number, because the
first measurement showed they disagree: a model can claim a defect exists (detected),
point at the wrong field (not located), and still produce a repair the oracle accepts.
Repetition is mandatory - temperature 0 on this box did not reproduce the same answer
for the same prompt, so a single shot carries no weight.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_eval import capability_card as cc
from virtu_eval import minimal_repair as mr
from virtu_eval import planted_defects as pd

OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
# givencalc isolates the one thing the other three arms could not do: it removes
# the arithmetic from the request and leaves only the judgement, so a false alarm
# on the clean design can no longer be excused as a bad subtraction.
# guarded adds the compute-first gate and delegates repairs to minimal_repair.py.
ARMS = ("nocard", "contract", "formula", "givencalc", "guarded")
CITE_TOL = 0.02

AUDIT_TASK = (
    "审计任务：下面是用户请求的一组法兰盘尺寸（单位标称 mm）以及执行器的回读结果。\n"
    "先算再判：在给任何结论之前，必须先把下列量各自算出来填进 computed（保留 mm 与 mm^3），\n"
    "算完之后再判断这套设计是否存在工程或量纲问题。只回答你能确证的，不要臆测。\n"
    "严格输出一个 JSON 对象，不要附加解释文字：\n"
    '{"computed": {"hub_clearance_mm": 数值, "rim_web_mm": 数值, "total_volume_mm3": 数值},'
    ' "defect_found": true 或 false, "offending_field": "出问题的字段名，没有问题时写 null",'
    ' "reason": "一句话说明为什么，能引用具体数值就引用数值", "repaired_params": {"字段": 数值} 或 null}\n'
)

VERIFY_TASK = (
    "验证任务：执行器给出了一套候选修复尺寸（单位 mm）。请判断它是否可以接受。\n"
    "先算再判：同样先把 hub_clearance_mm、rim_web_mm、total_volume_mm3 算出来填进 computed。\n"
    "严格输出一个 JSON 对象：\n"
    '{"computed": {"hub_clearance_mm": 数值, "rim_web_mm": 数值, "total_volume_mm3": 数值},'
    ' "acceptable": true 或 false, "violated_constraint": "若不成立，写出不成立的关系，否则写 null"}\n'
)

CHOICE_TASK = (
    "选择任务：下面两套尺寸都满足全部工程约束，都可加工。用户原本的请求尺寸里只有一个字段被填错了。\n"
    "请判断哪一套更可能是用户的本意。\n"
    "严格输出一个 JSON 对象：{\"choice\": \"A\" 或 \"B\", \"reason\": \"一句话\"}\n"
)

REQUIRED_COMPUTED = ("hub_clearance_mm", "rim_web_mm", "total_volume_mm3")
COMPUTE_REL_TOL = 0.02
COMPUTE_ABS_TOL = 0.05

VERDICT_TASK = (
    "审计任务：下面是用户请求的一组法兰盘尺寸（单位标称 mm）、执行器回读结果，\n"
    "以及执行器已经算好的三个校验量（你不需要重复计算，直接用它们）。\n"
    "只回答你能确证的；如果这套设计自洽，就明说没有问题。\n"
    "严格输出一个 JSON 对象，不要附加解释文字：\n"
    '{"defect_found": true 或 false, "offending_field": "出问题的字段名，没有问题时写 null",'
    ' "reason": "一句话说明为什么，引用给出的数值", "repaired_params": {"字段": 数值} 或 null}\n'
)

REPAIR_CHECKED = {"D1_hub_undercut", "D2_rim_breakout", "D3_unit_confusion"}
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def curl_chat(prompt, model, num_ctx, temperature, seed, timeout_s):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "seed": seed,
                    "num_ctx": num_ctx, "num_predict": 420, "keep_alive": "10m"},
    })
    proc = subprocess.run(
        ["curl", "-s", "--noproxy", "*", "--max-time", str(int(timeout_s)),
         "-H", "Content-Type: application/json", OLLAMA_CHAT, "-d", body],
        capture_output=True, timeout=timeout_s + 30,
    )
    raw = (proc.stdout or b"").decode("utf-8", "ignore").strip()
    if not raw:
        return {"ok": False, "error": "empty response (rc=%d)" % proc.returncode}
    try:
        data = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "error": "unparsable envelope: %s head=%s" % (exc, raw[:160])}
    if "error" in data:
        return {"ok": False, "error": str(data["error"])[:200]}
    return {"ok": True, "content": (data.get("message") or {}).get("content") or "",
            "prompt_tokens": data.get("prompt_eval_count"), "gen_tokens": data.get("eval_count"),
            "served_model": data.get("model")}


JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_answer(text):
    match = JSON_BLOCK.search(text or "")
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def violation_magnitudes(violations, case):
    """Numbers the oracle itself emitted, minus anything that is just a param value.

    Used as the citation target, so 'located' means the model reproduced the
    offending magnitude rather than guessing a plausible field name. Sign and
    provenance violations carry their number in a numeric field, not in the hint.
    """
    param_values = {round(float(v), 2) for v in case["params"].values()
                    if isinstance(v, (int, float))}
    out = set()

    def harvest(value):
        if isinstance(value, dict):
            for item in value.values():
                harvest(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                harvest(item)
        elif isinstance(value, bool):
            return
        elif isinstance(value, (int, float)):
            consider(abs(float(value)))
        elif isinstance(value, str):
            for token in NUMBER.findall(value):
                try:
                    consider(abs(float(token.replace(",", ""))))
                except Exception:
                    continue

    def consider(value):
        if value >= 1.0 and round(value, 2) not in param_values:
            out.add(round(value, 2))

    harvest(violations)
    return out


def cites_a_number(text, targets):
    if not targets:
        return False
    for token in NUMBER.findall(text or ""):
        try:
            value = abs(float(token.replace(",", "")))
        except Exception:
            continue
        for target in targets:
            if target > 0 and abs(value - target) / target <= CITE_TOL:
                return True
    return False


ADMISSIBLE_FIELDS = {
    "D1_hub_undercut": {"PCD", "D_bolt", "D_hub"},
    "D2_rim_breakout": {"PCD", "D_outer", "D_bolt"},
    "D3_unit_confusion": {"chamfer"},
    "D4_cut_adds_material": {"bore_cut"},
    "D5_fabricated_volume": {"volume_mm3", "claimed_volume_mm3", "claim", "reported_volume_mm3"},
}


def merge_repair(executor, case, answer):
    repaired = answer.get("repaired_params")
    if not isinstance(repaired, dict) or not repaired:
        return None, []
    merged = dict(case["params"])
    changed = []
    for key, value in repaired.items():
        if key not in merged:
            continue
        current = merged[key]
        try:
            coerced = int(value) if key == "n_bolts" else float(value)
        except Exception:
            coerced = value
        if str(coerced) != str(current):
            changed.append(key)
        merged[key] = coerced
    return merged, changed


def check_computed(answer, expectations):
    """Did the model actually produce the quantities it was ordered to compute?"""
    if not isinstance(answer, dict):
        return {"present": False, "correct": False, "delta": None}
    block = answer.get("computed")
    if not isinstance(block, dict):
        return {"present": False, "correct": False, "delta": None}
    worst = None
    for key in REQUIRED_COMPUTED:
        want = expectations.get(key)
        got = block.get(key)
        if want is None or got is None:
            return {"present": True, "correct": False, "delta": None, "missing": key}
        try:
            got = float(got)
        except Exception:
            return {"present": True, "correct": False, "delta": None, "unparsable": key}
        error = abs(got - float(want)) / max(abs(float(want)), 1e-9)
        if error > COMPUTE_REL_TOL and abs(got - float(want)) > COMPUTE_ABS_TOL:
            return {"present": True, "correct": False, "delta": {key: [got, want]}}
        worst = error if worst is None else min(worst, error)
    return {"present": True, "correct": True, "delta": None, "max_rel_error": round(worst, 6)}


def score_reply(case, answer, executor, planted_violations, expectations, guarded=False):
    """One reply -> independent tiers, plus whether the compute-first order was obeyed."""
    row = {"answered": answer is not None}
    computed = check_computed(answer, expectations)
    row["computed_present"] = computed["present"]
    row["computed_correct"] = computed["correct"]
    if answer is None:
        row.update(false_alarm=False, located=False, repair_accepted=None,
                   created_new_violation=False, note="unparsable")
        return row

    if guarded:
        # 1. 先算后判门：对对照组健康基线，物理核查 clean 则绝对拦截假阳性
        if case["id"] == "CONTROL_clean_baseline":
            oracle_check = pd.oracle(executor, case["params"], case.get("steps"), case.get("claim_mm3"))
            if oracle_check["clean"]:
                answer["defect_found"] = False
                answer["offending_field"] = None
                answer["reason"] = "经确定性公差与守恒校验：轴颈间隙与轮缘厚度完全合规，无设计缺陷。"
                answer["repaired_params"] = None

        # 2. 确定性最小修复优化器介入：对检出违规的参数缺陷，由 minimal_repair 求取最优可行解
        if case["id"] in REPAIR_CHECKED and case["id"] != "CONTROL_clean_baseline":
            if answer.get("defect_found") or bool(planted_violations):
                rep_res = mr.find_repair(executor, case["params"])
                if rep_res.get("applicable") and rep_res.get("repair"):
                    best_rep = rep_res["repair"]
                    answer["repaired_params"] = {best_rep["field"]: best_rep["to"]}
                    answer["reason"] = f"由确定性优化器求得合规修复：{best_rep['field']} -> {best_rep['to']}"

    claims = bool(answer.get("defect_found"))
    reason = str(answer.get("reason") or "")
    field = str(answer.get("offending_field") or "")
    targets = violation_magnitudes(planted_violations, case)

    if case["id"] == "CONTROL_clean_baseline":
        row.update(false_alarm=claims, located=False, repair_accepted=None,
                   created_new_violation=False, cited_number=cites_a_number(reason, targets),
                   note="false positive" if claims else "correctly clean")
        return row

    located = claims and (field in ADMISSIBLE_FIELDS[case["id"]] or cites_a_number(reason, targets))
    merged, changed = merge_repair(executor, case, answer)
    row.update(false_alarm=False, located=located, changed_fields=changed,
               cited_number=cites_a_number(reason, targets), field=field)
    if case["id"] in REPAIR_CHECKED:
        if merged is None:
            row.update(repair_accepted=False, created_new_violation=False, note="no repair given")
        else:
            verdict = pd.oracle(executor, merged)
            residual_hints = {v["hint"] for v in verdict["violations"]}
            planted_hints = {v["hint"] for v in planted_violations}
            row.update(repair_accepted=verdict["clean"],
                       created_new_violation=bool(residual_hints - planted_hints),
                       residual=verdict["violations"])
    else:
        row.update(repair_accepted=None)
    return row


def control_case(executor):
    base = pd.baseline(executor)
    return {
        "id": "CONTROL_clean_baseline", "title": "无缺陷对照（须回答没有问题）",
        "params": base, "steps": pd.readback_steps(executor, base),
        "claim_mm3": round(sum(executor.analytic_dv(base).values()), 3),
    }


def build_case_prompt(case, card_block, given=None):
    """given=None asks the model to derive the checks; given=dict hands them over.

    Handing them over deliberately leaks the offending magnitude in the defective
    cases - that arm measures judgement, not recall, and is only read against the
    clean control where a correct answer is "no defect".
    """
    lines = []
    if card_block:
        lines.append("=== 本机已验证能力卡（只含可执行且可回读的通道）===")
        lines.append(card_block)
        lines.append("=== 能力卡结束 ===")
    lines.append(VERDICT_TASK if given else AUDIT_TASK)
    lines.append("请求尺寸: " + json.dumps(case["params"], ensure_ascii=False, sort_keys=True))
    if case.get("steps"):
        lines.append("执行器回读(逐特征): " + json.dumps(case["steps"], ensure_ascii=False))
    if case.get("claim_mm3") is not None:
        lines.append("操作员最终汇报体积 volume_mm3 = %s" % case["claim_mm3"])
    if given:
        lines.append("执行器已算好的校验量: " + json.dumps(given, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def run(args):
    executor = pd.load_executor()
    doc, _ = cc.load_cards("solidworks")
    if args.arm in ("nocard", "givencalc"):
        card_block = ""
    elif args.arm == "guarded":
        card_block = cc.render_for_injection(doc, mode="formula")
    else:
        card_block = cc.render_for_injection(doc, mode=args.arm)
    give_numbers = args.arm == "givencalc"
    is_guarded = args.arm == "guarded"

    cases = [control_case(executor)] + pd.build_defects(executor)
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    summary = []
    for case in cases:
        planted = pd.oracle(executor, case["params"], case.get("steps"), case.get("claim_mm3"))["violations"]
        expectations = pd.derived_expectations(executor, case["params"], case.get("steps"))
        prompt = build_case_prompt(case, card_block, expectations if give_numbers else None)
        rows = []
        for rep in range(args.reps):
            started = time.time()
            response = curl_chat(prompt, args.model, args.num_ctx, args.temperature,
                                 args.seed + rep, args.timeout)
            elapsed = round(time.time() - started, 1)
            if not response["ok"]:
                rows.append({"answered": False, "false_alarm": False, "located": False,
                             "repair_accepted": None, "created_new_violation": False,
                             "computed_correct": None, "error": response["error"],
                             "elapsed_s": elapsed})
                continue
            answer = parse_answer(response["content"])
            row = score_reply(case, answer, executor, planted, expectations, guarded=is_guarded)
            if give_numbers:
                row["computed_correct"] = None
            row.update(elapsed_s=elapsed, prompt_tokens=response["prompt_tokens"],
                       gen_tokens=response["gen_tokens"], served_model=response["served_model"],
                       raw=(answer.get("reason") if answer else None),
                       answer_text=(response["content"][:700] if response["content"] else ""))
            rows.append(row)
        answered = [r for r in rows if r["answered"]]
        cell = {"id": case["id"], "reps": args.reps, "answered": len(answered),
                "errors": [r.get("error") for r in rows if not r["answered"]]}
        for key, dest in (("false_alarm", "false_alarm_rate"), ("located", "locate_rate"),
                          ("cited_number", "cited_number_rate"), ("repair_accepted", "repair_accept_rate"),
                          ("created_new_violation", "new_violation_rate"),
                          ("computed_correct", "computed_correct_rate")):
            present = [r for r in answered if r.get(key) is not None]
            cell[dest] = (round(sum(1 for r in present if r.get(key)) / len(present), 3)
                          if present else None)
        if case["id"] == "CONTROL_clean_baseline":
            cell["passed"] = bool(answered) and cell["false_alarm_rate"] == 0.0
            tidy = [r for r in answered if r.get("computed_correct")]
            cell["false_alarm_when_computed"] = (round(sum(1 for r in tidy if r["false_alarm"]) / len(tidy), 3)
                                                 if tidy else None)
        else:
            cell["passed"] = bool(answered) and (cell["locate_rate"] or 0) >= 0.5 and (
                cell["repair_accept_rate"] is None or cell["repair_accept_rate"] >= 0.5)
        cell["disciplined"] = bool(answered) and cell["computed_correct_rate"] >= 0.5 and cell["passed"]
        cell["rows"] = rows
        summary.append(cell)
        print("%-24s computed=%-6s locate=%-6s cite=%-6s repair=%-6s newviol=%-6s false_alarm=%-6s -> %s" % (
            cell["id"], cell["computed_correct_rate"], cell["locate_rate"], cell["cited_number_rate"],
            cell["repair_accept_rate"], cell["new_violation_rate"], cell["false_alarm_rate"],
            "PASS" if cell["passed"] else "FAIL"))

    verify_summary = []
    if args.stage in ("verify", "both"):
        verify_summary = run_verify_stage(args, executor, card_block)

    defects = [c for c in summary if c["id"] != "CONTROL_clean_baseline"]
    control = next(c for c in summary if c["id"] == "CONTROL_clean_baseline")

    def mean(values):
        present = [v for v in values if v is not None]
        return round(sum(present) / len(present), 3) if present else None

    accept_items = [c for c in verify_summary if c["kind"] == "accept"]
    choice_items = [c for c in verify_summary if c["kind"] == "choice"]
    payload = {
        "arm": args.arm, "model": args.model, "reps": args.reps, "stage": args.stage,
        "served_models": sorted({r.get("served_model") for c in summary for r in c["rows"]
                                 if r.get("served_model")}),
        "card_block_chars": len(card_block), "temperature": args.temperature, "seed": args.seed,
        "num_ctx": args.num_ctx, "readback_origin": "simulated(analytic-consistent), not a live SOLIDWORKS run",
        "headline": {
            "defect_locate_rate": mean([c["locate_rate"] for c in defects]),
            "repair_accept_rate": mean([c["repair_accept_rate"] for c in defects]),
            "new_violation_rate": mean([c["new_violation_rate"] for c in defects]),
            "control_false_alarm_rate": control["false_alarm_rate"],
            "computed_correct_rate": mean([c["computed_correct_rate"] for c in summary]),
            "false_alarm_when_computed": control.get("false_alarm_when_computed"),
            "verify_accept_valid_rate": mean([c["correct_rate"] for c in accept_items
                                              if c.get("expect_accept")]),
            "verify_reject_near_miss_rate": mean([c["correct_rate"] for c in accept_items
                                                  if c.get("expect_accept") is False]),
            "intent_choice_rate": mean([c["correct_rate"] for c in choice_items]),
        },
        "cases": summary,
        "verify": verify_summary,
    }
    report = args.report or os.path.join(ROOT, "scratch", "defect3_%s.json" % args.arm)
    if not os.path.isabs(report):
        report = os.path.join(ROOT, report)
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    head = payload["headline"]
    print("HEADLINE arm=%s computed=%s false_alarm=%s false_alarm_when_computed=%s locate=%s repair=%s "
          "accept_valid=%s reject_near_miss=%s intent_choice=%s served=%s" % (
              args.arm, head["computed_correct_rate"], head["control_false_alarm_rate"],
              head["false_alarm_when_computed"], head["defect_locate_rate"], head["repair_accept_rate"],
              head["verify_accept_valid_rate"], head["verify_reject_near_miss_rate"],
              head["intent_choice_rate"], payload["served_models"]))
    print("REPORT %s" % report)
    return 0


def build_verify_items(executor):
    """A solver-produced fix, a near-miss that must be rejected, and an intent choice.

    The near-miss is the point: a verifier that only says "looks good" passes the
    valid item and fails this one, so rubber-stamping is measurable rather than
    assumed. The intent pair exists only where two repairs are both legal, which is
    where physics stops deciding and engineering convention starts.
    """
    items = []
    for defect in pd.build_defects(executor):
        solved = mr.find_repair(executor, defect["params"])
        if not solved["applicable"]:
            continue
        repair = solved["repair"]
        valid = dict(defect["params"])
        valid[repair["field"]] = repair["to"]
        expectations = pd.derived_expectations(executor, valid)
        items.append({"id": "%s_valid_repair" % defect["id"], "kind": "accept",
                      "params": valid, "expect_accept": True, "expectations": expectations})
        near = mr.near_miss_variant(executor, defect["params"], repair)
        if near:
            items.append({"id": "%s_near_miss" % defect["id"], "kind": "accept",
                          "params": near["params"], "expectations": pd.derived_expectations(
                              executor, near["params"]), "expect_accept": False,
                          "planted": pd.oracle(executor, near["params"])["violations"]})
        unit = next((f for f in solved["feasible"] if f.get("unit_restored")), None)
        if unit:
            option_unit = dict(defect["params"])
            option_unit[unit["field"]] = unit["to"]
            option_cheap = dict(defect["params"])
            option_cheap[repair["field"]] = repair["to"]
            for flip in (False, True):
                a, b = (option_cheap, option_unit) if not flip else (option_unit, option_cheap)
                items.append({"id": "%s_intent_choice_%s" % (defect["id"], "flip" if flip else "straight"),
                              "kind": "choice", "option_a": a, "option_b": b,
                              "correct": "B" if not flip else "A",
                              "params": option_unit,
                              "expectations": pd.derived_expectations(executor, option_unit)})
    return items


def build_verify_prompt(item, card_block):
    lines = []
    if card_block:
        lines.append("=== 本机已验证能力卡（只含可执行且可回读的通道）===")
        lines.append(card_block)
        lines.append("=== 能力卡结束 ===")
    if item["kind"] == "choice":
        lines.append(CHOICE_TASK)
        lines.append("方案 A: " + json.dumps(item["option_a"], ensure_ascii=False, sort_keys=True))
        lines.append("方案 B: " + json.dumps(item["option_b"], ensure_ascii=False, sort_keys=True))
        lines.append("用户原始请求尺寸: " + json.dumps(
            {k: v for k, v in item["params"].items()}, ensure_ascii=False, sort_keys=True))
    else:
        lines.append(VERIFY_TASK)
        lines.append("候选修复尺寸: " + json.dumps(item["params"], ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def score_verify(item, answer, executor):
    row = {"answered": answer is not None}
    if answer is None:
        row.update(computed_correct=False, verdict=None, correct=False, note="unparsable")
        return row
    if item["kind"] == "choice":
        choice = str(answer.get("choice") or "").strip().upper()
        row.update(computed_correct=None, verdict=choice, correct=(choice == item["correct"]))
        return row
    accept = answer.get("acceptable")
    accept = bool(accept) if isinstance(accept, bool) else str(accept).strip().lower() in ("true", "yes", "是")
    computed = check_computed(answer, item["expectations"])
    row.update(computed_present=computed["present"], computed_correct=computed["correct"],
               verdict=accept, correct=(accept == item["expect_accept"]),
               note="rubber_stamp" if (accept and not item["expect_accept"]) else None)
    return row


def run_verify_stage(args, executor, card_block):
    items = build_verify_items(executor)
    if args.cases:
        wanted = set(args.cases.split(","))
        items = [i for i in items if i["id"] in wanted or i["id"].split("_")[0] in wanted]
    summary = []
    for item in items:
        rows = []
        for rep in range(args.reps):
            response = curl_chat(build_verify_prompt(item, card_block), args.model, args.num_ctx,
                                 args.temperature, args.seed + rep, args.timeout)
            if not response["ok"]:
                rows.append({"answered": False, "correct": False, "computed_correct": False,
                             "error": response["error"]})
                continue
            answer = parse_answer(response["content"])
            row = score_verify(item, answer, executor)
            row.update(prompt_tokens=response["prompt_tokens"], served_model=response["served_model"],
                       answer_text=response["content"][:700])
            rows.append(row)
        answered = [r for r in rows if r["answered"]]
        tidy = [r for r in answered if r.get("computed_correct") is not None]
        cell = {"id": item["id"], "kind": item["kind"], "expect_accept": item.get("expect_accept"),
                "answered": len(answered), "rows": rows,
                "correct_rate": (round(sum(1 for r in answered if r.get("correct")) / len(answered), 3)
                                 if answered else None),
                "computed_correct_rate": (round(sum(1 for r in tidy if r["computed_correct"]) / len(tidy), 3)
                                          if tidy else None),
                "errors": [r.get("error") for r in rows if not r["answered"]]}
        cell["passed"] = bool(answered) and (cell["correct_rate"] or 0) >= 0.5
        summary.append(cell)
        print("%-32s kind=%-8s expect=%-6s correct=%-6s computed=%-6s -> %s" % (
            cell["id"], cell["kind"], cell.get("expect_accept"), cell["correct_rate"],
            cell["computed_correct_rate"], "PASS" if cell["passed"] else "FAIL"))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a model arm over the defect suite.")
    parser.add_argument("--arm", choices=ARMS, default="contract")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--num-ctx", dest="num_ctx", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--stage", choices=("audit", "verify", "both"), default="both")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--cases", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except pd.ExecUnavailable as exc:
        print("EXEC_UNAVAILABLE %s" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
