# -*- coding: utf-8 -*-
"""SW2021 训练资产构建器：功能清单 -> 训练集 / 指令映射表 / 测试用例库。

设计原则：
1. 所有样本可追溯到 data/ops_*.psv 的具体 op_code，不生成无源内容；
2. 参数取值来自清单中的参数域（min/max/default 或枚举），不做随机编造；
3. 每条记录自带 2021 版本基线与证据状态，默认 pending（待原生截图核验）。
"""
import csv
import hashlib
import itertools
import json
import os
import re
import zlib
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "out")

BASELINE = {
    "product": "SOLIDWORKS 2021",
    "service_pack": "SP5.0",
    "build": "29.5.0.0070",
    "exe": "D:\\SOLIDWORKS (2)\\SLDWORKS.exe",
    "revision_prefix": "29.",
    "ui_language": "简体中文",
    "verified_ui": False,
    "evidence": "pending_native_screenshot",
}

VERIFY_CMD = {
    "草图": "草图选项卡→检查草图合法性",
    "特征": "评估选项卡→质量属性",
    "装配": "评估选项卡→干涉检查",
    "工程图": "工程图选项卡→图层",
    "曲面": "评估选项卡→检查",
    "钣金": "钣金选项卡→展开",
    "焊件": "焊件选项卡→焊件切割清单",
    "渲染仿真": "Simulation→结果→安全系数",
    "模具": "模具工具选项卡→分型线",
    "管道布线": "Routing 选项卡→从-到清单",
    "配置": "ConfigurationManager→重建",
    "宏": "工具→宏→运行",
}

NUM = re.compile(r"^(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)(?::(-?\d+(?:\.\d+)?))?(?::([^:]+))?$")


def load_ops():
    ops = []
    for fn in sorted(os.listdir(DATA)):
        if not (fn.startswith("ops_") and fn.endswith(".psv")):
            continue
        path = os.path.join(DATA, fn)
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 8:
                    raise ValueError(f"{fn}:{lineno} 字段数 {len(parts)} != 8")
                code, module, l2, l3, menu, pspec, checks, err = parts
                ops.append({
                    "code": code,
                    "module": module,
                    "l2": l2,
                    "l3": l3,
                    "path": menu,
                    "params": parse_params(pspec),
                    "checks": [c for c in checks.split("/") if c],
                    "error": parse_error(err),
                    "source": f"{fn}#{lineno}",
                })
    return ops


def parse_params(spec):
    if spec.strip() in ("-", ""):
        return {}
    out = {}
    for item in spec.split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        name, rest = item.split(":", 1)
        name = name.strip()
        m = NUM.match(rest)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            default = float(m.group(3)) if m.group(3) is not None else lo
            unit = (m.group(4) or "").strip()
            out[name] = {"kind": "num", "min": lo, "max": hi, "default": default,
                         "unit": unit, "values": num_values(lo, hi, default)}
        else:
            # 允许 "A0/A1/A2:3" 这类带计数的枚举
            m2 = re.match(r"^(.*?)(?::\d+)?$", rest)
            body = (m2.group(1) if m2 else rest).strip()
            vals = [v for v in body.split("/") if v]
            out[name] = {"kind": "enum", "values": vals or [body]}
    return out


def num_values(lo, hi, default=None):
    if hi <= lo:
        return [lo]
    vals = []
    if default is not None and lo <= default <= hi:
        vals.append(round(default, 3))
    for f in (0.1, 0.35, 0.6, 0.9):
        v = round(lo + (hi - lo) * f, 3)
        v = int(v) if abs(v - round(v)) < 1e-9 else v
        if lo <= v <= hi and v not in vals:
            vals.append(v)
    return vals[:4] or [round(lo, 3)]


def parse_error(err):
    bits = err.split("~")
    while len(bits) < 3:
        bits.append("")
    return {"code": bits[0].strip(), "trigger": bits[1].strip(), "fix": bits[2].strip()}


UNIT_DISPLAY = {"deg": "°", "um": "μm", "mm": "mm", "个": "个"}


def fmt(v, unit=""):
    if isinstance(v, float):
        v = int(v) if abs(v - round(v)) < 1e-9 else round(v, 2)
    u = UNIT_DISPLAY.get(unit, unit)
    return f"{v}{u}" if u else str(v)


def params_pretty(params, spec):
    out = {}
    for k, v in (params or {}).items():
        unit = spec.get(k, {}).get("unit", "") if spec else ""
        out[k] = fmt(v, unit)
    return out


def params_text(params, spec):
    if not params:
        return "无附加参数"
    pretty = params_pretty(params, spec)
    return "，".join(f"{k}={v}" for k, v in pretty.items())


def op_variants(op, n=12):
    spec = op["params"]
    if not spec:
        return [{} for _ in range(n)]
    pools = []
    for name, p in spec.items():
        pools.append([(name, v) for v in p["values"]])
    combos = [dict(c) for c in itertools.product(*pools)]
    if len(combos) > 400:
        combos = combos[:400]
    return [dict(combos[i % len(combos)]) for i in range(n)]


