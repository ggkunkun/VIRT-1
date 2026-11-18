#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界模型护栏门禁聚合入口（CI / pre-push 单点）。

背景：2026-11-08 修复 12 项护栏漏洞后，回归能力散落在多个脚本里，
没有任何一个入口能"一条命令判定全链路是否退化"。人力靠记忆逐个跑，
漏跑一个就等于门禁失守。本脚本把全部自检收敛成单一出口。

设计原则（与仓库既有的可证伪性纪律一致）：
  - 任一必需项失败 → 退出码 1，绝不"报错但绿"
  - 缺依赖导致的跳过 → 显式打印 SKIP 并在汇总里计数，不计入 PASS
  - 必需项不允许 SKIP：一旦关键护栏自检因环境缺失被跳过，同样判红
    （宁可红，也不要假装验证过）

用法：
  .venv/Scripts/python.exe scripts/wm_ci_gate.py
  .venv/Scripts/python.exe scripts/wm_ci_gate.py --quiet
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# (显示名, 脚本, 参数, 是否必需)
#   必需 = 该项在环境正常时必须 PASS；SKIP 即判红
GATES = [
    ("契约↔解码同源", "wm_contract.py", [], True),
    ("闸门归一", "wm_gate.py", [], True),
    ("护栏三层钩子", "guard_hooks.py", [], True),
    ("反幻觉护栏", "anti_hallucination_guard.py", ["--selftest"], True),
    ("L2 复算器", "wm_verifier.py", ["--selftest"], True),
    ("12 项漏洞回归", "wm_vuln_regression.py", [], True),
    ("缺参假绿探针", "wm_missing_input_probe.py", [], True),
    ("全链路审计", "wm_audit_full.py", [], False),
    ("Modelfile 契约同源", "build_wm_modelfile.py", ["--check"], False),
    # 评测纯度：12 族生成器模板 49/49 全部被训练集覆盖，模板级去污后干净
    # 用例为 0，等于在同源模板上自测。这一项故意标为必需——指标不能证明
    # 泛化这件事，比任何一条护栏回归都更该让门禁变红。
    ("评测去污纯度", "wm_eval_purity.py", [], True),
    # 题面改写归族：评测题面换成生产口吻后，场景推断必须仍归本族。缺这一项，
    # 改写层一旦把「表面质量」写成「质量」、把「设计」写成「建模规格」，
    # 评测就会静默跑在错误族上（本轮 FIX H5/H6 即由此暴露）。
    ("题面改写归族", "wm_eval_paraphrase.py", ["--samples", "60"], True),
    # 独立回归集（非自证）：上面的漏洞回归场景与真值都由本仓库自写、真值直接取
    # 被测求解器，属同源自证。本项换一套人工样本（冻结在 data/holdout），
    # 真值改由脚本内置解析式独立算出，并对每题灌入偏移 30% 的错误答案确认必须被拒。
    # 必需项：这一项一旦依靠被测实现自己证明自己，前面所有 PASS 的可信度都要打折。
    ("独立回归集", "wm_holdout_regression.py", [], True),
    # 12 族零误拦（生产链路）：不传 scenario，只用题面还原场景 + 求解器复算，
    # 断言 12 族 × 200 条零误拦、零数值偏差、零"未背书却放行"。与独立回归集互补：
    # 后者验"错答必拒"，前者验"对答必放"，缺一半就只剩单向门。
    ("12 族零误拦", "wm_zero_block_12fam.py", [], True),
    # 端到端孪生一致性：生成器场景真值 → wm_verifier.recompute → 与样本期望答案逐字段比对。
    # 证明"生成器算一套、求解器另算一套"的静默漂移不存在（本项首跑即抓出 H62 牌号被
    # 当成 h=62 的真实缺陷）。
    ("端到端孪生一致性", "wm_end2end_parity.py", [], True),
]

# 视为"环境依赖缺失而跳过"的特征串
SKIP_HINTS = ("ModuleNotFoundError", "ImportError", "No module named",
              "cannot import", "not installed")


def run_one(script: str, args: list[str]) -> tuple[str, int, str]:
    path = os.path.join(SCRIPTS, script)
    if not os.path.isfile(path):
        return "MISSING", 127, f"脚本不存在: {path}"
    try:
        r = subprocess.run([PY, path, *args], capture_output=True, text=True,
                           cwd=SCRIPTS, timeout=900, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 124, "执行超时 900s"
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    tail = "\n".join([ln for ln in out.splitlines() if ln.strip()][-1:])
    if r.returncode == 0:
        # 退出码 0 但打印了导入失败，同样视为不可信
        for hint in SKIP_HINTS:
            if hint in out:
                return "SKIP", 0, tail
        return "PASS", 0, tail
    return "FAIL", r.returncode, tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="只打印汇总与失败详情")
    args = ap.parse_args()

    rows, failed, skipped = [], [], []
    for name, script, sargs, required in GATES:
        status, rc, tail = run_one(script, sargs)
        tag = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP",
               "MISSING": "MISSING", "TIMEOUT": "TIMEOUT"}[status]
        rows.append((name, script, tag, required, rc, tail))
        if tag == "PASS":
            continue
        if tag == "SKIP" and not required:
            skipped.append(name)
            continue
        failed.append((name, script, tag, tail))
        if not args.quiet:
            print(f"[{tag}] {name} ({script}) rc={rc}\n        {tail}")

    width = max(len(r[0]) for r in rows) + 2
    print("=" * 78)
    print("世界模型护栏门禁汇总")
    print("=" * 78)
    for name, script, tag, required, rc, _ in rows:
        mark = "必需" if required else "可选"
        print(f"  {name:<{width}} {script:<30} {tag:<8} {mark}")
    print("-" * 78)
    npass = sum(1 for r in rows if r[2] == "PASS")
    print(f"PASS {npass}/{len(rows)}    FAIL {len(failed)}    SKIP(可选) {len(skipped)}")
    if skipped:
        print("  跳过项：" + ", ".join(skipped))
    if failed:
        print("\n判红原因：", file=sys.stderr)
        for name, script, tag, tail in failed:
            print(f"  [{tag}] {name} ({script}) -> {tail}", file=sys.stderr)
        return 1
    print("[gate] ALL PASS：护栏全链路无退化")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
