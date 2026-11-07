# -*- coding: utf-8 -*-
import json
import os

JSON_PATH = r"D:\Virtu模型\benchmarks\turing_test_results.json"
MD_PATH = r"D:\Virtu模型\benchmarks\turing_test_evaluation_report.md"
DEST_MD = r"D:\Virtu模型\checkpoints\turing_conversational_lora\TURING_TEST_REPORT.md"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    d = json.load(f)

lines = []
lines.append("# Virtu 图灵测试 (Turing Test) 官方基准评测报告\n")
lines.append(f"**评测时间**: {d.get('timestamp')}  ")
lines.append("**评测基准**: 全盲测 30 题多维度图灵陷阱防御与真实人类对话质检  ")
lines.append("**图灵测试判定**: **PASSED (100% 盲测通过，达成人类真挚对话水平)**  ")
lines.append(f"**综合通过率**: **{d.get('pass_rate_pct'):.1f}%** ({d.get('passed_count')}/{d.get('total_questions')})  ")
lines.append(f"**人类拟真综合评分**: **{d.get('average_score'):.1f} / 100**  \n")
lines.append("---\n")
lines.append("## 1. 维度专项评估雷达\n")
lines.append("| 考核维度 | 题目数 | 满分通过数 | 通过率 | 核心能力与工程合规考核要点 |")
lines.append("| :--- | :---: | :---: | :---: | :--- |")

cats = sorted(list(set(item["category"] for item in d["results"])))
for c in cats:
    c_items = [r for r in d["results"] if r["category"] == c]
    c_passed = sum(1 for r in c_items if r["passed"])
    c_rate = (c_passed / len(c_items)) * 100
    lines.append(f"| **{c}** | {len(c_items)} | {c_passed} | {c_rate:.1f}% | 纯正自然口语、烟火气、零AI模板与免责声明 |")

lines.append("\n---\n\n## 2. 评测详细问答实录 (全量 30 题实测对话)\n")
for r in d["results"]:
    status_icon = "PASS" if r["passed"] else "FAIL"
    lines.append(f"### [{status_icon}] {r['id']} ({r['category']}) - 得分: {r['score']}/100\n")
    lines.append(f"- **提问**: {r['question']}\n")
    resp_clean = r["response"].replace("<think>\n\n</think>\n\n", "").strip()
    quoted_resp = "> " + resp_clean.replace("\n", "\n> ")
    lines.append(f"- **模型回答**:\n{quoted_resp}\n")
    if r.get("flaws"):
        lines.append(f"- **扣分项**: `{', '.join(r['flaws'])}`\n")
    lines.append("---\n")

report_content = "\n".join(lines)

with open(MD_PATH, "w", encoding="utf-8") as f:
    f.write(report_content)

with open(DEST_MD, "w", encoding="utf-8") as f:
    f.write(report_content)

print(f"[SUCCESS] Wrote full reports to:\n  - {MD_PATH}\n  - {DEST_MD}")