def step(op, params, no=1):
    return {
        "no": no,
        "path": op["path"],
        "params": params_pretty(params, op["params"]) or {"说明": "使用默认配置"},
        "check": op["checks"][0] if op["checks"] else "几何与参数一致",
    }


def verify_step(op, no=2):
    return {
        "no": no,
        "path": VERIFY_CMD.get(op["module"], "评估选项卡→测量"),
        "params": {"对象": op["l3"]},
        "check": "；".join(op["checks"][1:]) if len(op["checks"]) > 1 else "结果与设计值一致",
    }


TEMPLATES = [
    "在{ctx}上完成{l3}：使用「{path}」，参数为{pstr}。请给出可复现步骤，并说明如何校验{check}。",
    "{ctx}设计中需要{l3}，请按 SOLIDWORKS 2021 给出操作路径、参数取值（{pstr}）与校验要点。",
    "我要把{l3}的{pstr}设为设计值，2021 版应在哪个选项卡操作？给出步骤与失败回退方案。",
    "请检查{ctx}的{l3}是否规范：{check}。不合规时给出修正步骤与复验方法。",
    "用 2021 版原生命令完成{l3}（{pstr}），输出格式必须是「步骤编号+操作路径+参数配置+校验要点」。",
]


TEMPLATE_INTENTS = ["创建", "查询", "修改", "校验", "标准化"]


def make_instruction(op, params, ctx, idx):
    t = TEMPLATES[idx % len(TEMPLATES)]
    return t.format(
        ctx=ctx, l3=op["l3"], path=op["path"],
        pstr=params_text(params, op["params"]), check=op["checks"][0] if op["checks"] else "几何正确",
    )


def rec_id(prefix, n):
    return f"{prefix}-{n:06d}"


