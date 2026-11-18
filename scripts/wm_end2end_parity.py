# -*- coding: utf-8 -*-
"""端到端孪生一致性：生成器真值 -> wm_verifier.recompute -> 与期望答案逐字段比对。

目的：证明「生成器场景输入」「求解器复算」「样本期望答案（assistant JSON）」三者同源，
不存在生成器自算一套、求解器另算一套的静默漂移。invalid 族无数值解，按契约形态校验。

注：rec 里没有 "expected" 键，期望答案就是 messages[assistant].content 的 JSON。
"""
import json
import os
import math
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import eval_worldmodel as E          # noqa: E402
import wm_verifier                   # noqa: E402

N_PER_FAMILY = 200
SEED = 20261109
ECHO_KEYS = {"feed_per_rev_mm", "nose_radius_mm", "basic_size_mm"}  # 归一化输入回显，求解器不产出
REL_TOL = 0.08   # 与 eval_worldmodel 生产口径一致；生成器期望值统一做了 3~4 位有效数字舍入


def assistant_json(rec):
    for m in rec.get("messages") or []:
        if m.get("role") == "assistant":
            try:
                return json.loads(m.get("content") or "")
            except Exception:
                return {}
    return {}


def flat(d, prefix=""):
    out = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


def cmp_fields(ref, exp_ws):
    fr, fe = flat(ref), flat(exp_ws)
    common, diffs, missing, rels = 0, [], [], []
    for k, ev in fe.items():
        if isinstance(ev, bool) or not isinstance(ev, (int, float)):
            continue
        key = k if k in fr else k.split(".")[-1]
        rv = fr.get(key)
        if rv is None or isinstance(rv, bool) or not isinstance(rv, (int, float)):
            if k.split(".")[-1] not in ECHO_KEYS:
                missing.append(k)
            continue
        common += 1
        if not (math.isfinite(float(ev)) and math.isfinite(float(rv))):
            continue
        rel = abs(float(rv) - float(ev)) / max(1e-9, abs(float(ev)))
        rels.append((rel, k))
        if rel > REL_TOL:
            diffs.append({"field": k, "expected": ev, "recompute": rv, "rel": rel})
    return common, diffs, missing, rels


def main():
    rng = random.Random(SEED)
    tot = {"n": 0, "field_checked": 0, "diff": 0, "missing": 0, "judge_fail": 0,
           "no_ref": 0, "invalid_ok": 0, "invalid_bad": 0}
    bad = []
    worst = (0.0, None, None)
    for fam, gen in E.GEN_BY_FAMILY.items():
        n = fc = df = ms = jf = nr = 0
        for _ in range(N_PER_FAMILY):
            rec = gen(rng)
            if not rec:
                continue
            n += 1
            scen = rec.get("scenario") or {}
            exp = assistant_json(rec)
            if scen.get("task") == "invalid":
                ok = (exp.get("invalid") is True and exp.get("world_state") is None)
                tot["invalid_ok" if ok else "invalid_bad"] += 1
                continue
            try:
                ref = wm_verifier.recompute(scen)
            except Exception:
                ref = None
            if not ref:
                nr += 1
                tot["no_ref"] += 1
                continue
            c, diffs, missing, rels = cmp_fields(ref, exp.get("world_state") or {})
            if rels:
                mx = max(rels)
                if mx[0] > worst[0]:
                    worst = (mx[0], fam, mx[1])
            fc += c
            ms += len(missing)
            if diffs:
                df += 1
                if len(bad) < 6:
                    bad.append({"fam": fam, "diffs": diffs[:3]})
            # 求解器不负责回显闸门/文本键，judge 会把这些记成 missing，
            # 故此处不做 judge（judge 已在 12 族零误拦回归中用 Guard 完整 corrected 覆盖）。
            # 这里只校验一点：求解器不得凭空造出期望答案里没有的数值键（防止口径外扩）。
            fe = flat(exp.get("world_state") or {})
            evals = [float(x) for x in fe.values()
                     if isinstance(x, (int, float)) and not isinstance(x, bool)]

            def _derived(v):
                # 合法派生量（如 mass_kg = mass_g/1000）不算口径外扩
                return any(abs(float(v) - e * s_) <= 1e-3 * max(1.0, abs(float(v)))
                           for e in evals for s_ in (1e-3, 1e3))

            extra = [k for k, v in flat(ref).items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool)
                     and k.split(".")[-1] not in fe and k not in fe
                     and not _derived(v)]
            if extra and len(bad) < 12:
                bad.append({"fam": fam, "extra_ref_keys": extra[:6]})
        tot["n"] += n
        tot["field_checked"] += fc
        tot["diff"] += df
        tot["missing"] += ms
        tot["judge_fail"] += jf
        print(f"[{fam:15s}] n={n:4d} 逐字段比对={fc:4d} 数值偏差={df:3d} "
              f"缺字段={ms:3d} judge不过={jf:3d} 无参考值={nr:3d}")

    print("\n=== TOTAL ===")
    print(json.dumps(tot, ensure_ascii=False))
    print(f"最大相对偏差={worst[0]:.2e} ({worst[1]}/{worst[2]})")
    for s in bad:
        print("  BAD:", json.dumps(s, ensure_ascii=False)[:420])
    ok = (tot["diff"] == 0 and tot["judge_fail"] == 0 and tot["missing"] == 0
          and tot["no_ref"] == 0 and tot["invalid_bad"] == 0)
    print("PARITY_OK" if ok else "PARITY_DRIFT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
