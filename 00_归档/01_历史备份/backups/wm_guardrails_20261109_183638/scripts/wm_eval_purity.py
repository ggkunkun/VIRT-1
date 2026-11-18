#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测集去污纯度探针 —— 评测指标到底能不能证明泛化。

背景（2026-11-08）：
  FIX H9 只挡「prompt 逐字重合」，挡不住「同一模板换个数字」。实测把
  wm_leak_audit.template_of()（数字脱敏）这一层叠到 eval_worldmodel 上，
  模板级去污后可用用例直接掉到 0 —— 说明 GEN_BY_FAMILY 生成的评测用例
  与 data/sft 训练集是**同一套模板、只换数字**，属于同源自测。

本脚本把这件事从「一次性的手工发现」固化成可复跑的检查：按族统计生成器
产出的模板有多少已被训练集覆盖，剩余多少是可用的干净用例。

判定口径：
  每族「模板级去污后可用用例数」>= --min-clean（默认 1）才算该族具备
  泛化证明力。低于阈值即非零退出——评测本身不干净时，不要让指标看起来
  像是通过验证。

用法：
  .venv/Scripts/python.exe scripts/wm_eval_purity.py
  .venv/Scripts/python.exe scripts/wm_eval_purity.py --min-clean 5 --samples 400
"""
from __future__ import annotations

import argparse
import random
import sys

import eval_worldmodel as E
from wm_leak_audit import template_of


def prompts_of(gen, rng, tries: int):
    """取生成器产出的 user prompt 模板（去重）。生成器返回 None 属正常。"""
    seen = set()
    for _ in range(tries):
        rec = gen(rng)
        if not rec:
            continue
        try:
            u = rec["messages"][1]["content"]
        except Exception:
            continue
        if u:
            seen.add(template_of(u))
    return seen


def fidelity(samples: int):
    """改写保真（FIX H10）：改写只准换措辞，不准换输入与期望值。

    独立口径：用**被测的**场景推断器去解析改写后的题面，把解析出的数值与
    生成器原始 scenario.inputs 逐字段对比。改写器自己不参与裁判，避免
    「自己改自己验」的自证循环。任何一处数值被改动都会被抓出来。
    """
    import wm_eval_paraphrase as P
    from anti_hallucination_guard import infer_scenario_from_prompt

    rows, bad = [], []
    for fam, gen in E.GEN_BY_FAMILY.items():
        raw = getattr(gen, "__wrapped__", gen)
        ok = chk = 0
        for k in range(samples):
            rec = raw(random.Random(4242 + k))
            if not rec:
                continue
            base = (rec.get("scenario") or {}).get("inputs") or {}
            exp_before = rec["messages"][2]["content"]
            new = P.rewrite(rec, fam, random.Random(4242 + k))
            if not new:
                continue
            if rec["messages"][2]["content"] != exp_before:  # 期望值必须原封不动
                bad.append((fam, ["期望值被改写"], new[:120]))
                continue
            got = (infer_scenario_from_prompt(new) or {}).get("inputs") or {}
            chk += 1
            mism = []
            for key, v in base.items():
                if key not in got or got[key] is None:
                    continue          # 推断器没解析该字段 → 由归族自测负责，不算篡改
                gv = got[key]
                if isinstance(v, (list, tuple)) and isinstance(gv, (list, tuple)):
                    if len(v) != len(gv) or any(
                            abs(float(a) - float(b)) > 1e-9 * max(1.0, abs(float(a)))
                            for a, b in zip(v, gv)):
                        mism.append(key)
                elif isinstance(v, (int, float)) and not isinstance(v, bool) \
                        and isinstance(gv, (int, float)):
                    if abs(float(v) - float(gv)) > 1e-9 * max(1.0, abs(float(v))):
                        mism.append(f"{key}({v}→{gv})")
            if mism:
                bad.append((fam, mism, new[:120]))
            else:
                ok += 1
        rows.append((fam, ok, chk))
    return rows, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=300,
                    help="每族最多采样多少次生成器调用")
    ap.add_argument("--min-clean", type=int, default=1,
                    help="每族模板级去污后至少需要多少个干净用例，默认 1")
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--fidelity", type=int, default=30,
                    help="每族做多少条改写保真校验（对比改写前后输入与期望值）")
    args = ap.parse_args()

    train_prompts = E.load_train_prompts()
    train_tmpl = {template_of(p) for p in train_prompts if p}
    print("=" * 78)
    print("评测集去污纯度探针")
    print("=" * 78)
    print(f"训练集唯一 prompt {len(train_prompts)} 条 / 模板 {len(train_tmpl)} 个")
    print(f"题面改写层：{'已启用（评测题面与训练措辞脱钩）' if getattr(E, 'PARAPHRASE_READY', False) else '未启用（题面与训练同措辞）'}")
    print(f"每族采样上限 {args.samples} 次；判定阈值 min-clean={args.min_clean}")
    print()
    print(f"{'族':<16}{'生成模板':>10}{'已被训练集覆盖':>16}{'干净可用':>10}   判定")
    print("-" * 78)

    dirty_fams, total_gen, total_clean = [], 0, 0
    for fam, gen in E.GEN_BY_FAMILY.items():
        rng = random.Random(args.seed)
        tmpl = prompts_of(gen, rng, args.samples)
        covered = tmpl & train_tmpl
        clean = tmpl - train_tmpl
        total_gen += len(tmpl)
        total_clean += len(clean)
        ok = len(clean) >= args.min_clean
        if not ok:
            dirty_fams.append(fam)
        print(f"{fam:<16}{len(tmpl):>10}{len(covered):>16}{len(clean):>10}   "
              f"{'OK' if ok else 'NO-CLEAN-DATA'}")

    print("-" * 78)
    ratio = (1 - total_clean / total_gen) * 100 if total_gen else 0.0
    print(f"合计：生成模板 {total_gen} 个，其中 {total_gen - total_clean} 个被训练集覆盖"
          f"（{ratio:.1f}%），干净可用 {total_clean} 个")

    # 第二检查项：改写保真。题面可以换措辞，输入与期望值一个都不许变。
    print()
    print("-" * 78)
    print("改写保真：改写只换措辞，输入与期望值必须原封不动")
    print("-" * 78)
    rows, bad = fidelity(args.fidelity)
    infid = 0
    for fam, ok, chk in rows:
        if chk == 0:
            print(f"{fam:<16} 未校验（本族无可改写样本）")
            continue
        if ok != chk:
            infid += chk - ok
        print(f"{fam:<16} 校验 {chk:>4} 条  一致 {ok:>4} 条   "
              f"{'OK' if ok == chk else 'MISMATCH'}")
    for fam, mism, txt in bad[:5]:
        print(f"  [BAD] {fam}: {mism} | {txt}")
    if bad:
        print(f"[FAIL] 改写篡改 {len(bad)} 条用例的输入/期望值：改写层只能换措辞，"
              f"换了数值就不再是同一道题，指标失去可比性")

    print("-" * 78)
    if dirty_fams:
        print(f"[FAIL] 以下族在同源模板上自测，指标无法证明泛化：{dirty_fams}")
        print("       出路：为这些族改写题面模板/参数组合维度，而不是继续加开关。")
        return 1
    if bad:
        return 1
    print("[PASS] 每族都留有干净用例，且改写前后输入/期望值零变更，评测口径具备泛化证明力")
    return 0


if __name__ == "__main__":
    sys.exit(main())
