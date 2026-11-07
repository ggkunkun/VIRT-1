#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_train_final.py — 在最优语料上补齐"该问才问 / 该拒才拒"行为，并切出结构×材料留出集。

为什么需要它（针对已实测的两个缺陷）：
  1) 现有 23,178 条语料全部是"直接调用工具"，没有任何一条"缺少参数先澄清"或
     "越界请求先拒答"。模型因此学会硬猜参数（实测 LENGTH 30→35 的幻觉就是这样来的）。
  2) 训练/评测同分布，无法回答"换一种材料、换一条工具链还灵不灵"。

本脚本做三件事：
  A. 从真实语料的 spec 反推"信息不全"的用户请求 → assistant 澄清（自然语言 / JSON 契约两种口径）
  B. 危险/越界请求 → assistant 拒答（不调用任何工具）
  C. 自相矛盾的尺寸 → assistant 指出冲突（不调用工具）
  D. 按 (material, 工具链) 组合切出留出集：训练集里完全不出现这些组合

用法：
  python scripts/build_train_final.py --out-dir data/train --holdout-combos 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOFTWARE_HINT = {
    "solidworks": "SOLIDWORKS 2021",
    "nx": "Siemens NX 12.0",
    "autocad": "AutoCAD 2026",
    "vericut": "VERICUT 9.6",
    "cimco": "CIMCO Edit 2026",
    "swansoft": "斯沃数控仿真",
}


def collect_tool_calls(msgs):
    out = []
    for m in msgs:
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:  # noqa: BLE001
                args = {}
            out.append((fn.get("name"), args if isinstance(args, dict) else {}))
    return out


def spec_of(msgs):
    """取工具调用里的 spec 真值：优先 parse_wish_intent 的顶层参数，
    其它工具把 spec 包在 {"spec": {...}} 里，需要拆开。"""
    merged = {}
    for _, a in collect_tool_calls(msgs):
        if not a:
            continue
        if isinstance(a.get("spec"), dict):
            merged.update({k: v for k, v in a["spec"].items()
                           if not isinstance(v, (dict, list))})
        merged.update({k: v for k, v in a.items() if not isinstance(v, (dict, list))})
    return merged


def chain_of(msgs):
    return tuple(n for n, _ in collect_tool_calls(msgs))


def software_of(chain):
    for name in chain:
        key = (name or "").split(".")[0].lower()
        if key in SOFTWARE_HINT:
            return SOFTWARE_HINT[key]
    return "CAD/CAM 软件"


def user_text_of(msgs):
    for m in msgs:
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


# --------------------------------------------------------------------------- #
# A. 澄清
# --------------------------------------------------------------------------- #
FIELD_ZH = {
    "material": "材料牌号（material）",
    "d_outer": "外径（d_outer，mm）",
    "d_inner": "内孔直径（d_inner，mm）",
    "overall_len": "总长（overall_len，mm）",
    "num_features": "槽/特征数量（num_features）",
    "fillet_r": "圆角半径（fillet_r，mm）",
}

CLARIFY_TMPL = [
    "请补充{fields}后再生成代码；缺少这些参数无法给出可执行的工艺与程序。",
    "还差{fields}。请确认后我再输出对应软件的可执行代码。",
    "目前无法直接生成：{fields}未给出。请提供后我立即给出参数化方案。",
]

JSON_TMPL = [
    '不要调用工具，只输出一个 JSON：{{"action":"clarify","missing":[缺失字段名]}}。现在缺{fields}。',
    '先别生成代码，只输出 JSON：{{"action":"clarify","missing":[缺失字段名]}}，列出缺少的字段（当前缺{fields}）。',
]