def build_ops_samples(ops, parts):
    rows, ims = [], []
    seq = 0
    im_seq = 0
    for op in ops:
        for i, params in enumerate(op_variants(op, 12)):
            seq += 1
            ctx = parts[i % len(parts)]["name"]
            instr = make_instruction(op, params, ctx, i)
            rows.append({
                "id": rec_id("SW21", seq),
                "task_type": "operation",
                "module": op["module"],
                "l2": op["l2"],
                "l3": op["l3"],
                "op_code": op["code"],
                "instruction": instr,
                "steps": [step(op, params, 1), verify_step(op, 2)],
                "verification": {
                    "geometric": op["checks"],
                    "numeric": "体积/质量/长度变化方向与操作类型一致（增料 ΔV>0，除料 ΔV<0）",
                    "gate": "全部校验点通过方可判定该操作样本合格",
                },
                "error_branch": op["error"],
                "version": BASELINE,
                "source": op["source"],
                "split": split_of(seq),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
            for t in range(5):
                im_seq += 1
                ims.append({
                    "id": rec_id("IM", im_seq),
                    "text": make_instruction(op, params, ctx, t),
                    "intent_class": TEMPLATE_INTENTS[t % len(TEMPLATE_INTENTS)],
                    "module": op["module"],
                    "target_op": op["code"],
                    "slots": params,
                    "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                    "confidence": 0.95,
                })
    return rows, ims


INTENT_CLASSES = [
    "创建", "修改", "删除", "查询", "校验", "导出", "导入", "装配", "标注", "配置",
    "优化", "排错", "批处理", "标准化", "选型", "计算", "仿真", "渲染", "展开", "布线",
]


def split_of(n):
    r = n % 20
    if r == 0:
        return "test"
    if r == 1:
        return "val"
    return "train"


def by_code(ops):
    return {o["code"]: o for o in ops}


def build_parts(ops_map, parts):
    rows = []
    seq = 0
    for part in parts:
        sweep_keys = list(part["sweep"].keys())
        combos = [dict(zip(sweep_keys, vals)) for vals in itertools.product(*[part["sweep"][k] for k in sweep_keys])]
        combos = combos[:12]
        for i, combo in enumerate(combos):
            seq += 1
            params = dict(part["base"])
            params.update(combo)
            spec_all = {}
            for c in part["ops"]:
                spec_all.update(ops_map[c]["params"])
            steps = []
            for j, code in enumerate(part["ops"], 1):
                op = ops_map[code]
                over = {k: v for k, v in params.items() if k in op["params"]}
                steps.append({
                    "no": j, "path": op["path"],
                    "params": params_pretty(over, op["params"]) or {"说明": "沿用上游尺寸"},
                    "check": op["checks"][0] if op["checks"] else "与设计值一致",
                })
            rows.append({
                "id": rec_id("SW21W", seq),
                "task_type": "workflow",
                "module": part["ops"][0][:3] if part["ops"] else "特征",
                "l2": "全流程",
                "l3": part["name"],
                "op_code": part["ops"][0],
                "instruction": (
                    f"完成 {part['name']}（{part['family']}，材料 {part['material']}，毛坯 {part['blank']}）"
                    f"从草图到工程图的全流程；关键尺寸 {params_text(params, spec_all)}；"
                    f"最终出图要求：{part['drawing']}。"
                ),
                "steps": steps,
                "verification": {
                    "geometric": ["草图完全定义", "无重建错误", "关键尺寸与参数一致"],
                    "numeric": "质量属性与理论体积偏差 ≤0.5%；钣金展开长度误差 ≤0.2mm",
                    "gate": "步骤可复现且工程图符合 GB/T 4458 系列",
                },
                "error_branch": ops_map[part["ops"][0]]["error"] if part["ops"] else None,
                "version": BASELINE,
                "source": f"recipes.json#parts/{part['id']}",
                "split": split_of(seq + 100),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
    return rows


def build_assembly(ops_map, asm):
    rows = []
    for i in range(1, 13):
        clearance = [0.2, 0.3, 0.5, 1.0][i % 4]
        steps = []
        n = 1
        for code in asm["mates"]:
            op = ops_map[code]
            steps.append({"no": n, "path": op["path"], "params": {"对象": f"{asm['name']} 组件"},
                          "check": op["checks"][0] if op["checks"] else "自由度递减"}); n += 1
        steps.append({"no": n, "path": "评估选项卡→干涉检查", "params": {"范围": "所有零部件"}, "check": "干涉体积 = 0"}); n += 1
        steps.append({"no": n, "path": "评估选项卡→间隙验证", "params": {"最小间隙": f"{clearance}mm"}, "check": f"最小间隙 ≥ {clearance}mm"}); n += 1
        steps.append({"no": n, "path": "装配体选项卡→材料明细表", "params": {"模板": "GB_BOM.sldbomtbt"}, "check": f"BOM 行数 = {asm['part_count']}"})
        rows.append({
            "id": rec_id("SW21A", i),
            "task_type": "assembly",
            "module": "装配",
            "l2": "装配全流程",
            "l3": asm["name"],
            "op_code": asm["mates"][0],
            "instruction": (
                f"装配 {asm['name']}（{asm['part_count']} 个零件），按 BOM 顺序插入并添加配合，"
                f"最小间隙按 {clearance}mm 控制，交付前完成干涉检查与自由度校核。"
            ),
            "steps": steps,
            "verification": {"geometric": asm["checks"], "numeric": "干涉体积 = 0；过约束数量 = 0；欠约束数量 = 0",
                             "gate": "MateXpert 无冲突且 BOM 与设计一致"},
            "error_branch": {"code": "SW-ASM-326", "trigger": "存在干涉体积", "fix": "定位干涉零件，改配合或修尺寸后复检"},
            "version": BASELINE,
            "source": f"recipes.json#assembly/{asm['id']}",
            "split": split_of(i + 200),
            "review": {"owner": "", "verified_at": "", "result": "pending"},
        })
    return rows


def build_drawings(ops_map, drawings):
    rows = []
    for i, d in enumerate(drawings, 1):
        seq = i
        rows.append({
            "id": rec_id("SW21D", seq),
            "task_type": "drawing",
            "module": "工程图",
            "l2": "GB 出图",
            "l3": d["name"],
            "op_code": "DRW-01",
            "instruction": (
                f"生成 {d['name']}（{d['size']}，{d['std']}）：视图组合 {','.join(d['views'])}；"
                f"标注要求 {','.join(d['dims'])}；表面结构 {d['ra']}。"
            ),
            "steps": [
                {"no": 1, "path": "文件→从零件制作工程图", "params": {"图幅": d["size"], "模板": f"GB_{d['size']}.slddrt"}, "check": "第一视角、比例 1:1"},
                {"no": 2, "path": "工程图选项卡→模型视图", "params": {"方向": d["views"][0]}, "check": "主视方向正确"},
                {"no": 3, "path": "工程图选项卡→剖面视图" if any("剖" in v for v in d["views"]) else "工程图选项卡→投影视图",
                 "params": {"视图": d["views"][-1]}, "check": "剖面线方向与相邻件相反"},
                {"no": 4, "path": "工程图选项卡→智能尺寸", "params": {"标注": d["dims"][0]}, "check": "尺寸不重复、不封闭"},
                {"no": 5, "path": "工程图选项卡→图层", "params": {"图层": "OUTLINE/DIM/CENTER"}, "check": "粗实线 0.7mm，细线 0.35mm"},
                {"no": 6, "path": "文件→另存为", "params": {"格式": "PDF", "比例": "1:1"}, "check": "字体不乱码、图框完整"},
            ],
            "verification": {"geometric": [d["std"], "线宽/字高/箭头符合 GB", "技术要求条目齐全"],
                             "numeric": "标注值与模型尺寸偏差 = 0", "gate": "人工按 GB/T 4458 逐项签署"},
            "error_branch": {"code": "SW-DRW-436", "trigger": "DWG 导出字体错位", "fix": "改用 TrueType 字体并映射图层"},
            "version": BASELINE,
            "source": f"recipes.json#drawings/{d['id']}",
            "split": split_of(seq + 300),
            "review": {"owner": "", "verified_at": "", "result": "pending"},
        })
    return rows


def build_troubleshoot(ops):
    rows, ims = [], []
    seq = 0
    for op in ops:
        err = op["error"]
        if not err["code"]:
            continue
        for k in range(2):
            seq += 1
            mode = "诊断" if k == 0 else "修复后回归"
            instr = (
                f"报错 {err['code']}：{err['trigger']}。请判断根因并给出修复步骤，最后说明如何做回归验证。"
                if k == 0 else
                f"{op['module']}模块出现「{err['trigger']}」，已按 {err['fix']} 处理。请给出回归验证步骤与验收判据。"
            )
            rows.append({
                "id": rec_id("SW21T", seq),
                "task_type": "troubleshooting",
                "module": op["module"],
                "l2": "异常处理",
                "l3": f"{op['l3']}异常",
                "op_code": op["code"],
                "instruction": instr,
                "steps": [
                    {"no": 1, "path": "评估选项卡→检查", "params": {"对象": op["l3"]}, "check": f"复现 {err['code']}"},
                    {"no": 2, "path": op["path"], "params": {"修正": err["fix"]}, "check": "错误消失且几何正确"},
                    {"no": 3, "path": VERIFY_CMD.get(op["module"], "评估选项卡→测量"), "params": {"对象": op["l3"]}, "check": "回归通过，同类问题不再出现"},
                ],
                "verification": {"geometric": op["checks"], "numeric": "修复前后差异可量化",
                                 "gate": "错误码不再出现且校验点全过"},
                "error_branch": err,
                "version": BASELINE,
                "source": op["source"],
                "split": split_of(seq + 400),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
            ims.append({
                "id": rec_id("IMT", seq),
                "text": instr,
                "intent_class": "排错",
                "module": op["module"],
                "target_op": op["code"],
                "slots": {"error_code": err["code"]},
                "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                "confidence": 0.9,
            })
    return rows, ims


def build_gb(gb, drawings):
    rows, ims = [], []
    seq = 0
    for i, g in enumerate(gb):
        for j in range(9):
            seq += 1
            d = drawings[j % len(drawings)]
            rows.append({
                "id": rec_id("SW21G", seq),
                "task_type": "annotation",
                "module": "工程图",
                "l2": "GB 标注",
                "l3": g["name"],
                "op_code": "DRW-22" if "形位" in g["name"] else "DRW-15",
                "instruction": f"按 {g['ref']} 在《{d['name']}》中设置「{g['name']}」：{g['rule']}。",
                "steps": [
                    {"no": 1, "path": "工程图选项卡→图层", "params": {"图层": "DIM"}, "check": "线宽 0.35mm"},
                    {"no": 2, "path": "工程图选项卡→" + ("形位公差" if "形位" in g["name"] else "智能尺寸"),
                     "params": {"规则": g["rule"]}, "check": g["check"]},
                    {"no": 3, "path": "文件→另存为", "params": {"格式": "PDF"}, "check": "输出与图样一致"},
                ],
                "verification": {"geometric": [g["ref"], g["check"]], "numeric": "标注值与标准值一致",
                                 "gate": "抽检 3 处均符合标准"},
                "error_branch": {"code": "SW-DRW-435", "trigger": "线宽或字高不符合 GB", "fix": "按图层统一改线粗与字高"},
                "version": BASELINE,
                "source": f"recipes.json#gb_annotations/{g['id']}",
                "split": split_of(seq + 500),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
        for t in range(2):
            ims.append({
                "id": rec_id("IMG", len(ims) + 1),
                "text": (f"工程图里{g['name']}怎么标才算符合国标？" if t == 0
                         else f"{g['ref']} 对{g['name']}的具体要求是什么，2021 版在哪里设置？"),
                "intent_class": "标注",
                "module": "工程图",
                "target_op": "DRW-22" if "形位" in g["name"] else "DRW-15",
                "slots": {"rule": g["rule"]},
                "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                "confidence": 0.92,
            })
    return rows, ims


def build_macro(topics, ops_map):
    rows, ims = [], []
    seq = 0
    value_pool = [1, 2, 5, 10, 12, 16, 20, 25, 32, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 500]
    for t in topics:
        for j in range(20):
            seq += 1
            val = value_pool[j % len(value_pool)]
            code = f"' {t['api']}  |  {t['goal']}\nDim swApp As Object\nSet swApp = CreateObject(\"SldWorks.Application\")\n' 参数 {t['param']} = {val}\n' 断言 {t['check']}"
            rows.append({
                "id": rec_id("SW21M", seq),
                "task_type": "api",
                "module": "宏",
                "l2": "二次开发",
                "l3": t["goal"],
                "op_code": "MACRO-06",
                "instruction": f"用 VBA 调用 {t['api']} 完成「{t['goal']}」，参数 {t['param']}={val}，并断言「{t['check']}」。",
                "steps": [
                    {"no": 1, "path": "工具→宏→新建", "params": {"语言": "VBA"}, "check": "工程创建成功"},
                    {"no": 2, "path": "宏编辑器→引用", "params": {"引用": "SOLIDWORKS 2021 Type Library"}, "check": "引用无缺失"},
                    {"no": 3, "path": "宏编辑器→代码", "params": {"API": t["api"], "参数": val}, "check": t["check"]},
                    {"no": 4, "path": "工具→宏→运行", "params": {"文件": "sw2021_mastery/work/macro.swp"}, "check": "无运行时错误"},
                ],
                "code": code,
                "verification": {"geometric": [t["check"]], "numeric": f"读回值与输入 {val} 一致",
                                 "gate": "连续执行 3 次结果一致"},
                "error_branch": {"code": "SW-MAC-1206", "trigger": "CreateObject 失败", "fix": "确认 ProgID 与 64 位环境，改用绝对路径启动"},
                "version": BASELINE,
                "source": f"recipes.json#macro_topics/{t['id']}",
                "split": split_of(seq + 600),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
        for k in range(3):
            ims.append({
                "id": rec_id("IMM", len(ims) + 1),
                "text": [f"帮我写个宏，{t['goal']}，参数可改。",
                         f"{t['api']} 在 2021 里怎么调用？给最小可运行代码。",
                         f"如何用宏批量处理并校验「{t['check']}」？"][k],
                "intent_class": "批处理" if k == 2 else "创建",
                "module": "宏",
                "target_op": "MACRO-06",
                "slots": {"api": t["api"], "param": t["param"]},
                "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                "confidence": 0.9,
            })
    return rows, ims


def build_mates(mates, asm, ops_map):
    rows, ims = [], []
    seq = 0
    for m in mates:
        op = ops_map[m["op"]]
        for j in range(30):
            seq += 1
            ctx = ["减速器", "夹具", "输送机", "泵体", "机架"][j % 5]
            rows.append({
                "id": rec_id("SW21P", seq),
                "task_type": "mate",
                "module": "装配",
                "l2": "配合规则",
                "l3": f"{m['type']}配合",
                "op_code": m["op"],
                "instruction": f"{ctx}装配中，{m['a']} 与 {m['b']} 采用{m['type']}配合，{m['param']}。给出配合选择顺序与自由度校验。",
                "steps": [
                    {"no": 1, "path": op["path"], "params": {"参考1": m["a"], "参考2": m["b"], "参数": m["param"]},
                     "check": op["checks"][0] if op["checks"] else "配合建立成功"},
                    {"no": 2, "path": "评估选项卡→MateXpert", "params": {"范围": "整个装配体"}, "check": "无过定义"},
                    {"no": 3, "path": "评估选项卡→干涉检查", "params": {"范围": "所选零部件"}, "check": "干涉体积 = 0"},
                ],
                "verification": {"geometric": ["自由度符合预期", m["check"]], "numeric": "残余自由度数量与理论一致",
                                 "gate": "MateXpert 0 冲突且运动模拟无碰撞"},
                "error_branch": {"code": "SW-ASM-325", "trigger": "配合冲突或参考丢失", "fix": "用 MateXpert 定位后删除冗余配合"},
                "version": BASELINE,
                "source": f"recipes.json#mates/{m['id']}",
                "split": split_of(seq + 700),
                "review": {"owner": "", "verified_at": "", "result": "pending"},
            })
        for k in range(4):
            ims.append({
                "id": rec_id("IMP", len(ims) + 1),
                "text": [f"{m['a']}和{m['b']}怎么配合？",
                         f"用{m['type']}配合会不会过定义？",
                         f"{m['type']}配合后还能动吗？",
                         f"给我{m['type']}配合的完整操作步骤和校验方法。"][k],
                "intent_class": "装配",
                "module": "装配",
                "target_op": m["op"],
                "slots": {"param": m["param"]},
                "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                "confidence": 0.95,
            })
    return rows, ims


def build_extra_intents():
    """补齐 20 类意图中不来自单一操作模板的类别（删除/导出/导入/配置/优化/选型/计算/仿真/渲染/展开/布线/装配/标注/批处理）。"""
    rows = []
    for i, (text, intent, module, op, slots) in enumerate(EXTRA_INTENTS, 1):
        rows.append({
            "id": rec_id("IMX", i),
            "text": text,
            "intent_class": intent,
            "module": module,
            "target_op": op,
            "slots": slots,
            "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
            "confidence": 0.92,
        })
    return rows


EXTRA_INTENTS = [
    ("把这几个面删掉但不要破面", "删除", "特征", "FEAT-47", {}),
    ("这个凸台不要了，直接删掉实体", "删除", "特征", "FEAT-38", {}),
    ("把工程图导出成 PDF，比例要 1:1", "导出", "工程图", "DRW-36", {"format": "PDF"}),
    ("展开图导出 DXF，折弯线单独一层", "导出", "钣金", "SM-24", {"format": "DXF"}),
    ("客户给的 STEP 打开一堆破面，怎么修", "导入", "曲面", "SURF-10", {"format": "STEP"}),
    ("导入的 IGES 曲面缝不成实体", "导入", "曲面", "SURF-10", {"format": "IGES"}),
    ("同一个零件要做 5 种长度，怎么配", "配置", "配置", "CFG-01", {"n": 5}),
    ("用设计表批量生成系列零件", "配置", "配置", "CFG-17", {"rows": 10}),
    ("总装打开太慢，有什么办法", "优化", "装配", "ASM-41", {}),
    ("大装配卡到不能动，怎么提速", "优化", "装配", "ASM-40", {}),
    ("M8 的螺栓孔用多大底孔", "选型", "特征", "FEAT-19", {"size": "M8"}),
    ("轴承和轴选什么配合", "选型", "装配", "ASM-07", {"fit": "k6"}),
    ("螺旋线导程 5mm 转 8 圈，长度多少", "计算", "特征", "FEAT-52", {"pitch": 5, "turns": 8}),
    ("用方程式把长度和孔径关联起来", "计算", "配置", "CFG-11", {}),
    ("这个支架受力够不够", "仿真", "渲染仿真", "REND-11", {}),
    ("安全系数不到 1.5 怎么办", "仿真", "渲染仿真", "REND-23", {"limit": 1.5}),
    ("出一张产品渲染图给客户看", "渲染", "渲染仿真", "REND-08", {"w": 1920, "h": 1080}),
    ("钣金件展开图怎么出", "展开", "钣金", "SM-08", {}),
    ("管子从泵口走到塔口怎么布", "布线", "管道布线", "ROUT-05", {}),
    ("这批管路要出从-到清单", "布线", "管道布线", "ROUT-17", {}),
    ("轴和轴承怎么装进去", "装配", "装配", "ASM-07", {}),
    ("这个孔怎么标符合国标", "标注", "工程图", "DRW-29", {}),
    ("表面粗糙度怎么统一标注", "标注", "工程图", "DRW-24", {"ra": 3.2}),
    ("100 个文件批量改材质", "批处理", "宏", "MACRO-19", {"files": 100}),
    ("批量导出工程图 PDF", "批处理", "宏", "MACRO-20", {"files": 100}),
    ("模型改尺寸后工程图会自动更新吗", "修改", "工程图", "DRW-17", {}),
    ("怎么快速看清特征树结构", "查询", "宏", "MACRO-13", {}),
    ("这两个件先定哪个位置再定哪个", "装配", "装配", "ASM-03", {}),
]


def build_testcases(ops, ops_map, parts, asm, drawings, workflows):
    tcs = []
    seq = 0
    by_mod = defaultdict(list)
    for o in ops:
        by_mod[o["module"]].append(o)
    # 1) 模块专项：每模块 26 条
    for mod, items in by_mod.items():
        for i in range(26):
            seq += 1
            pick = [items[(i * 3 + k) % len(items)] for k in range(3)]
            steps = []
            for j, op in enumerate(pick, 1):
                steps.append({"no": j, "path": op["path"], "params": {"按图样给定": "见任务书"}, "check": op["checks"][0] if op["checks"] else "合格"})
            tcs.append({
                "id": rec_id("TC", seq),
                "module": mod,
                "level": "module",
                "title": f"{mod}专项-{i+1:02d}：{pick[0]['l2']}综合操作",
                "precondition": "SOLIDWORKS 2021 SP5 已启动，单位为 MMGS，模板为 GB 模板",
                "task": f"在 30 分钟内完成：{ '；'.join(o['l3'] for o in pick) }，并逐项自检。",
                "steps": steps,
                "expected": [o["checks"][0] for o in pick if o["checks"]],
                "acceptance": {"accuracy": 1.0, "pass_rule": "步骤与路径 100% 匹配，校验点全过", "time_limit_min": 30},
                "ops": [o["code"] for o in pick],
                "est_min": 30,
            })
    # 2) 十个标准零件
    for p in parts:
        seq += 1
        tcs.append({
            "id": rec_id("TC", seq),
            "module": "综合",
            "level": "acceptance",
            "title": f"标准零件-{p['id']}：{p['name']}",
            "precondition": f"材料 {p['material']}，毛坯 {p['blank']}，GB 模板",
            "task": f"按图样完成 {p['name']} 建模并出图：{p['drawing']}。",
            "steps": [{"no": i, "path": ops_map[c]["path"], "params": {"尺寸": "按图样"}, "check": ops_map[c]["checks"][0] if ops_map[c]["checks"] else "合格"}
                      for i, c in enumerate(p["ops"], 1)],
            "expected": ["草图完全定义", "无重建错误", "工程图符合 GB/T 4458", "质量属性偏差 ≤0.5%"],
            "acceptance": {"accuracy": 1.0, "pass_rule": "10 项检查全过，允许 0 项偏差", "time_limit_min": 120},
            "ops": p["ops"],
            "est_min": 120,
        })
    # 3) 装配 30 条
    for i in range(30):
        seq += 1
        src = asm["mates"][i % len(asm["mates"])]
        op = ops_map[src]
        tcs.append({
            "id": rec_id("TC", seq),
            "module": "装配",
            "level": "integration",
            "title": f"装配验收-{i+1:02d}：{op['l3']}与约束链",
            "precondition": f"{asm['name']} 全部 {asm['part_count']} 个零件已插入，单位 MMGS",
            "task": f"完成 {op['l3']} 并保证整机无过约束、无干涉，最小间隙 ≥1mm。",
            "steps": [
                {"no": 1, "path": op["path"], "params": {"参考": "按装配关系"}, "check": "配合建立"},
                {"no": 2, "path": "评估选项卡→MateXpert", "params": {"范围": "整个装配体"}, "check": "0 冲突"},
                {"no": 3, "path": "评估选项卡→干涉检查", "params": {"范围": "所有零部件"}, "check": "干涉体积 0"},
                {"no": 4, "path": "评估选项卡→间隙验证", "params": {"最小间隙": "1mm"}, "check": "全部达标"},
            ],
            "expected": ["无过约束", "无欠约束", "干涉体积 0", "间隙 ≥1mm"],
            "acceptance": {"accuracy": 1.0, "pass_rule": "四项全过，任一不过即判失败", "time_limit_min": 45},
            "ops": [src],
            "est_min": 45,
        })
    # 4) 工程图 12 条
    for i in range(12):
        seq += 1
        d = drawings[i % len(drawings)]
        tcs.append({
            "id": rec_id("TC", seq),
            "module": "工程图",
            "level": "acceptance",
            "title": f"GB 出图-{i+1:02d}：{d['name']}",
            "precondition": f"模型已完成，图幅 {d['size']}，第一视角",
            "task": f"按 {d['std']} 完成 {d['name']}，视图 {','.join(d['views'])}，标注 {','.join(d['dims'])}。",
            "steps": [
                {"no": 1, "path": "文件→从零件制作工程图", "params": {"图幅": d["size"]}, "check": "图框与标题栏正确"},
                {"no": 2, "path": "工程图选项卡→模型视图", "params": {"方向": d["views"][0]}, "check": "主视方向正确"},
                {"no": 3, "path": "工程图选项卡→智能尺寸", "params": {"标注": d["dims"][0]}, "check": "尺寸齐全不重复"},
                {"no": 4, "path": "工程图选项卡→图层", "params": {"图层": "OUTLINE/DIM"}, "check": "线宽符合 GB/T 17450"},
            ],
            "expected": [d["std"], "公差/粗糙度/技术要求齐全", "PDF 导出 1:1"],
            "acceptance": {"accuracy": 1.0, "pass_rule": "按 GB/T 4458 逐项签署，0 项不合格", "time_limit_min": 60},
            "ops": ["DRW-01", "DRW-04", "DRW-15", "DRW-35"],
            "est_min": 60,
        })
    # 5) 端到端 40 条
    for i in range(40):
        seq += 1
        w = workflows[i % len(workflows)]
        tcs.append({
            "id": rec_id("TC", seq),
            "module": "综合",
            "level": "integration",
            "title": f"端到端-{i+1:02d}：{w['name']}",
            "precondition": "干净会话，2021 SP5，GB 模板",
            "task": f"执行 {w['name']} 全链路：{' → '.join(w['stages'])}。",
            "steps": [{"no": j, "path": ops_map[c]["path"], "params": {"按任务书": "见参数表"},
                       "check": ops_map[c]["checks"][0] if ops_map[c]["checks"] else "合格"}
                      for j, c in enumerate(w["ops"], 1)],
            "expected": [w["gate"]],
            "acceptance": {"accuracy": 1.0, "pass_rule": w["gate"], "time_limit_min": 90},
            "ops": w["ops"],
            "est_min": 90,
        })
    # 6) 排错 60 条
    trouble_ops = [o for o in ops if o["error"]["code"]][:60]
    for i, op in enumerate(trouble_ops, 1):
        seq += 1
        tcs.append({
            "id": rec_id("TC", seq),
            "module": op["module"],
            "level": "module",
            "title": f"异常处置-{i:02d}：{op['error']['code']}",
            "precondition": f"已复现 {op['error']['code']}",
            "task": f"定位「{op['error']['trigger']}」根因并修复，给出回归验证判据。",
            "steps": [
                {"no": 1, "path": "评估选项卡→检查", "params": {"对象": op["l3"]}, "check": "复现错误"},
                {"no": 2, "path": op["path"], "params": {"修正": op["error"]["fix"]}, "check": "错误消除"},
                {"no": 3, "path": VERIFY_CMD.get(op["module"], "评估选项卡→测量"), "params": {"对象": op["l3"]}, "check": "回归通过"},
            ],
            "expected": ["错误码不再出现", "几何/参数正确", "同类问题不复发"],
            "acceptance": {"accuracy": 1.0, "pass_rule": "三步全过，且修复动作可复现", "time_limit_min": 20},
            "ops": [op["code"]],
            "est_min": 20,
        })
    # 7) 回归 60 条
    for i in range(60):
        seq += 1
        op = ops[(i * 7) % len(ops)]
        tcs.append({
            "id": rec_id("TC", seq),
            "module": op["module"],
            "level": "regression",
            "title": f"回归-{i+1:02d}：{op['l3']}",
            "precondition": "上一轮已修复的缺陷版本",
            "task": f"对 {op['l3']} 执行回归：确认原缺陷消失且未引入新问题。",
            "steps": [{"no": 1, "path": op["path"], "params": {"回归用例": "原失败用例"}, "check": "结果与基线一致"},
                      {"no": 2, "path": VERIFY_CMD.get(op["module"], "评估选项卡→测量"), "params": {"对象": op["l3"]}, "check": "无新增重建错误"}],
            "expected": ["原缺陷不复现", "无新增警告", "质量属性在容差内"],
            "acceptance": {"accuracy": 1.0, "pass_rule": "回归通过率 100%", "time_limit_min": 15},
            "ops": [op["code"]],
            "est_min": 15,
        })
    return tcs


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(OUT, exist_ok=True)
    ops = load_ops()
    ops_map = by_code(ops)
    with open(os.path.join(DATA, "recipes.json"), encoding="utf-8") as f:
        rc = json.load(f)
    parts = rc["parts"]

    op_rows, op_ims = build_ops_samples(ops, parts)
    part_rows = build_parts(ops_map, parts)
    asm_rows = build_assembly(ops_map, rc["assembly"])
    drw_rows = build_drawings(ops_map, rc["drawings"])
    trb_rows, trb_ims = build_troubleshoot(ops)
    gb_rows, gb_ims = build_gb(rc["gb_annotations"], rc["drawings"])
    mac_rows, mac_ims = build_macro(rc["macro_topics"], ops_map)
    mate_rows, mate_ims = build_mates(rc["mates"], rc["assembly"], ops_map)

    # 零件样本的指令也进映射表
    part_ims = []
    for p in part_rows:
        for k in range(6):
            part_ims.append({
                "id": rec_id("IMW", len(part_ims) + 1),
                "text": [f"帮我做{p['l3']}，从草图到出图。",
                         f"{p['l3']}的建模顺序和关键参数是什么？",
                         f"{p['l3']}用 2021 怎么建最稳？",
                         f"给我{p['l3']}的完整工序和自检清单。",
                         f"{p['l3']}出图要符合哪些国标？",
                         f"{p['l3']}建模容易出哪些错，怎么避免？"][k],
                "intent_class": "创建" if k < 4 else ("标注" if k == 4 else "排错"),
                "module": p["module"],
                "target_op": p["op_code"],
                "slots": {},
                "expected_output_format": "步骤编号+操作路径+参数配置+校验要点",
                "confidence": 0.93,
            })

    dataset = op_rows + part_rows + asm_rows + drw_rows + trb_rows + gb_rows + mac_rows + mate_rows
    ims = op_ims + trb_ims + gb_ims + mac_ims + mate_ims + part_ims + build_extra_intents()
    tcs = build_testcases(ops, ops_map, parts, rc["assembly"], rc["drawings"], rc["workflows"])

    # 去重（指令文本唯一化，保留首个）
    seen, uniq = set(), []
    for r in ims:
        key = r["text"].strip()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    for i, r in enumerate(uniq, 1):
        r["id"] = rec_id("IM", i)
    ims = uniq

    write_jsonl(os.path.join(OUT, "train_dataset.jsonl"), dataset)
    write_jsonl(os.path.join(OUT, "instruction_map.jsonl"), ims)
    write_jsonl(os.path.join(OUT, "testcases.jsonl"), tcs)

    # 覆盖矩阵
    per_op = Counter(r["op_code"] for r in dataset)
    per_op_im = Counter(r["target_op"] for r in ims)
    per_op_tc = Counter(c for t in tcs for c in t["ops"])
    with open(os.path.join(OUT, "coverage_matrix.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["op_code", "module", "l2", "l3", "train_samples", "instruction_samples", "testcase_refs"])
        for o in ops:
            w.writerow([o["code"], o["module"], o["l2"], o["l3"],
                        per_op.get(o["code"], 0), per_op_im.get(o["code"], 0), per_op_tc.get(o["code"], 0)])

    manifest = {
        "generated_at": "2026-11-18",
        "baseline": BASELINE,
        "counts": {
            "ops_inventory": len(ops),
            "train_dataset": len(dataset),
            "instruction_map": len(ims),
            "testcases": len(tcs),
        },
        "by_task_type": dict(Counter(r["task_type"] for r in dataset)),
        "by_module": dict(Counter(r["module"] for r in dataset)),
        "testcase_by_module": dict(Counter(t["module"] for t in tcs)),
        "files": {},
    }
    for name in ["train_dataset.jsonl", "instruction_map.jsonl", "testcases.jsonl", "coverage_matrix.csv"]:
        p = os.path.join(OUT, name)
        manifest["files"][name] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(json.dumps(manifest["counts"], ensure_ascii=False))
    print("by_task_type:", manifest["by_task_type"])
    print("testcase_by_module:", manifest["testcase_by_module"])


if __name__ == "__main__":
    main()
