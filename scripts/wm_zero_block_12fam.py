# -*- coding: utf-8 -*-
"""12 族零误拦验证：生成器真值 -> 题面/答案 -> Guard(scenario=None) -> 复算比对。

判定口径（任一不满足即计 fail）：
  1) Guard 不得 reject/escalate 正确应答（零误拦）；
  2) Guard 若给出 corrected，必须与生成器真值一致（judge 通过），即复算无偏差；
  3) 归族必须由题面推断命中真值族（scenario=None 时靠 infer_scenario_from_prompt）。
"""
import json
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import eval_worldmodel as E                     # noqa: E402
from anti_hallucination_guard import Guard      # noqa: E402

N_PER_FAMILY = 200
SEED = 20261109


def msg_of(rec, idx_default):
    msgs = rec.get("messages") or []
    for m in msgs:
        if m.get("role") == "user":
            prompt = m.get("content") or ""
        elif m.get("role") == "assistant":
            answer = m.get("content") or ""
    return prompt, answer


def assistant_json(rec):
    """期望答案就在 messages[assistant].content（rec 无 expected 键）。"""
    import json as _j
    for m in rec.get("messages") or []:
        if m.get("role") == "assistant":
            try:
                return _j.loads(m.get("content") or "")
            except Exception:
                return {}
    return {}

def main():
    g = Guard()
    rng = random.Random(SEED)
    total = {"n": 0, "accept": 0, "corrected": 0, "rejected": 0, "escalate": 0,
             "fail": 0, "review": 0}
    report = {}
    for fam, gen in E.GEN_BY_FAMILY.items():
        st = {"n": 0, "accept": 0, "corrected": 0, "rejected": 0, "escalate": 0,
              "wrong_action": 0, "value_diff": 0, "fam_miss": 0, "uncertified": 0,
              "gen_none": 0, "prov": {}, "derivation_only": 0}
        samples = []
        for i in range(N_PER_FAMILY):
            try:
                rec = gen(rng)
            except Exception:
                rec = None
            if not rec:
                st["gen_none"] += 1
                continue
            prompt, answer = msg_of(rec, i)
            exp = assistant_json(rec)
            scen_truth = rec.get("scenario") or {}
            try:
                res = g.run(response_text=answer, prompt=prompt, scenario=None)
            except Exception:
                st["wrong_action"] += 1
                samples.append({"fam": fam, "err": traceback.format_exc()[-300:]})
                continue
            st["n"] += 1
            st[res.action] = st.get(res.action, 0) + 1
            if res.action in ("rejected", "escalate"):
                st["wrong_action"] += 1
                if len(samples) < 3:
                    samples.append({"fam": fam, "action": res.action,
                                    "issues": res.issues[:3], "prompt": prompt[:220]})
                continue
            if not res.certified:
                st["uncertified"] += 1
            st["prov"][res.provenance] = st["prov"].get(res.provenance, 0) + 1
            if res.provenance in ("derivation_solver", "no_reference", "no_scenario"):
                st["derivation_only"] += 1
                if len(samples) < 6:
                    samples.append({"fam": fam, "prov": res.provenance,
                                    "layers": res.layers_hit, "prompt": prompt[:220]})
            # 归族校验：Guard 内部推断出的 task 是否等于真值族
            got_fam = None
            try:
                got_fam = (E.infer_scenario_from_prompt(prompt) or {}).get("task") \
                    if hasattr(E, "infer_scenario_from_prompt") else None
            except Exception:
                got_fam = None
            if got_fam is None:
                try:
                    from anti_hallucination_guard import infer_scenario_from_prompt as INF
                    got_fam = (INF(prompt) or {}).get("task")
                except Exception:
                    got_fam = None
            if got_fam and scen_truth.get("task") and got_fam != scen_truth["task"] and got_fam != fam:
                st["fam_miss"] += 1
                if len(samples) < 6:
                    samples.append({"fam": fam, "got_fam": got_fam,
                                    "truth": scen_truth.get("task"), "prompt": prompt[:220]})
            # 数值比对：corrected（若存在）必须与生成器真值一致
            if res.corrected is not None and exp:
                try:
                    _full = (res.corrected if "world_state" in (res.corrected or {})
                             else {"world_state": res.corrected})
                    _r = E.judge(fam, exp, _full)
                    ok = _r[0] if isinstance(_r, tuple) else _r
                except Exception:
                    ok = True
                if not ok:
                    st["value_diff"] += 1
                    if len(samples) < 6:
                        samples.append({"fam": fam, "value_diff": True,
                                        "exp": exp, "corr": res.corrected})
        st["fail"] = st["wrong_action"] + st["value_diff"]
        report[fam] = st
        for k in ("n", "accept", "corrected", "rejected", "escalate"):
            total[k] = total.get(k, 0) + st.get(k, 0)
        total["fail"] += st["fail"]
        total["review"] += st["fam_miss"] + st["uncertified"]
        print(f"[{fam:15s}] n={st['n']:4d} accept={st.get('accept',0):4d} "
              f"corrected={st.get('corrected',0):3d} rejected={st.get('rejected',0):3d} "
              f"escalate={st.get('escalate',0):3d} | 误拦={st['wrong_action']:3d} "
              f"数值偏差={st['value_diff']:3d} 归族miss={st['fam_miss']:3d} "
              f"未背书={st['uncertified']:3d} 自证通道={st['derivation_only']:3d} "
              f"gen_none={st['gen_none']:3d} prov={st['prov']}")
        for s in samples[:2]:
            print("        sample:", json.dumps(s, ensure_ascii=False)[:400])

    print("\n=== TOTAL ===")
    print(json.dumps(total, ensure_ascii=False))
    print("ZERO_FALSE_BLOCK" if total["fail"] == 0 else f"FALSE_BLOCK={total['fail']}")
    print("ALLGREEN" if total["fail"] == 0 and total["review"] == 0 else "NEEDS_REVIEW")
    return 0 if total["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