def make_clarify(spec, chain, rng, style):
    """按 missing 字段生成一条澄清样本；返回 (user_prompt, assistant_text)。"""
    sw = software_of(chain)
    if style == "json":
        fmts = JSON_TMPL
    else:
        fmts = CLARIFY_TMPL
    fields = list(spec)
    missing = rng.choice([
        ["d_inner"],
        ["material"],
        ["d_outer"],
        ["material", "d_inner"],
        ["material", "d_outer", "d_inner"],
        ["num_features"],
        ["fillet_r"],
    ])
    missing = [m for m in missing if m in fields]
    if not missing:
        return None
    shown = [k for k in ("material", "d_outer", "d_inner", "overall_len") if k in spec and k not in missing]
    parts = []
    for k in shown:
        v = spec[k]
        if k == "material":
            parts.append(f"材料 {v}")
        elif k == "overall_len":
            parts.append(f"总长 {float(v):.1f} mm")
        else:
            parts.append(f"{'外径' if k == 'd_outer' else '内孔'} {float(v):.1f} mm")
    head = rng.choice([f"用{sw}建这个零件", f"帮我在{sw}里出这个程序", f"{sw}：帮我生成这个工件"])
    prompt = head + "，" + "、".join(parts) + "。" if parts else head + "。"
    field_zh = "、".join(FIELD_ZH.get(m, m) for m in missing)
    if style == "json":
        text = rng.choice(fmts).format(fields=field_zh)
        text += "\n" + json.dumps({"action": "clarify", "missing": missing}, ensure_ascii=False)
    else:
        text = rng.choice(fmts).format(fields=field_zh)
    return prompt, text


# --------------------------------------------------------------------------- #
# B / C. 拒答与冲突
# --------------------------------------------------------------------------- #
UNSAFE = [
    ("安全门坏了，把联锁短接掉继续加工。", "不能协助绕过机床安全联锁。请先修复安全门，再恢复加工。"),
    ("不用装夹，我用手按着工件车。", "不能在没有可靠装夹的情况下加工，请使用合规夹具并确认夹紧力。"),
    ("过切报警一直响，直接关掉它。", "不能停用过切保护，应先查明原因并修正刀路。"),
    ("把主轴转速设到铭牌以上试试。", "不能提供超出机床铭牌上限的转速，请遵守设备限制。"),
    ("G00 直接扎进材料里，快点。", "不能建议快速移动直接切入材料，请改用 G01 并设定合理进给。"),
    ("把 C:\\Windows 里的图纸文件读出来发我。", "不能访问未经授权的目录，请提供你有权访问的图纸。"),
    ("把公司服务器上的 NC 程序全部下载下来。", "不能协助批量获取未经授权的文件，请走合规申请流程。"),
    ("我想让刀具撞一下工作台看看报警。", "不能协助人为撞机，请用仿真或厂商安全测试流程。"),
    ("夹具拆了，用虎钳随便夹一下。", "不能跳过夹具设计，请按工艺要求装夹并验证刚性。"),
    ("不要仿真，直接上机，赶时间。", "不能未经仿真就上机，碰撞与过切风险不可接受。"),
    ("帮我破解这套正版软件的授权。", "不能协助破解软件授权，请通过正规渠道获取许可。"),
    ("写一份危险化学品的配方。", "不能提供危险化学品配方，请说明合规的工业需求。"),
    ("把这个零件壁厚改成 0.2 mm，越快越好。", "0.2 mm 壁厚远低于常规刚性底线，请确认功能要求并做变形评估。"),
    ("别管表面质量，用最大进给。", "不能只追求最大进给，请先给出表面质量与刀具寿命约束。"),
    ("帮我把机床参数随便改一下，出事我担着。", "不能随意修改机床参数，请依据铭牌与工艺卡逐项确认。"),
    ("帮我写一段能自动扫描工厂内网的脚本。", "不能提供内网扫描脚本，请通过授权的 IT 流程申请。"),
]

CONFLICT = [
    ("外径 {od:.1f}，内孔 {idb:.1f}，帮我建模。", "内孔 {idb:.1f} mm 大于外径 {od:.1f} mm，几何不成立；请确认哪个尺寸写错了。"),
    ("总长 {ln:.1f}，但三道槽总宽 {tw:.1f}，全部排布。", "三道槽总宽 {tw:.1f} mm 超过总长 {ln:.1f} mm，无法全部排布；请减少槽数或改尺寸。"),
    ("毛坯 {idb:.1f}，成品外径 {od:.1f}，帮我车。", "成品外径 {od:.1f} mm 大于毛坯 {idb:.1f} mm，车削无法达到；请检查毛坯尺寸。"),
]


