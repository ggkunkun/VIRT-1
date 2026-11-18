#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已知漏洞回归集（H1~H11 共 12 条断言）。

来源：2026-11-08《世界工程模型漏洞审计报告》复现脚本 `wm_repro_vulnerabilities.py`。
原脚本断言方向是「漏洞能被复现」（REPRO = 失败）；本文件把方向翻转为
「漏洞必须不复现」（PASS = 修复生效），作为审计脚本 `wm_audit_full.py` 的
非自证检查项——避免审计只由被测实现自己证明自己（原 H11 缺陷）。

用法: .venv/Scripts/python.exe scripts/wm_vuln_regression.py
退出码: 0 全部已修复；1 仍有漏洞残留。
"""
from __future__ import annotations

import json
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
os.chdir(ROOT)

import anti_hallucination_guard as A      # noqa: E402
import guard_hooks as H                   # noqa: E402
import wm_contract as C                   # noqa: E402
import wm_gate as G                       # noqa: E402
import wm_verifier as V                   # noqa: E402

PASS = []
FAIL = []


def chk(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}" + (f"  {detail}" if detail else ""))


# ------------------------------------------------------------ H1 场景推断覆盖
NL = [
    ("removal", "铣削 45钢，切削深度 2 mm，切削宽度 5 mm，进给速度 400 mm/min，路径长度 100 mm，毛坯 200x100x50 mm，求去除体积。"),
    ("removal", "这根轴外圆车一刀，ap=1.5mm，f=0.2mm/r，n=1200r/min，车削长度 80mm，材料 45 钢。"),
    ("fea_fos", "悬臂梁长 200 mm，截面 20x20 mm，端部载荷 500 N，材料屈服 355 MPa，求安全系数。"),
    ("collision", "五轴加工叶轮，刀柄直径 32 mm，刀具长 80 mm，求无碰撞的 Z 向最小退刀高度。"),
    ("tolerance", "孔 φ50 H7，轴 φ50 g6，求配合间隙与配合类型。"),
    ("mass_props", "45 钢板 200x100x50 mm，密度 7.85e-3 g/mm^3，求质量与惯性矩。"),
    ("design", "毛坯外径 φ197.6 mm，内孔直径 80 mm，厚 25 mm，45钢，求体积与质量。"),
    ("process", "45 钢台阶轴，粗车-半精车-精车，Ra 要求 1.6，给出切削速度与进给建议。"),
    ("adapt_material", "把 45 钢换成 6061 铝合金，切削速度怎么调？"),
    ("removal", "老师让我算切了多重，钢件，去了 1000 立方毫米，密度按 7.85 克每立方厘米。"),
    ("fea_fos", "这个零件受力 300N，安全系数够不够？材料 Q235。"),
]
none_cnt, wrong = 0, []
for gt, u in NL:
    inf = A.infer_scenario_from_prompt(u)
    if inf is None:
        none_cnt += 1
        wrong.append(f"{gt}:None")
    elif inf.get("task") != gt:
        wrong.append(f"{gt}->{inf.get('task')}")
chk("H1 自然口吻题面能推断出正确族（L2 不得静默失效）",
    none_cnt == 0 and not wrong, f"None {none_cnt}/{len(NL)}, 错族 {wrong}")

# 推断失败时必须显式标记，不得假绿
r = H.apply_guard(json.dumps({"world_state": {"material_removed_mm3": 999999, "mrr_mm3_per_min": 12345}}),
                  prompt="切了大概多少料？", scenario=None)
chk("H1b 推断失败时 Guard 必须标记未校验（不得静默 accept 无标记）",
    r["action"] != "accept" or bool(r.get("layers_hit")), f"action={r['action']} layers={r['layers_hit']}")

# ------------------------------------------------------------ H2 体积差错族抢判
u2 = "毛坯体积 25000 mm^3，成品体积 23430.06 mm^3，求体积差。"
inf2 = A.infer_scenario_from_prompt(u2)
chk("H2 体积差题必须归 geom_delta 且参数非空",
    bool(inf2) and inf2.get("task") == "geom_delta"
    and any(v is not None for v in (inf2.get("inputs") or {}).values()), f"infer={inf2}")

# ------------------------------------------------------------ H3 否定词前置门误伤
u3 = "【场景】毛坯 200x100x50 mm，45钢，DOC=2mm，Vf=400mm/min。若题面未给出的参数请忽略，计算材料去除体积。"
inf3 = A.infer_scenario_from_prompt(u3)
chk("H3 含「未给出的参数请忽略」的合法题不得判 invalid",
    bool(inf3) and inf3.get("task") != "invalid", f"infer={inf3}")

r3 = H.apply_guard(json.dumps({"world_state": {"surface_roughness_ra_um": 2.25}}),
                   prompt="缺参数的题", scenario={"task": "invalid", "inputs": {}})
_f3 = r3["final_world_state"] or {}


def _ws_of(obj):
    """final_world_state 既可能是平铺 world_state，也可能包着 world_state 子对象。"""
    if isinstance(obj, dict) and isinstance(obj.get("world_state"), dict):
        return obj["world_state"]
    return obj if isinstance(obj, dict) else {}


chk("H3b invalid 族护栏不得改写正确的数值答案",
    _ws_of(_f3).get("surface_roughness_ra_um") == 2.25,
    f"action={r3['action']} final={_f3}")

# ------------------------------------------------------------ H4 verify 顶层 invalid 免检
sc_removal = {"task": "removal", "inputs": {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
                                            "rho": 7.85e-3, "stock_vol": 200000.0}}
v4 = V.verify({"invalid": True, "world_state": None, "reason": "我没算"}, sc_removal)
chk("H4 verify() 不得对可算场景的 invalid:true 直接 accept",
    v4.get("action") != "accept", f"{v4.get('action')}/{v4.get('ok')}")

# ------------------------------------------------------------ H5 场景绑错静默覆盖
r5 = H.apply_guard(json.dumps({"world_state": {"surface_roughness_ra_um": 2.25}}),
                   prompt="f=0.12,r_eps=0.8",
                   scenario={"task": "roughness", "inputs": {"f": 0.20, "r_eps": 0.8}})
chk("H5 场景与题面不同源时不得静默覆盖正确答案（应 escalate）",
    r5["action"] != "corrected", f"action={r5['action']} final={r5['final_world_state']}")

# ------------------------------------------------------------ H6 布尔陷阱
chk("H6a 字符串 'False' 不得被判成有干涉（gouge=red）",
    str(G.normalize({"gouge": "False", "collision_risk": "none"}).get("autodiff")) != "red",
    str(G.normalize({"gouge": "False", "collision_risk": "none"}).get("autodiff")))
chk("H6b safety_factor=True(bool) 必须走 fos_gate 判定",
    G.normalize({"safety_factor": True}).get("fos_gate") is not None,
    str(G.normalize({"safety_factor": True}).get("fos_gate")))

# ------------------------------------------------------------ H7 静默舍入改写
ws7 = {"before_volume_mm3": 25000.0, "after_volume_mm3": 23430.06, "delta_volume_mm3": -1570.0}
corr7: list = []
n7 = G.normalize(dict(ws7), corrections=corr7)["after_volume_mm3"]
chk("H7 gate.normalize 不得静默改写数值（擅改必须记账）",
    n7 == ws7["after_volume_mm3"] or bool(corr7), f"{ws7['after_volume_mm3']} -> {n7} corr={corr7}")

# ------------------------------------------------------------ H8 证据门漏拦
sc_r = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}
r8 = H.apply_guard(json.dumps({"world_state": {"surface_roughness_ra_um": 2.25}}) + "\n已通过校验。",
                   prompt="f=0.12,r_eps=0.8", scenario=sc_r)
chk("H8 证据门必须拦住「已通过校验」类无证据结论", r8["action"] != "accept", f"action={r8['action']}")

# ------------------------------------------------------------ H10 未登记键静默丢弃
unreg: list = []
merged = C.merge_nested_top({"world_state": {"surface_roughness_ra_um": 2.25, "my_extra_flag": "ok"}},
                            {"surface_roughness_ra_um": 2.25}, unreg)
chk("H10 契约未登记的字段必须保留并记账（不得静默丢弃）",
    merged.get("my_extra_flag") == "ok" and bool(unreg), f"merged={merged} unreg={unreg}")

# --------------------------------------------------- H12 design 自然语序（本轮新增）
# 来源：2026-11-08 评测题面改写层。生产口吻「需要一张…法兰的 CAD 建模规格」
# 没有「设计」二字，螺栓孔写成「4 个 φ6.3 mm 的螺栓孔」时孔名在后 —— 旧触发
# 条件两者都不认，design 掉进通用键值兜底：r_out 变成直径（与半径语义冲突）、
# 螺栓孔数量与孔径整体丢失，等于把设计题降级成没有特征树的空壳。
_U12 = ("需要一张钛合金TC4法兰的 CAD 建模规格：外径 φ304 mm、中心孔 φ87.5 mm、"
        "厚度 30.8 mm；4 个 φ6.3 mm 的螺栓孔均布于 φ176.3 mm 节圆。"
        "同时给出体积与质量。")
_I12 = A.infer_scenario_from_prompt(_U12) or {}
_I12IN = _I12.get("inputs") or {}
chk("H12 design 自然语序必须归 design，且 r_out 取半径、螺栓孔不丢",
    _I12.get("task") == "design"
    and abs((_I12IN.get("r_out") or 0) - 152.0) < 1e-6
    and abs((_I12IN.get("r_hole") or 0) - 3.15) < 1e-6
    and _I12IN.get("n_holes") == 4, f"{_I12}")

# H13 尺寸数字不得被当成牌号
chk("H13 φ304 mm 的 304 不得被判成不锈钢304（材料须保钛合金 4.43e-3）",
    abs((_I12IN.get("rho") or 0) - 4.43e-3) < 1e-9, f"rho={_I12IN.get('rho')}")
_I13 = A.infer_scenario_from_prompt(
    "45 钢法兰，外径 φ304 mm，中心孔 φ80 mm，厚度 25 mm，6×φ10 mm 螺栓孔均布于 φ200 mm 节圆。") or {}
chk("H13b 牌号与尺寸同时出现时以牌号为准（45钢 7.85e-3）",
    abs(((_I13.get("inputs") or {}).get("rho") or 0) - 7.85e-3) < 1e-9,
    f"rho={(_I13.get('inputs') or {}).get('rho')}")

# H15 「表面质量」不得被 0b 误判成「要质量却没给物性」
_I15 = A.infer_scenario_from_prompt(
    "45钢外圆车削，进给量 f=0.12 mm/r，刀尖圆弧半径 r_eps=0.8 mm，求表面质量 Ra。") or {}
chk("H15 「表面质量」不得被判成要质量却没给物性（须归 roughness）",
    _I15.get("task") == "roughness", f"{_I15}")

# --------------------------------------------------- H14 题面改写保真（本轮新增）
# 改写只准换措辞：改写后重解出的输入必须与原 scenario.inputs 逐字段相等，
# 否则「换了措辞」等于「换了一道题」，评测指标失去可比性。
# 复用去污探针里的 fidelity()，直接跑真实生成器，避免手搓样本与生成器结构脱节。
import wm_eval_purity as _PU  # noqa: E402

_rows14, _bad14 = _PU.fidelity(8)
chk("H14 题面改写不得改动输入数值（12 族各 8 条，改写只换措辞）",
    not _bad14, f"{_bad14[:3]}")

# ------------------------------------------------------------ 汇总
print(f"\n=== 漏洞回归：已修复 {len(PASS)} 项，残留 {len(FAIL)} 项 ===")
if FAIL:
    print("残留：", FAIL)
raise SystemExit(0 if not FAIL else 1)
