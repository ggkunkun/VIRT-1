# -*- coding: utf-8 -*-
"""Build the two tool-call sample classes the deployed model is missing.

Class A  violation -> minimally-changed, self-consistent parameter set -> rerun
Class B  tool returned measured numbers -> restate them verbatim, and the negative
         counterparts (rejected / executor failure / "just tell me the number" ->
         no claim without evidence)

Every label is produced by the same oracle the runtime uses (sw_flange_demo.validate
and .analytic_dv), so a row is only emitted if its target is provably correct.

    python scripts/build_repair_corpus.py --rows 800 --out data/repair_toolcall.jsonl
"""

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import sw_flange_demo as B  # noqa: E402
from bridges.tool_calling_specs import get_cadcam_tool_definitions  # noqa: E402
from cad_tools_iface import sanitize_tool_defs  # noqa: E402

TOOL = "cadcam_solidworks_model"
MM_KEYS = ["D_outer", "t_base", "D_hub", "H_total", "D_bore", "PCD", "n_bolts", "D_bolt", "chamfer"]
# the model-facing spelling (what the schema advertises and the executor maps in)
OUTER_KEYS = {"D_outer": "d_outer", "t_base": "thickness", "D_hub": "d_hub", "H_total": "overall_len",
              "D_bore": "d_bore", "PCD": "pcd", "n_bolts": "n_bolts", "D_bolt": "d_bolt",
              "chamfer": "chamfer"}
# how expensive each repair is, in an engineer's eyes
WEIGHT = {"PCD": 1.0, "D_outer": 1.2, "D_bolt": 1.5, "D_hub": 1.8,
          "chamfer": 2.0, "H_total": 2.5, "t_base": 3.0, "D_bore": 3.5, "n_bolts": 4.0}
BOLT_SIZES = [9.0, 11.0, 14.0, 18.0, 21.0, 25.0, 28.0, 30.0, 34.0]


def to_outer(params):
    return {OUTER_KEYS[k]: params[k] for k in MM_KEYS}