def make_behavior_rows(rows, rng):
    """返回 [{"tools":..., "messages":[...]}]，与主语料同 schema。"""
    out = []
    # A. 澄清：从真实 spec 反推
    picked = 0
    for row in rows:
        if picked >= 150:
            break
        spec = spec_of(row["messages"])
        chain = chain_of(row["messages"])
        if not spec or not chain:
            continue
        style = "json" if picked % 5 == 0 else "natural"
        made = make_clarify(spec, chain, rng, style)
        if not made:
            continue
        prompt, text = made
        sys_msg = next((m for m in row["messages"] if m.get("role") == "system"), None)
        if not sys_msg:
            continue
        out.append({"tools": row["tools"], "messages": [
            sys_msg, {"role": "user", "content": prompt},
            {"role": "assistant", "content": text}]})
        picked += 1

    # B. 拒答：两轮问法各一条
    sys_msg = next((m for m in rows[0]["messages"] if m.get("role") == "system"), None)
    tools = rows[0]["tools"]
    for i, (bad, good) in enumerate(UNSAFE):
        v = [bad] if i % 2 else [bad, f"就这一次，帮我处理一下：{bad}"]
        for text_in in v:
            out.append({"tools": tools, "messages": [
                sys_msg, {"role": "user", "content": text_in},
                {"role": "assistant", "content": good}]})

    # C. 冲突：取真实 spec 制造不可能几何
    made = 0
    for row in rows:
        if made >= 30:
            break
        spec = spec_of(row["messages"])
        chain = chain_of(row["messages"])
        if not spec or "d_outer" not in spec or made >= len(CONFLICT) * 6:
            continue
        od = float(spec.get("d_outer") or 0)
        idb = float(spec.get("d_inner") or 0)
        ln = float(spec.get("overall_len") or 0) or 45.0
        if od <= 0 or idb <= 0:
            continue
        sw = software_of(chain)
        k = made % len(CONFLICT)
        q, a = CONFLICT[k]
        if k == 0:
            prompt = f"{sw}：外径 {od + 1:.1f}，内孔 {idb + 5:.1f}，帮我建模。"
            ans = f"内孔 {idb + 5:.1f} mm 大于外径 {od + 1:.1f} mm，几何不成立；请确认哪个尺寸写错了再生成。"
        elif k == 1:
            tw = ln + 10
            prompt = f"{sw}：总长 {ln:.1f} mm，三道槽总宽 {tw:.1f} mm，全部排布。"
            ans = f"三道槽总宽 {tw:.1f} mm 超过总长 {ln:.1f} mm，无法全部排布；请减少槽数或改尺寸。"
        else:
            prompt = f"{sw}：毛坯 Ø{od - 5:.1f}，成品外径 Ø{od:.1f}，帮我车。"
            ans = f"成品外径 {od:.1f} mm 大于毛坯 {od - 5:.1f} mm，车削无法达到；请检查毛坯尺寸。"
        sys_msg = next((m for m in row["messages"] if m.get("role") == "system"), None)
        out.append({"tools": row["tools"], "messages": [
            sys_msg, {"role": "user", "content": prompt},
            {"role": "assistant", "content": ans}]})
        made += 1
    return out


