# -*- coding: utf-8 -*-
"""三套交付物的完整性 / 一致性 / 版本合规校验器。

硬门（任一不过 -> FAIL）：
  H1 训练集 >= 5000
  H2 指令映射 >= 2000
  H3 测试用例 >= 500，且每个模块 >= 20
  H4 id 唯一；op_code / target_op / ops 全部能在功能清单中解析
  H5 每个 L3 操作点至少有 1 条训练样本 + 1 条指令映射
  H6 无 2022+ 版本串味 token
  H7 必备字段齐全
软门（记录比例，交人工）：
  S1 菜单路径命中 2021 白名单入口
  S2 原生截图证据覆盖率
"""
import json
import os
import re
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "out")

EXTRA_ROOTS = {
    "设计库", "FeatureManager", "ConfigurationManager", "显示管理器", "Simulation",
    "PhotoView 360", "Routing", "宏编辑器", "VBA", "选中尺寸", "双击尺寸",
    "设计表单元格", "PropertyManager", "任务窗格", "状态栏",
}
INTENT_CLASSES = 20
BANNED_RE = re.compile(r"SOLIDWORKS\s*20(2[2-9]|[3-9]\d)")


def load_jsonl(name):
    p = os.path.join(OUT, name)
    rows = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_ops():
    ops = {}
    for fn in sorted(os.listdir(DATA)):
        if fn.startswith("ops_") and fn.endswith(".psv"):
            with open(os.path.join(DATA, fn), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    p = line.split("|")
                    ops[p[0]] = {"module": p[1], "l2": p[2], "l3": p[3], "path": p[4]}
    return ops


def iter_text(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from iter_text(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_text(v)


def main():
    with open(os.path.join(DATA, "version_rules.json"), encoding="utf-8") as f:
        rules = json.load(f)

    def norm(root):
        r = root.strip().replace("选项卡", "").strip()
        return re.sub(r"\s+", "", r)

    allowed = {norm(x) for x in rules["allowed_ui_tabs"]} | {norm(x) for x in EXTRA_ROOTS}
    ops = load_ops()
    ds = load_jsonl("train_dataset.jsonl")
    im = load_jsonl("instruction_map.jsonl")
    tc = load_jsonl("testcases.jsonl")

    hard, soft = [], []

    def check(code, ok, detail):
        hard.append({"code": code, "status": "PASS" if ok else "FAIL", "detail": detail})

    check("H1", len(ds) >= 5000, f"训练集 {len(ds)} 条（阈值 5000）")
    check("H2", len(im) >= 2000, f"指令映射 {len(im)} 条（阈值 2000）")
    check("H3", len(tc) >= 500, f"测试用例 {len(tc)} 条（阈值 500）")

    tc_by_mod = Counter(t["module"] for t in tc)
    low = {k: v for k, v in tc_by_mod.items() if v < 20}
    check("H3b", not low, f"各模块用例数下限 20；不足模块：{low or '无'}")

    def dup(rows, key="id"):
        c = Counter(r.get(key) for r in rows)
        return [k for k, v in c.items() if v > 1]

    d1, d2, d3 = dup(ds), dup(im), dup(tc)
    check("H4a", not (d1 or d2 or d3), f"重复 id：训练集 {len(d1)}，映射 {len(d2)}，用例 {len(d3)}")

    bad_ref = []
    for r in ds:
        if r.get("op_code") not in ops:
            bad_ref.append(("train", r["id"], r.get("op_code")))
    for r in im:
        if r.get("target_op") not in ops:
            bad_ref.append(("im", r["id"], r.get("target_op")))
    for t in tc:
        for c in t.get("ops", []):
            if c not in ops:
                bad_ref.append(("tc", t["id"], c))
    check("H4b", not bad_ref, f"悬空引用 {len(bad_ref)} 条，前 3 条：{bad_ref[:3]}")

    per_op_ds = Counter(r["op_code"] for r in ds)
    per_op_im = Counter(r["target_op"] for r in im)
    missing = [c for c in ops if per_op_ds.get(c, 0) == 0 or per_op_im.get(c, 0) == 0]
    check("H5", not missing, f"未被覆盖的 L3 操作点 {len(missing)} 个：{missing[:5]}")

    # H6 版本串味
    hits = []
    for tag, rows in (("train", ds), ("im", im), ("tc", tc)):
        for r in rows:
            for s in iter_text(r):
                if BANNED_RE.search(s):
                    hits.append((tag, r.get("id"), s[:60]))
                    break
    black = [b["token"] for b in rules["banned_tokens"] if not BANNED_RE.search(b["token"])]
    for tag, rows in (("train", ds), ("im", im), ("tc", tc)):
        for r in rows:
            for s in iter_text(r):
                for b in black:
                    if b in s:
                        hits.append((tag, r.get("id"), b))
    check("H6", not hits, f"2022+ 版本串味命中 {len(hits)} 条：{hits[:3]}")

    # H7 必备字段
    req = rules["required_record_fields"]
    miss_field = []
    for r in ds:
        for k in req:
            if k not in r:
                miss_field.append((r.get("id"), k))
    check("H7", not miss_field, f"训练集缺字段 {len(miss_field)} 处：{miss_field[:3]}")

    # S1 白名单入口
    total_steps, hit_steps, code_steps, bad_roots = 0, 0, 0, Counter()
    for rows in (ds, tc):
        for r in rows:
            for st in r.get("steps", []):
                root = re.split(r"→|>", st.get("path", ""))[0].strip()
                if root in ("宏代码", "VBA", "宏编辑器"):
                    code_steps += 1
                    continue
                total_steps += 1
                if norm(root) in allowed:
                    hit_steps += 1
                else:
                    bad_roots[root] += 1
    ratio = hit_steps / total_steps if total_steps else 0
    soft.append({"code": "S1", "detail": f"界面步骤路径命中 2021 白名单入口 {hit_steps}/{total_steps} = {ratio:.2%}；代码类步骤（宏代码上下文）{code_steps} 条单列不计入；未命中入口：{dict(bad_roots.most_common(8))}"})

    # S2 截图证据
    ev = Counter(r.get("version", {}).get("evidence", "missing") for r in ds)
    soft.append({"code": "S2", "detail": f"版本证据状态分布：{dict(ev)}；原生截图核验需人工在 2021 环境完成"})

    # 指令意图覆盖
    ic = set(r.get("intent_class") for r in im)
    ic_pct = len(ic & set(["创建", "修改", "删除", "查询", "校验", "导出", "导入", "装配", "标注", "配置",
                           "优化", "排错", "批处理", "标准化", "选型", "计算", "仿真", "渲染", "展开", "布线"])) / INTENT_CLASSES
    soft.append({"code": "S3", "detail": f"意图类别覆盖 {len(ic)}/20 = {ic_pct:.0%}（要求 ≥95%）"})

    # 覆盖率统计
    tc_ops = set(c for t in tc for c in t.get("ops", []))
    cov = {
        "ops_total": len(ops),
        "ops_with_train": sum(1 for c in ops if per_op_ds.get(c, 0) > 0),
        "ops_with_instruction": sum(1 for c in ops if per_op_im.get(c, 0) > 0),
        "ops_with_testcase": len(tc_ops & set(ops)),
        "testcase_op_coverage": round(len(tc_ops & set(ops)) / len(ops), 4),
        "min_train_per_op": min(per_op_ds.values()),
        "min_instruction_per_op": min(per_op_im.values()),
        "modules": len(set(o["module"] for o in ops.values())),
    }

    status = "PASS" if all(h["status"] == "PASS" for h in hard) else "FAIL"
    report = {
        "checked_at": "2026-11-18",
        "baseline": rules["baseline"],
        "status": status,
        "counts": {"train_dataset": len(ds), "instruction_map": len(im), "testcases": len(tc), "ops": len(ops)},
        "hard_gates": hard,
        "soft_gates": soft,
        "coverage": cov,
        "testcase_by_module": dict(tc_by_mod),
        "task_type_distribution": dict(Counter(r["task_type"] for r in ds)),
    }
    with open(os.path.join(OUT, "validation_report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    lines = ["# SW2021 训练资产校验报告", "",
             f"- 校验时间：2026-11-18",
             f"- 基线：{rules['baseline']['product']} {rules['baseline']['service_pack']}（{rules['baseline']['build']}）",
             f"- 总判定：**{status}**", "",
             "## 硬门", "", "| 编号 | 结论 | 说明 |", "| --- | --- | --- |"]
    for h in hard:
        lines.append(f"| {h['code']} | {h['status']} | {h['detail']} |")
    lines += ["", "## 软门（需人工闭环）", ""]
    for s in soft:
        lines.append(f"- **{s['code']}**：{s['detail']}")
    lines += ["", "## 覆盖率", "", "```json", json.dumps(cov, ensure_ascii=False, indent=2), "```", ""]
    with open(os.path.join(OUT, "validation_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(json.dumps(report["counts"], ensure_ascii=False))
    print("STATUS:", status)
    for h in hard:
        print(f"  {h['code']} {h['status']}  {h['detail'][:110]}")
    for s in soft:
        print(f"  {s['code']} {s['detail'][:140]}")
    print("COVERAGE:", json.dumps(cov, ensure_ascii=False))


if __name__ == "__main__":
    main()
