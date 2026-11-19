# -*- coding: utf-8 -*-
"""从 logs/training_log.jsonl 渲染每日训练报告（禁止手写覆盖）。"""
import json
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(BASE, "logs", "training_log.jsonl")
OUT = os.path.join(BASE, "reports")
TOTAL_HOURS = 698.0
TARGETS = {"train_dataset": 5000, "instruction_map": 2000, "testcases": 500}


def load():
    if not os.path.exists(LOG):
        return []
    rows = []
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = load()
    if not rows:
        print("no log")
        return
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    date = sorted(by_date)[-1]
    today = by_date[date]

    train_h = sum(r["hours"] for r in today if r["stage"] != "BUILD")
    cum_h = sum(r["hours"] for r in rows if r["stage"] != "BUILD")
    ops_done = sorted({o for r in rows for o in r.get("ops", [])})
    cases = sum(r.get("cases", 0) for r in today if r["stage"] != "BUILD")
    passed = sum(1 for r in today if r.get("result") == "pass")
    score = 0
    scored = [r for r in today if r.get("score")]
    if scored:
        score = round(sum(sum(r["score"].values()) for r in scored) / len(scored), 1)

    manifest_path = os.path.join(BASE, "out", "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    lines = [f"# 训练日报 {date}", ""]
    lines += ["## 今日", "", "| 项 | 值 |", "| --- | --- |",
              f"| 训练时长 | {train_h:.1f}h |",
              f"| 考核用例 | {cases} 条 |",
              f"| 通过模块/条目 | {passed}/{len(today)} |",
              f"| 平均得分 | {score} |",
              f"| 覆盖 L3 | {len(ops_done)}/348 |", ""]

    lines += ["### 明细", "", "| 阶段 | 模块 | 时长 | 样本 | 用例 | 结果 | 次日 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in today:
        lines.append(f"| {r['stage']} | {r['module']} | {r['hours']}h | {r.get('samples',0)} | {r.get('cases',0)} | {r.get('result','-')} | {r.get('next','-')} |")

    lines += ["", "## 累计", "",
              f"- 训练时长：**{cum_h:.1f}h / {TOTAL_HOURS:.0f}h**（{cum_h/TOTAL_HOURS:.1%}）",
              f"- 已登记 L3：**{len(ops_done)} / 348**（{len(ops_done)/348:.1%}）"]

    if manifest:
        c = manifest["counts"]
        lines += ["", "## 资产状态", "", "| 资产 | 实测 | 目标 | 状态 |", "| --- | --- | --- | --- |"]
        for k, label in [("train_dataset", "训练数据集"), ("instruction_map", "指令映射表"), ("testcases", "测试用例库")]:
            got = c.get(k, 0)
            lines.append(f"| {label} | {got} | ≥{TARGETS[k]} | {'达标' if got >= TARGETS[k] else '不足'} |")

    blockers = [b for r in today for b in r.get("blockers", [])]
    lines += ["", "## 阻塞项", ""]
    lines += [f"- {b}" for b in blockers] if blockers else ["- 无"]

    lines += ["", "## 次日计划", ""]
    nxt = [r.get("next") for r in today if r.get("next")]
    lines += [f"- {n}" for n in nxt] if nxt else ["- 按 L2 模块顺序推进"]

    lines += ["", "---", "",
              "> 本报告由 `gen/daily_report.py` 从 `logs/training_log.jsonl` 自动生成；手改无效。", ""]

    path = os.path.join(OUT, f"daily_{date}.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"written: {path}")
    print(f"train_h={train_h}, cum_h={cum_h}, ops={len(ops_done)}, cases={cases}")


if __name__ == "__main__":
    main()