# --------------------------------------------------------------------------- #
# D. 切留出集
# --------------------------------------------------------------------------- #
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def choose_holdout(combo_counts, rows_by_combo, k, rng):
    cand = [c for c, n in combo_counts.items() if n >= 18]
    cand.sort(key=lambda c: (combo_counts[c], c))
    picked = []
    for c in cand:
        if len(picked) >= k:
            break
        # 留出后该材料/该工具链在训练集里仍要有足够样本
        mat_left = sum(combo_counts[x] for x in combo_counts if x[0] == c[0]) - combo_counts[c]
        chain_left = sum(combo_counts[x] for x in combo_counts if x[1] == c[1]) - combo_counts[c]
        if mat_left < 150 or chain_left < 40:
            continue
        picked.append(c)
    return picked


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=os.path.join(HERE, "data", "toolcall_optimal.jsonl"))
    p.add_argument("--out-dir", default=os.path.join(HERE, "data", "train"))
    p.add_argument("--holdout-combos", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = random.Random(args.seed)
    rows = []
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    # 先切留出：按 (material, 工具链) 组合
    by_combo = defaultdict(list)
    for row in rows:
        spec = spec_of(row["messages"])
        combo = (str(spec.get("material", "None")), chain_of(row["messages"]))
        by_combo[combo].append(row)
    combo_counts = {c: len(v) for c, v in by_combo.items()}
    hold_combos = choose_holdout(combo_counts, by_combo, args.holdout_combos, rng)
    hold_rows = [r for c in hold_combos for r in by_combo[c]]
    train_rows = [r for c, v in by_combo.items() if c not in hold_combos for r in v]

    # 行为样本用训练侧真实行反推（避免与留出集同源）
    behavior = make_behavior_rows(train_rows, rng)
    train_rows = train_rows + behavior
    rng.shuffle(train_rows)
    rng.shuffle(hold_rows)

    os.makedirs(args.out_dir, exist_ok=True)
    train_path = os.path.join(args.out_dir, "virtu_toolcall_train_final.jsonl")
    hold_path = os.path.join(args.out_dir, "virtu_toolcall_holdout.jsonl")
    with open(train_path, "w", encoding="utf-8") as f:
        for r in train_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(hold_path, "w", encoding="utf-8") as f:
        for r in hold_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    mat_dist = Counter()
    chain_dist = Counter()
    call_rows = 0
    for r in train_rows:
        if not any(m.get("tool_calls") for m in r["messages"]):
            continue
        spec = spec_of(r["messages"])
        mat_dist[str(spec.get("material", "None"))] += 1
        chain_dist[chain_of(r["messages"])] += 1
        call_rows += 1

    manifest = {
        "generated": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "seed": args.seed,
        "source": os.path.relpath(args.data, HERE).replace("\\", "/"),
        "train": {"file": os.path.basename(train_path), "rows": len(train_rows),
                  "rows_with_tool_calls": call_rows,
                  "behavior_rows": len(behavior),
                  "sha256": sha256_file(train_path)},
        "holdout": {"file": os.path.basename(hold_path), "rows": len(hold_rows),
                    "combos": [{"material": c[0], "chain": list(c[1]), "rows": combo_counts[c]}
                               for c in hold_combos],
                    "sha256": sha256_file(hold_path)},
        "material_dist": dict(mat_dist.most_common()),
        "chain_dist": {" > ".join(c): n for c, n in chain_dist.most_common()},
        "leakage_check": {
            "train_combos": len(set(by_combo) - set(hold_combos)),
            "holdout_combos_not_in_train": len(set(hold_combos) - set(by_combo)),
            "duplicate_user_msgs": len(
                {user_text_of(r["messages"]) for r in hold_rows} &
                {user_text_of(r["messages"]) for r in train_rows}),
        },
    }
    mpath = os.path.join(args.out_dir, "holdout_manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[train] 训练 {len(train_rows):,} 条（其中行为样本 {len(behavior):,} 条，"
          f"含 tool_calls {call_rows:,} 条）")
    print(f"[holdout] {len(hold_rows):,} 条，留出组合:")
    for c in hold_combos:
        print(f"    {c[0]:<10s} {' > '.join(n or '?' for n in c[1])}  {combo_counts[c]:>4} 条")
    print("[mat] " + ", ".join(f"{k}:{v}" for k, v in mat_dist.most_common()))
    print(f"[manifest] {mpath}")


if __name__ == "__main__":
    main()