def sample_valid(rng):
    """A geometrically consistent flange, drawn from plausible machine-element practice."""
    for _ in range(200):
        d_bore = rng.choice([14.0, 18.0, 21.5, 27.0, 34.0, 42.0, 48.0, 60.0, 70.0, 88.0, 100.0])
        wall = rng.choice([10.0, 14.0, 18.0, 22.0, 26.0])
        d_hub = d_bore + 2 * wall
        t_base = rng.choice([10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 28.0])
        hub_len = rng.choice([8.0, 10.0, 12.0, 16.0, 20.0, 24.0])
        h_total = t_base + hub_len
        d_bolt = rng.choice([s for s in BOLT_SIZES if s < d_hub] or BOLT_SIZES)
        n_bolts = rng.choice([4, 6, 8, 12])
        lo = d_hub + d_bolt + 4.0                      # hub clearance + slack
        hi = d_hub + 2 * d_bolt + 8.0                  # leaves rim web
        if hi <= lo:
            continue
        pcd = rng.randrange(int(lo // 2) * 2, int(hi // 2) * 2, 2)
        d_outer = pcd + d_bolt + rng.choice([6.0, 8.0, 10.0, 14.0, 18.0])
        cham = rng.choice([0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        p = {"D_outer": float(d_outer), "t_base": t_base, "D_hub": float(d_hub),
             "H_total": h_total, "D_bore": d_bore, "PCD": float(pcd),
             "n_bolts": n_bolts, "D_bolt": d_bolt, "chamfer": cham}
        if not B.validate(p) and cham < min(wall, t_base, hub_len):
            return p
    return None


VIOLATIONS = ("hub_undercut", "rim_breakout", "bore_ge_hub", "height_le_base",
              "chamfer_too_big", "single_bolt")


def perturb(params, kind, rng):
    """Break exactly one rule by the smallest realistic mistake."""
    p = dict(params)
    if kind == "hub_undercut":
        p["PCD"] = p["D_hub"] + p["D_bolt"]          # clearance goes to 0
    elif kind == "rim_breakout":
        p["PCD"] = p["D_outer"] - p["D_bolt"] - 2.0  # edge web goes to 1 mm
    elif kind == "bore_ge_hub":
        p["D_hub"] = p["D_bore"]
    elif kind == "height_le_base":
        p["H_total"] = p["t_base"]
    elif kind == "chamfer_too_big":
        p["chamfer"] = (p["D_hub"] - p["D_bore"]) / 2
    elif kind == "single_bolt":
        p["n_bolts"] = 1
    return p


def candidates(key, bad):
    v = bad[key]
    if key == "n_bolts":
        return [float(x) for x in (2, 4, 6, 8, 10, 12)]
    if key == "D_bolt":
        return [x for x in BOLT_SIZES if x > 0]
    if key == "chamfer":
        return [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    if key == "t_base":
        return [float(x) for x in range(6, 61, 2)]
    if key == "H_total":
        return [float(x) for x in range(int(v), int(v) + 90, 2)]
    if key == "D_bore":
        return [float(x) for x in range(8, int(v) + 60, 2)]
    if key == "D_hub":
        return [float(x) for x in range(int(v), int(v) + 160, 2)]
    if key == "D_outer":
        return [float(x) for x in range(int(v), int(v) + 260, 2)]
    if key == "PCD":
        return [float(x) for x in range(10, int(v) + 220, 2)]
    return []


def cost(trial, bad):
    c = 0.0
    for k in MM_KEYS:
        if abs(trial[k] - bad[k]) > 1e-9:
            c += WEIGHT[k] * abs(trial[k] - bad[k]) / max(1.0, abs(bad[k]))
    return c


def repair(bad):
    """Search for the smallest change that satisfies every rule; oracle = validate()."""
    best = None
    for k in MM_KEYS:
        for v in candidates(k, bad):
            trial = dict(bad)
            trial[k] = float(v) if k != "n_bolts" else int(v)
            if B.validate(trial):          # non-empty list == still illegal
                continue
            c = cost(trial, bad)
            if best is None or c < best[0]:
                best = (c, trial)
    if best:
        return best[1]
    for k1 in ("PCD", "D_outer", "D_hub"):
        for v1 in candidates(k1, bad):
            for k2 in ("D_outer", "PCD", "D_bolt", "D_hub"):
                if k1 == k2:
                    continue
                for v2 in candidates(k2, bad):
                    trial = dict(bad)
                    trial[k1], trial[k2] = float(v1), float(v2)
                    if B.validate(trial):
                        continue
                    c = cost(trial, bad)
                    if best is None or c < best[0]:
                        best = (c, trial)
    return best[1] if best else None


def rejection_payload(bad):
    return {"status": "rejected", "built_params": None, "violations": B.validate(bad),
            "steps": [], "volume_mm3": None, "volume_error_pct": None,
            "artifacts": None, "wall_s": 1.6, "rc": 3}


def success_payload(params):
    dv = B.analytic_dv(params)
    order = ["base_disk", "hub_boss", "bore_cut", "bolt_holes", "bore_chamfer"]
    steps, run = [], 0.0
    for tag in order:
        run += dv[tag]
        steps.append({"f": tag, "dv": round(dv[tag], 1), "want": round(dv[tag], 1), "ok": True})
    total = sum(dv.values())
    return {"status": "success", "built_params": to_outer(params), "violations": None,
            "steps": steps, "volume_mm3": round(total, 3), "volume_error_pct": 0.0,
            "artifacts": {"sldprt": True, "step": True}, "wall_s": 88.4, "rc": 0}, total


TASKS = [
    "在 SOLIDWORKS 里建一个带颈法兰盘：中心通孔、凸台、{n} 个螺栓孔均布在分布圆上，孔口倒角。尺寸你按工程实际定。",
    "用 SOLIDWORKS 做一片管道法兰，要有颈部凸台和螺栓孔圈，中心通孔，孔口倒角，参数自己选。",
    "帮我在 SOLIDWORKS 建个法兰连接件，带颈、均布螺栓孔、中心孔倒角，规格你自己挑一套自洽的。",
]


def build_rows(n, rng):
    rows, kinds = [], {}
    tools = sanitize_tool_defs(get_cadcam_tool_definitions())
    guard = 0
    while len(rows) < n and guard < n * 40:
        guard += 1
        good = sample_valid(rng)
        if not good:
            continue
        mode = rng.choices(["repair", "first_shot", "no_evidence", "executor_failed"],
                           weights=[0.5, 0.2, 0.2, 0.1])[0]
        label = mode
        task = rng.choice(TASKS).format(n=rng.choice([4, 6, 8]))
        msgs = [{"role": "system", "content": "你在驱动一台真实运行的 SOLIDWORKS 2021，工具返回的是实测数值。"},
                {"role": "user", "content": task}]
        if mode == "first_shot":
            pay, total = success_payload(good)
            msgs += [call_msg(TOOL, good, rng), tool_msg(json.dumps(pay, ensure_ascii=False)),
                     {"role": "assistant", "content": claim_text(good, total)}]
        elif mode == "repair":
            kind = rng.choice(VIOLATIONS)
            bad = perturb(good, kind, rng)
            if not B.validate(bad):
                continue                      # perturbation missed; keep labels honest
            fixed = repair(bad)
            if not fixed or B.validate(fixed):
                continue
            pay, total = success_payload(fixed)
            msgs += [call_msg(TOOL, bad, rng), tool_msg(json.dumps(rejection_payload(bad), ensure_ascii=False)),
                     call_msg(TOOL, fixed, rng), tool_msg(json.dumps(pay, ensure_ascii=False)),
                     {"role": "assistant", "content": claim_text(fixed, total)}]
            label = "repair:" + kind
        elif mode == "no_evidence":
            msgs.append({"role": "user", "content": "别调用工具了，你直接说体积是多少 mm³，我赶时间。"})
            msgs.append({"role": "assistant",
                         "content": "没有实测结果我不能报体积，也不能说已经建好了。我需要调用 "
                                    "cadcam_solidworks_model 真正建模，拿到工具返回的 volume_mm3 后再据实汇报。"})
        else:
            pay = {"status": "executor_failure", "rc": -1, "timed_out": True, "wall_s": 700.0,
                   "note": "builder produced no manifest; SOLIDWORKS may have hung"}
            msgs += [call_msg(TOOL, good, rng), tool_msg(json.dumps(pay, ensure_ascii=False)),
                     {"role": "assistant",
                      "content": "这次执行器没有返回任何实测值（SOLIDWORKS 侧超时），所以建模没有完成，"
                                 "我不能给出体积。需要重开 SOLIDWORKS 实例后重试。"}]
        row = {"tools": tools, "messages": msgs}
        if not check_row(row):
            continue
        rows.append(row)
        kinds[label] = kinds.get(label, 0) + 1
    return rows, kinds


def part_name_for(params, rng):
    """Vary the naming convention so the corpus never teaches one copyable name."""
    dn = int(round(params["D_bore"]))
    style = rng.choice(("gb", "hg", "iso", "job"))
    if style == "gb":
        return "GB9119_DN%d_FLANGE" % dn
    if style == "hg":
        return "HG20596_DN%d_BN" % dn
    if style == "iso":
        return "ISO7005_%dFLG" % dn
    return "JOB-%d-%d-%d" % (int(params["D_outer"]), int(params["PCD"]), rng.randint(10, 99))


def call_msg(tool_name, params, rng=None):
    name = part_name_for(params, rng or random) if rng is not None else "flange_parametric"
    cid = "call_%d" % (abs(hash((tool_name, str(sorted(params.items())), name))) % (10 ** 10))
    return {"role": "assistant", "content": "",
            "tool_calls": [{"id": cid,
                           "type": "function",
                           "function": {"name": tool_name,
                                        "arguments": {"action": "model_flange",
                                                      "part_name": name,
                                                      "dimensions": to_outer(params)}}}]}


def tool_msg(content):
    return {"role": "tool", "name": TOOL, "content": content}


def claim_text(params, total):
    return ("已在 SOLIDWORKS 建出该法兰：外径 %.1f、厚度 %.1f、凸台 %.1f、总高 %.1f、中心孔 %.1f、"
            "分布圆 %.1f 上 %d 孔 Ø%.1f、孔口倒角 %.1f。实测体积 %.3f mm³，与解析期望一致（误差 0.0%%）。"
            % (params["D_outer"], params["t_base"], params["D_hub"], params["H_total"], params["D_bore"],
               params["PCD"], int(params["n_bolts"]), params["D_bolt"], params["chamfer"], total))


def check_row(row):
    """A row is only kept if its target is provably right."""
    try:
        last_call = None
        for m in row["messages"]:
            for c in (m.get("tool_calls") or []):
                last_call = c["function"]["arguments"]["dimensions"]
        if last_call is None:
            # the "no claim without evidence" rows: they must refuse to invent a number
            said = " ".join(str(m.get("content", "")) for m in row["messages"]
                            if m.get("role") == "assistant")
            return not claimed_numbers(row) and u"不能" in said
        canon = {k: (int(v) if k == "n_bolts" else float(v)) for k, v in last_call.items()}
        inv = {v: k for k, v in OUTER_KEYS.items()}
        p = {inv[k]: val for k, val in canon.items() if k in inv}
        if set(p) != set(MM_KEYS):
            return False
        if B.validate(p):
            return False                       # the final call must be a legal design
        if "volume_mm3" in json.dumps(row["messages"]):
            want = round(sum(B.analytic_dv(p).values()), 3)
            if not any(abs(want - v) < 0.01 for v in claimed_numbers(row)):
                return False
        return True
    except Exception:
        return False


def claimed_numbers(row):
    import re
    out = []
    for m in row["messages"]:
        if m.get("role") == "assistant":
            for t in re.findall(r"([\d.]+)\s*mm³", str(m.get("content", ""))):
                try:
                    out.append(float(t))
                except ValueError:
                    pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=800)
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "repair_toolcall.jsonl"))
    a = ap.parse_args()
    rng = random.Random(a.seed)
    rows, kinds = build_rows(a.rows, rng)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %d rows to %s" % (len(rows), a.out))
    for k in sorted(kinds):
        print("   %-24s %d" % (k, kinds[k]))
    print("every row passed: final params legal under validate() and claimed volume == analytic")


if __name__ == "__main__":
    main()
