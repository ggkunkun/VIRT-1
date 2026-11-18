#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工程世界模型全量只读审计（2026-11-08）。

不修改任何文件。逐项复现缺陷清单，输出 PASS / FAIL / ERROR 与证据。
用法: .venv/Scripts/python.exe scripts/wm_audit_full.py
"""
from __future__ import annotations

import io
import json
import math
import os
import random
import re
import subprocess
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, ROOT)
sys.path.insert(0, SCRIPTS)
os.chdir(ROOT)

RESULTS = []


def chk(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"EXC {type(e).__name__}: {e}"
    RESULTS.append((name, bool(ok), str(detail)))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}: {detail}", flush=True)


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- self-tests
SELFTESTS = [
    ("wm_schema", [sys.executable, "scripts/wm_schema.py"], "CROSS-CHECK ALL PASS"),
    ("wm_contract", [sys.executable, "scripts/wm_contract.py"], "CROSS-CHECK OK"),
    ("wm_verifier", [sys.executable, "scripts/wm_verifier.py", "--selftest"], "ALL PASS"),
    ("wm_gate", [sys.executable, "scripts/wm_gate.py"], "PASS"),
    ("wm_eval", [sys.executable, "scripts/wm_eval.py"], "PASS"),
    ("guard", [sys.executable, "scripts/anti_hallucination_guard.py", "--selftest"], "ALL PASS"),
    ("guard_hooks", [sys.executable, "scripts/guard_hooks.py"], "PASS"),
]


def _selftest(cmd, needle):
    def _f():
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0 and needle in out, f"rc={p.returncode} {needle}={needle in out}"
    return _f


for _name, _cmd, _needle in SELFTESTS:
    chk("selftest/" + _name, _selftest(_cmd, _needle))


# ---------------------------------------------------------------- contract / schema
def contract_crosscheck():
    import wm_contract as C
    import wm_schema as S
    props = set(S._ws_props())
    bad = []
    for fam in C.KEY_SCHEMA:
        ck, sk = set(C.schema_keys(fam)), set(S.FAMILY_FIELDS.get(fam, []))
        if ck != sk:
            bad.append(f"{fam}: contract-only={sorted(ck - sk)} schema-only={sorted(sk - ck)}")
        req = set(S.REQUIRED_FIELDS.get(fam, []))
        if not req <= sk:
            bad.append(f"{fam}: required not in family fields {sorted(req - sk)}")
        if fam != "invalid" and not S.FAMILY_CARD.get(fam):
            bad.append(f"{fam}: no formula card")
    missing = sorted(set(C.ALL_SCHEMA_KEYS) - props)
    if missing:
        bad.append(f"contract keys missing from wide schema: {missing}")
    return not bad, "; ".join(bad) or f"{len(C.KEY_SCHEMA)} families, {len(props)} keys aligned"


chk("contract/schema 同源", contract_crosscheck)


def recompute_keys_align():
    import wm_contract as C
    import wm_verifier as V
    import wm_schema as S
    scenarios = {
        "removal": {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0, "rho": 7.85e-3, "stock_vol": 200000.0},
        "roughness": {"f": 0.12, "r_eps": 0.8},
        "fea_fos": {"Sy": 355.0, "sigma": 101.4},
        "collision": {"z_safe": 50.0, "z_min_rapid": 38.0, "stock_top": 40.0},
        "tolerance": {"tols": [0.05, 0.03], "upper_dev": 0.04, "lower_dev": -0.12},
        "geom_delta": {"feature_vol": 100.0, "before": 25000.0},
        "design": {"r_out": 50.0, "r_bore": 20.0, "t": 10.0, "n_holes": 6, "r_hole": 5.0, "rho": 7.85e-3},
        "process": {"D": 40.0, "L": 120.0, "ap": 2.0, "f": 0.25, "vc": 180.0, "r_eps": 0.8},
        "adapt_material": {"Sy": 245.0, "sigma": 163.0},
        "adapt_machine": {"D": 16.0, "vc": 120.0, "n_max": 3000.0},
    }
    bad = []
    for fam, inp in scenarios.items():
        ref = V.recompute({"task": fam, "inputs": inp})
        allowed = set(C.schema_keys(fam))
        extra = sorted(set(ref) - allowed)
        if extra:
            bad.append(f"{fam}: solver produces keys the contract forbids {extra}")
    return not bad, "; ".join(bad) or "10 families: every solver field is contract-registered"


chk("recompute 字段均在契约内", recompute_keys_align)


def gate_literals_single_source():
    import wm_schema as S
    import wm_verifier as V
    import wm_gate as G
    bad = []
    ref = V.recompute({"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 101.4}})
    if ref["fos_gate"] not in S.STR_FIELDS["fos_gate"]:
        bad.append(f"solver fos_gate={ref['fos_gate']!r} not in schema enum")
    norm = G.normalize({"delta_volume_mm3": 5.0})
    vc = norm.get("volume_conservation")
    if vc not in S.STR_FIELDS["volume_conservation"]:
        bad.append(f"wm_gate volume_conservation={vc!r} not in schema enum")
    # collision_risk must not be overwritten by the gate
    sc = {"task": "collision", "inputs": {"z_safe": 0.0, "z_min_rapid": 4.0, "stock_top": 5.0}}
    r = V.recompute(sc)
    g = G.normalize(dict(r))
    if r["collision_risk"] != g["collision_risk"]:
        bad.append(f"wm_gate rewrote collision_risk {r['collision_risk']} -> {g['collision_risk']}")
    return not bad, "; ".join(bad) or "fos_gate / volume_conservation / collision_risk aligned"


chk("闸门字面与语义同源", gate_literals_single_source)


# ---------------------------------------------------------------- verifier
def l1_invalid_bypass():
    import wm_verifier as V
    s = {"task": "removal", "inputs": {"doc": 2, "woc": 5, "vf": 400, "L": 100,
                                       "rho": 7.85e-3, "stock_vol": 200000}}
    base = V.l1_check({"material_removed_mm3": 1.0}, s)
    bypass = V.l1_check({"material_removed_mm3": 1.0, "invalid": 1}, s)
    return bool(base) and base == bypass, f"normal={len(base)} issues, with invalid:1={len(bypass)} issues"


chk("L1 不可被 invalid 键绕过", l1_invalid_bypass)


def recompute_no_exceptions():
    import wm_verifier as V
    cases = [
        {"task": "roughness", "inputs": {"f": 0.1}},
        {"task": "roughness", "inputs": {"f": 0.1, "r_eps": 0}},
        {"task": "process", "inputs": {"D": 0, "L": 1, "ap": 1, "f": 1, "vc": 1, "r_eps": 1}},
        {"task": "tolerance", "inputs": {"tols": [0.1]}},
        {"task": "fea_fos", "inputs": {"Sy": 355}},
        {"task": "collision", "inputs": {"z_safe": 1}},
        {"task": "adapt_machine", "inputs": {"D": 10, "vc": 100}},
        {"task": "design", "inputs": {"r_out": 10}},
        {"task": "geom_delta", "inputs": {"feature_vol": 1}},
        {"task": "mass_props", "inputs": {"shape": "box", "params": {}}},
    ]
    raised = []
    for c in cases:
        try:
            V.recompute(c)
        except Exception as e:
            raised.append(f"{c['task']}:{type(e).__name__}")
    return not raised, ", ".join(raised) or f"{len(cases)} malformed scenarios handled without exception"


chk("recompute 缺参/除零不抛异常", recompute_no_exceptions)


def verify_no_exception():
    import wm_verifier as V
    try:
        r = V.verify({"world_state": {"surface_roughness_ra_um": 1.25}},
                     {"task": "roughness", "inputs": {"f": 0.1}})
        return r["action"] in ("escalate_solver", "reject_L1"), f"action={r['action']}"
    except Exception as e:
        return False, f"raised {type(e).__name__}: {e}"


chk("verify 缺参时 fail-closed 且不崩", verify_no_exception)


def wm_eval_implicit_mul():
    import wm_eval as E
    cases = {"(2)(3)": 6.0, "(1+2)(3+4)": 21.0, "2pi": 2 * math.pi}
    bad = []
    for expr, want in cases.items():
        got = E.safe_eval(expr)
        if got is None or abs(got - want) > 1e-6:
            bad.append(f"{expr} -> {got}, expect {want}")
    return not bad, "; ".join(bad) or f"{len(cases)} implicit-multiplication forms OK"


chk("wm_eval 隐式乘法", wm_eval_implicit_mul)


def derivation_inertia():
    import wm_derivation as D
    import wm_eval as E
    import distill_local_solver as S
    sc = {"shape": "cylinder", "params": {"r": 10.0, "h": 50.0}, "rho": 2.7e-3}
    d = D._derive_mass_props(sc)
    got = E.safe_eval(d.get("inertia_izz_mm4", ""))
    want = S.mass_props_csg("cylinder", sc["params"], sc["rho"])[2][2]
    ok = got is not None and abs(got - want) / want < 1e-6
    cent_ok = any(k == "centroid_mm" or k.startswith("centroid_mm_") for k in d)
    return ok, f"derivation Iz={got} solver Iz={want}, centroid_key={cent_ok}"


chk("wm_derivation 惯性矩与求解器同源", derivation_inertia)


# ---------------------------------------------------------------- judge / guard
def judge_array_keys():
    import build_worldmodel_sft as W
    import eval_worldmodel as E
    rng = random.Random(777)
    bad = []
    for fam, gen in (("tolerance", W.gen_tolerance), ("mass_props", W.gen_mass_props)):
        rec = gen(rng)
        exp = json.loads(rec["messages"][2]["content"])
        ok, fmt, miss = E.judge(fam, exp, exp)
        if not ok:
            bad.append(f"{fam}: {miss}")
    return not bad, "; ".join(bad) or "self-judge passes for array-bearing families"


chk("judge 数组键不假失败", judge_array_keys)


def guard_preserves_design_subtree():
    import build_worldmodel_v2 as V2
    import eval_worldmodel as E
    from guard_hooks import apply_guard
    rng = random.Random(31)
    rec = V2.gen_design_from_requirement(rng)
    exp = json.loads(rec["messages"][2]["content"])
    resp = json.dumps(exp, ensure_ascii=False)
    gres = apply_guard(resp, prompt=rec["messages"][1]["content"],
                       scenario=rec.get("scenario"), tol_rel=E.REL_TOL)
    obj = E._wrap(gres.get("final_world_state"))
    ok, fmt, miss = E.judge("design", exp, obj)
    return ok, f"guard_action={gres['action']} judge_miss={miss}"


chk("护栏保留 design 子树", guard_preserves_design_subtree)


def guard_no_free_lunch():
    """护栏可以把全错答案纠正成可交付形态，但分数必须可归因，不能冒充模型能力。"""
    import build_worldmodel_sft as W
    import eval_worldmodel as E
    from guard_hooks import apply_guard
    rng = random.Random(9)
    rec = W.gen_removal_mrr(rng)
    exp = json.loads(rec["messages"][2]["content"])
    ws = exp.get("world_state") or {}
    poison = {k: (v * 50 + 1 if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
              for k, v in ws.items()}
    resp = json.dumps({"world_state": poison}, ensure_ascii=False)
    gres = apply_guard(resp, prompt=rec["messages"][1]["content"],
                       scenario=rec.get("scenario"), tol_rel=E.REL_TOL)
    obj = E._wrap(gres.get("final_world_state"))
    ok, fmt, miss = E.judge("removal", exp, obj)
    src = read("scripts/eval_worldmodel.py")
    annotated = all(k in src for k in ("solver_overwrote_fields", "pass_basis",
                                       "原生通过 = 模型能力"))
    attributed = (not ok) or gres["action"] in ("corrected", "rejected", "escalate")
    return annotated and attributed, \
        (f"action={gres['action']} judge_pass_after_guard={ok} "
         f"evaluation_annotated={annotated} layers={gres.get('layers_hit')}")


chk("护栏交付分可归因（不冒充模型能力）", guard_no_free_lunch)


def probe_contract_alignment():
    import wm_probe as P
    import build_worldmodel_sft as W
    rng = random.Random(5)
    rec = W.gen_fea_fos(rng)
    exp = json.loads(rec["messages"][2]["content"])
    ok1, why1 = P.judge("fea_fos", exp, exp)
    alt = json.loads(json.dumps(exp))
    gate = "FOS>=1.5_pass" if alt["world_state"].get("fos_gate") == "pass" else "FOS<1.5_FAIL"
    alt["world_state"]["fos_gate"] = gate
    ok2, why2 = P.judge("fea_fos", exp, alt)
    return ok1 and ok2, f"self={ok1}({why1}) long_literal_alias={ok2}({why2})"


chk("wm_probe 判分口径与官方同源", probe_contract_alignment)


def step_test_invalid_graded():
    import wm_step_test as ST
    from guard_hooks import apply_guard
    cases = ST.build_cases({"volume_mm3": 120000.0, "bbox_mm": (100.0, 60.0, 20.0)})
    none_scn = [fam for fam, _p, scn in cases if not isinstance(scn, dict)]
    inv_cases = [(fam, p, scn) for fam, p, scn in cases if fam == "invalid"]
    if none_scn or not inv_cases:
        return False, f"none_scn={none_scn}, inv_cases={len(inv_cases)}"
    _, inv_prompt, inv_scn = inv_cases[0]
    exp = {"invalid": True, "world_state": None, "reason": "missing_required_inputs",
           "violated_constraints": ["missing_inputs"]}
    good_raw = json.dumps({"invalid": True, "world_state": None,
                           "reason": "缺毛坯尺寸与切削参数",
                           "violated_constraints": ["missing_inputs"]}, ensure_ascii=False)
    bad_raw = json.dumps({"world_state": {"material_removed_mm3": 100.0}}, ensure_ascii=False)
    g_good = apply_guard(good_raw, prompt=inv_prompt, scenario=inv_scn)
    g_bad = apply_guard(bad_raw, prompt=inv_prompt, scenario=inv_scn)
    ok_good, _, _ = ST.judge("invalid", exp, ST._guard_obj(g_good))
    ok_bad, _, _ = ST.judge("invalid", exp, ST._guard_obj(g_bad))
    return (ok_good is True and ok_bad is False), f"ok_good={ok_good} ok_bad={ok_bad} none_scn={none_scn}"


chk("wm_step_test invalid 族可判分", step_test_invalid_graded)


# ---------------------------------------------------------------- inference entry
def infer_parity():
    import typing
    import worldmodel_infer as W
    src = read("scripts/worldmodel_infer.py")
    need = ["think", "format", "num_predict", "encoding"]
    missing = [k for k in need if k not in src]
    try:
        typing.get_type_hints(W.generate_world_state)
        hints = True
    except Exception as e:
        hints = False
        missing.append(f"get_type_hints:{type(e).__name__}")
    return not missing and hints, f"missing={missing} type_hints={hints}"


chk("worldmodel_infer 与评测入口同参", infer_parity)


# ---------------------------------------------------------------- data
def sft_corpus_audit():
    import wm_schema as S
    import wm_contract as C
    import glob
    top = set(S.wide_schema()["properties"])
    ws_props = set(S._ws_props())
    canon_gates = {
        gk: set(gvals)
        for spec in C.KEY_SCHEMA.values()
        for gk, gvals in (spec.get("gates") or {}).items()
    }
    report = []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "sft", "virtu_worldmodel*.jsonl"))):
        n = dup = scen = deriv = bad_top = bad_ws = bad_gate = 0
        seen = set()
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            n += 1
            rec = json.loads(line)
            msgs = rec.get("messages") or []
            if len(msgs) < 3:
                if isinstance(rec.get("outputs"), dict):
                    for k, v in rec["outputs"].items():
                        if k in canon_gates and v is not None and v not in canon_gates[k]:
                            bad_gate += 1
                continue
            key = msgs[2]["content"]
            if key in seen:
                dup += 1
            seen.add(key)
            if rec.get("scenario"):
                scen += 1
            try:
                ans = json.loads(key)
            except Exception:
                continue
            if ans.get("derivation"):
                deriv += 1
            bad_top += sum(1 for k in ans if k not in top)
            ws = ans.get("world_state")
            if isinstance(ws, dict):
                bad_ws += sum(1 for k in ws if k not in ws_props)
                for k, v in ws.items():
                    if k in canon_gates and v is not None and v not in canon_gates[k]:
                        bad_gate += 1
        report.append((os.path.basename(path), n, dup, scen, deriv, bad_top, bad_ws, bad_gate))
    bad = [r for r in report if r[2] or r[5] or r[6] or r[7]]
    summary = "; ".join(
        f"{r[0]}:n={r[1]} dup={r[2]} scen={r[3]} deriv={r[4]} badtop={r[5]} badws={r[6]} badgate={r[7]}"
        for r in report
    )
    return not bad, summary


chk("SFT 语料落盘审计", sft_corpus_audit)


def collision_label_consistency():
    import build_worldmodel_sft as W
    import wm_verifier as V
    rng = random.Random(20261108)
    n = contradictory = 0
    for _ in range(600):
        rec = W.gen_collision_gcode(rng)
        ws = json.loads(rec["messages"][2]["content"]).get("world_state") or {}
        if ws.get("gouge") is True and ws.get("collision_risk") == "none":
            contradictory += 1
        n += 1
        # cross-check against the solver whenever a scenario is available
        sc = rec.get("scenario")
        if sc:
            ref = V.recompute(sc)
            if ref and any(ref.get(k) != ws.get(k) for k in
                           ("collision_risk", "gouge", "autodiff") if k in ref):
                contradictory += 1
    return contradictory == 0, f"{contradictory} contradictory labels / {n} generated"


chk("collision 标签自洽", collision_label_consistency)


def tolerance_class_balance():
    import build_worldmodel_sft as W
    rng = random.Random(20261108)
    fits, passes = set(), set()
    for _ in range(500):
        rec = W.gen_tolerance(rng)
        ws = json.loads(rec["messages"][2]["content"]).get("world_state") or {}
        fits.add(ws.get("tolerance_fit"))
        passes.add(str(ws.get("tolerance_pass")))
    return len(fits) > 1 and len(passes) > 1, f"tolerance_fit={sorted(map(str,fits))} tolerance_pass={sorted(passes)}"


chk("tolerance 族覆盖多类", tolerance_class_balance)


# ---------------------------------------------------------------- modelfile
def modelfile_audit():
    import wm_contract as C
    p3 = "checkpoints/virtu-wm-v3.Modelfile"
    p1 = "modelfiles/virtu-13.63b.wm-v1.Modelfile"
    t3, t1 = read(p3), read(p1)
    bad = []
    for p, txt in ((p3, t3), (p1, t1)):
        if "cadcam_desktop_gui" in txt:
            bad.append(f"{p}: 世界模型 SYSTEM 混入桌面工具规范（格式竞争复发）")
        from_line = next((l for l in txt.splitlines() if l.startswith("FROM")), "")
        if "\\" in from_line:
            bad.append(f"{p}: FROM 含反斜杠绝对路径")
    missing = [k for k in C.ALL_SCHEMA_KEYS if k not in t3]
    if missing:
        bad.append(f"{p3}: 契约键名未全量下发 {missing[:8]}")
    if "你是 Virtu 制造世界模型" not in t3:
        bad.append(f"{p3}: SYSTEM 不是当前纯契约 build_system() 产物")
    # 训练编码逐字拼 ChatML；serving 模板若是纯文本三段即格式错配（11-11 实测漂移）
    if "<|im_start|>" not in t3:
        bad.append(f"{p3}: TEMPLATE 不是 ChatML，与训练编码不同源")
    for param in ("temperature 0.1", "top_k 20", "repeat_penalty 1.02",
                  "stop <|im_start|>"):
        if param not in t1:
            bad.append(f"{p1}: 参数与强化报告声明漂移，缺 {param}")
    # num_gpu=30 已于 11-07 实测证伪（超配打崩服务）：层数必须按部署时空闲显存推导，
    # 禁止在 Modelfile 里硬编码；审计从「必查 num_gpu 30」反转为「禁止硬编码」
    for p, txt in ((p3, t3), (p1, t1)):
        if re.search(r"^PARAMETER\s+num_gpu\s+\d+", txt, re.M):
            bad.append(f"{p}: 硬编码 num_gpu（11-07 已证伪超配打崩服务），须按空闲显存推导")
    return not bad, "; ".join(bad) or "两份 Modelfile 均与当前契约/文档同源"


chk("Modelfile 契约新鲜度", modelfile_audit)


def builder_check_breadth():
    p = subprocess.run([sys.executable, "scripts/build_wm_modelfile.py", "--check"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0 and "8 族" not in out, f"rc={p.returncode} out={out.strip()[:160]}"


chk("build_wm_modelfile --check 覆盖 12 族", builder_check_breadth)


# ---------------------------------------------------------------- offline replay
def offline_pipeline_replay():
    """把生成器真值当模型输出回放整条评测链路（不是模型实测，只验尺子）。

    期望答案走 extract_json -> apply_guard -> judge 后 raw 与 delivery 都应 100%；
    任何 FAIL 都是评测链路自己的假失败（数组键、design 子树、闸门字面等）。
    """
    import build_worldmodel_sft as W
    import build_worldmodel_v2 as V2
    import eval_worldmodel as E
    from guard_hooks import apply_guard
    rng = random.Random(20261108)
    gens = {
        "removal": W.gen_removal_mrr, "roughness": W.gen_roughness,
        "fea_fos": W.gen_fea_fos, "collision": W.gen_collision_gcode,
        "tolerance": W.gen_tolerance, "geom_delta": W.gen_geometric_delta,
        "mass_props": W.gen_mass_props,
        "design": V2.gen_design_from_requirement,
        "process": V2.gen_machining_process_plan,
    }
    bad = []
    n = raw_ok = delivery_ok = 0
    for fam, gen in gens.items():
        for _ in range(3):
            rec = gen(rng)
            if rec is None:
                continue
            exp = json.loads(rec["messages"][2]["content"])
            u = rec["messages"][1]["content"]
            resp = json.dumps(exp, ensure_ascii=False)
            raw = E.extract_json(resp)
            gres = apply_guard(resp, prompt=u, scenario=rec.get("scenario"),
                               tol_rel=E.REL_TOL)
            obj = E._wrap(gres.get("final_world_state"))
            ok_raw = E.judge(fam, exp, raw)[0]
            ok_g = E.judge(fam, exp, obj)[0]
            n += 1
            raw_ok += int(ok_raw)
            delivery_ok += int(ok_g)
            if not (ok_raw and ok_g):
                bad.append(f"{fam}: raw={ok_raw} delivery={ok_g} "
                           f"action={gres['action']} miss={E.judge(fam, exp, obj)[2][:3]}")
    return not bad, f"expectation replay {raw_ok}/{n} raw, {delivery_ok}/{n} delivery; " \
                    + ("; ".join(bad[:3]) if bad else "no false failures")


chk("端到端评测链路标准答案回放", offline_pipeline_replay)


def known_vulnerability_regression():
    """FIX H11（2026-11-08 审计）：本脚本原先 27 项全部由被测实现自证——
    同一套代码既是被审计对象又是裁判，任何一类真实缺陷都照不到。这里挂上
    独立的已知漏洞回归集 `scripts/wm_vuln_regression.py`（来自审计复现脚本，
    断言方向为「漏洞必须不复现」），把审计从自证变成外部口径。
    """
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "wm_vuln_regression.py")],
                       capture_output=True, text=True, cwd=ROOT,
                       encoding="utf-8", errors="replace")
    lines = [l for l in (r.stdout or "").splitlines() if l.startswith("=== 漏洞回归")]
    fail = [l for l in (r.stdout or "").splitlines() if l.startswith("[FAIL]")]
    return r.returncode == 0, (lines[0] if lines else f"rc={r.returncode}") +         ("; " + "; ".join(fail[:3]) if fail else "")


chk("已知 12 项漏洞回归集（H1~H11，非自证）", known_vulnerability_regression)


# ---------------------------------------------------------------- summary
npass = sum(1 for _, ok, _ in RESULTS if ok)
print(f"\n=== AUDIT {npass}/{len(RESULTS)} PASS ===")
for name, ok, detail in RESULTS:
    if not ok:
        print(f"  FAIL {name}: {detail}")
sys.exit(0 if npass == len(RESULTS) else 1)
