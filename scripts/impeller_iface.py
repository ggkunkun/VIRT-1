# -*- coding: utf-8 -*-
"""叶轮设计接口契约层（移植自 cad_tools_iface 的法兰盘验证机制）。

法兰盘实测：失败 largely 是接口给了可抄示例 + 无证据约束造成；修契约+掩码少样本后
LoRA 与基座双双通过（无需改权重）。本模块把同一机制移植到封闭式叶轮设计域。

口径：契约只声明【行为纪律 + 定义域不等式 + 方法名】，不给出尺子的具体公式常数/容差/
 worked 数值解——那些是探针内部，泄露即 gaming（飞轮 §5）。数值演示全部掩码。
"""
import re
import json

IMPELLER_REPAIR_CONTRACT = (
    "契约（必须遵守）：\n"
    "1. 自主选定一套自洽的叶轮参数；禁止照抄下面演示里出现过的任何尺寸组合——演示只教走法，"
    "数值已全部隐去，照抄不会计分。\n"
    "2. 证据约束：claimed_tip_speed_m_s、claimed_pressure_ratio、claimed_FOS 三个宣称值必须由你给出的"
    "参数真实计算后才能填写；没有计算过程不得宣称任何性能数值。叶尖速定义 u2=π·D2·N/60000"
    "（D2 用 mm、N 用 rpm、u2 得 m/s），宣称叶尖速必须等于此式结果。\n"
    "3. 被审计判红时：violations 逐条指出了违反的不等式或物理边界。必须依据这些边界推导合规区间，"
    "仅对违规字段做确定性修正后重新输出完整 JSON；严禁原样重发同一组参数，严禁在解空间随机穷举。\n"
    "4. 输出必须是单个合法 JSON 代码块；禁止把反馈文字或解释语句插入 JSON 字段内部（那会损坏 JSON）。\n"
    "5. 几何自洽硬不等式（离心叶轮定义域）：0≤bore<D1h<D1t<D2（bore=0 表示无中心通孔的整体转子/实心轮毂）；0.40≤D1t/D2≤0.85；"
    "0.02≤b2/D2≤0.10；0.20·D2≤axial_length≤0.55·D2；"
    "axial_length≥hub_disk_thickness+shroud_thickness+b2；叶片厚≥1.2、盖盘厚≥1.5、叶根圆角≥1.0；"
    "进口叶片通道净宽 π·D1t/Z−叶厚≥8mm。\n"
    "6. 物理闭环须自行迭代计算（不得硬编码结果）：用 Wiesner 滑移系数 + Euler 透平方程迭代出口密度"
    "求总压比；由进口速度三角形迭代进口密度求叶顶相对马赫数（≤1.15）；用旋转盘离心等效应力（含叶片载荷）"
    "求 FOS（≥1.5）。压比目标 π≥4.0 需要足够高的叶尖速与合理的出口角/流道宽配合。\n"
    "7. 熔断：连续 2 次同一参数违规或 3 次尝试失败，立即停止修改并说明几何/物理冲突根因，不进行无限穷举。\n"
)

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MM_FIELDS = {"D2_mm", "b2_mm", "D1t_mm", "D1h_mm", "axial_length_mm", "shroud_thickness_mm",
             "blade_thickness_mm", "hub_disk_thickness_mm", "bore_diameter_mm", "fillet_root_mm"}


def mask_prose(text):
    return NUMBER.sub("<数值>", str(text or ""))


def mask_params(p):
    """保留字段走法，隐去全部可抄数值。"""
    if not isinstance(p, dict):
        return p
    out = {}
    for k, v in p.items():
        if k == "design_rationale":
            out[k] = "<设计依据，数值隐去>"
        elif k == "Z_blades":
            out[k] = "<整数>"
        elif k == "N_rpm":
            out[k] = "<rpm>"
        elif k == "beta2b_deg":
            out[k] = "<deg>"
        elif k in MM_FIELDS:
            out[k] = "<mm>"
        elif isinstance(v, (int, float)):
            out[k] = "<值>"
        else:
            out[k] = v
    return out


def mask_ruler_feedback(data):
    """tool 返回的复算量也是答案，须掩码。"""
    if not isinstance(data, dict):
        return mask_prose(data)
    out = {}
    for k, v in data.items():
        if k == "violations" and isinstance(v, list):
            out[k] = [mask_prose(x) for x in v]
        elif k in ("values", "ruler_values") and isinstance(v, dict):
            out[k] = {kk: "<复算值>" for kk in v}
        elif isinstance(v, (int, float)):
            out[k] = "<复算值>"
        else:
            out[k] = mask_prose(v) if isinstance(v, str) else v
    return out


def render_fewshot(records, k=2):
    lines = [f"下面 {k} 个例子只演示走法（被判红→依边界确定性修正→重发→据实汇报），"
             "其中尺寸数值、复算数值已全部隐去：标准与数值必须你自己选，照抄演示不会被计分。"]
    for i, rec in enumerate(records[:k], 1):
        lines.append(f"【例 {i}】")
        for m in rec.get("messages", []):
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                lines.append("user 请求 " + str(content)[:160])
            elif role == "assistant":
                try:
                    pj = json.loads(content)
                    lines.append("assistant 参数 " + json.dumps(mask_params(pj), ensure_ascii=False))
                except Exception:
                    lines.append("assistant 答复 " + mask_prose(content)[:200])
            elif role == "tool":
                try:
                    tj = json.loads(content)
                    lines.append("tool 审计 " + json.dumps(mask_ruler_feedback(tj), ensure_ascii=False))
                except Exception:
                    lines.append("tool 审计 " + mask_prose(content)[:200])
    return "\n".join(lines)


def assert_no_copyable_numbers(rendered):
    """反作弊自检：渲染后的演示不得含可抄的尺寸数值（飞轮 §5）。"""
    leaks = re.findall(r'"(?:D2_mm|D1t_mm|D1h_mm|b2_mm|N_rpm|bore_diameter_mm|claimed_tip_speed_m_s)"\s*:\s*-?\d', rendered)
    return leaks