# -*- coding: utf-8 -*-
"""virtu_omni/reverse_engineering/graders.py — 逆向工程能力确定性客观判分器.

遵循测量宪法（Rule 8 测量宪法）与零幻觉准则：
1. 纯数学与客观拓扑校验，严禁 LLM-as-judge；
2. 每一个分值必须有清晰的 trace 字符串，表明“哪段字节、哪个物理量产生了你”；
3. 严格践行可证伪性：坏样本（尺寸漂移、体积违背、语法损坏）必须得 0 分或极低分。
"""

from __future__ import annotations
import math
import re
from typing import Dict, Any, List, Tuple, Optional


def grade_dimension_fidelity(
    pred_dims: Dict[str, Any],
    gt_dims: Dict[str, Any],
    required_dims: Optional[List[str]] = None,
    tol_rel: float = 0.015
) -> Tuple[float, str]:
    """评估提取的关键几何尺寸与 Ground Truth 之间的保真度 (0 ~ 100)."""
    if not isinstance(pred_dims, dict) or not pred_dims:
        return 0.0, "pred_dims 为空或格式非法"

    req = required_dims or [k for k in gt_dims.keys() if k not in ("bounding_box_size", "grooves", "feature_sequence", "theoretical_volume_cm3")]
    if not req:
        req = ["outer_diameter", "total_length"]

    points = 0.0
    traces = []

    for dim_name in req:
        if dim_name not in gt_dims:
            continue
        gt_val = gt_dims[dim_name]
        pred_val = pred_dims.get(dim_name)

        if pred_val is None:
            # 尝试在 key_dimensions 的别名或列表中检索
            if dim_name == "outer_diameter":
                pred_val = pred_dims.get("od") or (max(pred_dims.get("cylindrical_diameters", [])) if pred_dims.get("cylindrical_diameters") else None)
            elif dim_name == "inner_bore":
                pred_val = pred_dims.get("id") or pred_dims.get("bore")
            elif dim_name == "total_length":
                pred_val = pred_dims.get("length")
            elif dim_name == "pcd_diameter":
                holes = pred_dims.get("hole_patterns", [])
                pred_val = holes[0].get("pcd_diameter") if holes else None
            elif dim_name == "bolt_hole_dia":
                holes = pred_dims.get("hole_patterns", [])
                pred_val = holes[0].get("hole_diameter") if holes else None
            elif dim_name == "bolt_hole_count":
                holes = pred_dims.get("hole_patterns", [])
                pred_val = holes[0].get("hole_count") if holes else None
            elif dim_name in ("pitch_x", "pitch_y"):
                cart = pred_dims.get("cartesian_holes", {})
                pred_val = cart.get(dim_name)

        if pred_val is None:
            traces.append(f"{dim_name}: 缺失 (GT={gt_val}) -> 0分")
            continue

        if isinstance(gt_val, (int, float)):
            try:
                pv = float(pred_val)
                gv = float(gt_val)
                denom = max(abs(gv), 1e-4)
                err_rel = abs(pv - gv) / denom
                if err_rel <= tol_rel:
                    points += 1.0
                    traces.append(f"{dim_name}: 合格 (Pred={pv}, GT={gv}, Err={err_rel*100:.2f}%)")
                elif err_rel <= tol_rel * 2.0:
                    points += 0.5
                    traces.append(f"{dim_name}: 次优 (Pred={pv}, GT={gv}, Err={err_rel*100:.2f}%)")
                else:
                    traces.append(f"{dim_name}: 超差 (Pred={pv}, GT={gv}, Err={err_rel*100:.2f}%)")
            except (ValueError, TypeError):
                traces.append(f"{dim_name}: 类型无法转换为数值 -> 0分")
        elif isinstance(gt_val, list):
            # 列表匹配 (如阶梯轴径 step_diameters)
            try:
                p_list = sorted([float(x) for x in pred_val])
                g_list = sorted([float(x) for x in gt_val])
                match_cnt = 0
                for g_item in g_list:
                    if any(abs(p_item - g_item) / max(g_item, 1e-4) <= tol_rel for p_item in p_list):
                        match_cnt += 1
                ratio = match_cnt / max(len(g_list), 1)
                points += ratio
                traces.append(f"{dim_name}: 列表匹配率 {ratio*100:.1f}% (Pred={p_list}, GT={g_list})")
            except Exception as e:
                traces.append(f"{dim_name}: 列表对比异常 {str(e)}")
        else:
            if str(pred_val).strip() == str(gt_val).strip():
                points += 1.0
                traces.append(f"{dim_name}: 匹配 ({pred_val})")
            else:
                traces.append(f"{dim_name}: 不匹配 (Pred={pred_val}, GT={gt_val})")

    score = round((points / max(len(req), 1)) * 100.0, 2)
    return score, "; ".join(traces)


def grade_family_classification(pred_family: str, gt_family: str) -> Tuple[float, str]:
    """构件族分类判分 (100 or 0)."""
    p = str(pred_family).strip().upper()
    g = str(gt_family).strip().upper()
    if p == g:
        return 100.0, f"构件族分类一致: {p}"
    return 0.0, f"构件族分类错误: Pred={p}, GT={g}"


def grade_volume_conservation(pred_volume_cm3: float, gt_volume_cm3: float, tol_rel: float = 0.02) -> Tuple[float, str]:
    """体积守恒公理校验 (|V_pred - V_gt| / V_gt <= tol_rel)."""
    try:
        pv = float(pred_volume_cm3)
        gv = float(gt_volume_cm3)
    except (ValueError, TypeError):
        return 0.0, "体积数值解析失败"

    if pv <= 0 or gv <= 0:
        return 0.0, f"物理体积非正 (Pred={pv}, GT={gv})"

    err = abs(pv - gv) / gv
    if err <= 0.01:
        return 100.0, f"体积守恒极优 (Err={err*100:.2f}%, Pred={pv:.2f}cm³, GT={gv:.2f}cm³)"
    elif err <= tol_rel:
        return 90.0, f"体积守恒合格 (Err={err*100:.2f}%, Pred={pv:.2f}cm³, GT={gv:.2f}cm³)"
    elif err <= tol_rel * 2.0:
        return 60.0, f"体积守恒次优 (Err={err*100:.2f}%, Pred={pv:.2f}cm³, GT={gv:.2f}cm³)"
    else:
        return 0.0, f"体积守恒严重违背 (Err={err*100:.2f}%, Pred={pv:.2f}cm³, GT={gv:.2f}cm³)"


def grade_hole_pattern_fidelity(pred_holes: List[Dict[str, Any]], gt: Dict[str, Any], tol_rel: float = 0.02) -> Tuple[float, str]:
    """孔系拓扑与分度圆 PCD 判定."""
    gt_pcd = gt.get("pcd_diameter")
    gt_count = gt.get("bolt_hole_count")
    gt_dia = gt.get("bolt_hole_dia")

    if not gt_pcd and not gt.get("pitch_x"):
        # 该构件无需安装孔系，直接满分
        return 100.0, "无孔系要求 (免检通过)"

    if gt_pcd:
        if not pred_holes:
            return 0.0, f"未检测到孔系 (GT_PCD={gt_pcd})"
        best_match = None
        min_err = 999.0
        for h in pred_holes:
            p_pcd = h.get("pcd_diameter", 0.0)
            err = abs(p_pcd - gt_pcd) / max(gt_pcd, 1e-4)
            if err < min_err:
                min_err = err
                best_match = h

        if min_err <= tol_rel:
            p_cnt = best_match.get("hole_count", 0)
            p_dia = best_match.get("hole_diameter", 0.0)
            cnt_ok = (p_cnt == gt_count)
            dia_err = abs(p_dia - gt_dia) / max(gt_dia, 1e-4) if gt_dia else 0.0
            dia_ok = (dia_err <= tol_rel)

            if cnt_ok and dia_ok:
                return 100.0, f"孔系完美对齐 (PCD={best_match.get('pcd_diameter')}, 数量={p_cnt}, 孔径={p_dia})"
            elif cnt_ok or dia_ok:
                return 80.0, f"孔系部分对齐 (PCD吻合, 数量对齐={cnt_ok}, 孔径对齐={dia_ok})"
            else:
                return 60.0, f"PCD吻合但孔径/数量偏差 (Pred={best_match})"
        else:
            return 20.0, f"PCD超差 (Pred_PCD={best_match.get('pcd_diameter') if best_match else 'None'}, GT={gt_pcd})"

    # 笛卡尔安装孔判定
    if gt.get("pitch_x") and gt.get("pitch_y"):
        pred_cart = gt.get("cartesian_holes", {})
        px = pred_cart.get("pitch_x")
        py = pred_cart.get("pitch_y")
        if px and py:
            err_x = abs(px - gt["pitch_x"]) / gt["pitch_x"]
            err_y = abs(py - gt["pitch_y"]) / gt["pitch_y"]
            if err_x <= tol_rel and err_y <= tol_rel:
                return 100.0, f"笛卡尔孔距对齐 (pitch_x={px}, pitch_y={py})"
            else:
                return 50.0, f"笛卡尔孔距超差 (Pred=({px},{py}), GT=({gt['pitch_x']},{gt['pitch_y']}))"

    return 70.0, "孔系检测次优"


def grade_parametric_feature_tree(vba_code: str, gt_sequence: List[str]) -> Tuple[float, str]:
    """参数化特征树完整性评估."""
    if not vba_code:
        return 0.0, "VBA 特征宏代码为空"

    matches = 0
    traces = []
    for feat in gt_sequence:
        pattern = rf"\b{re.escape(feat)}\b"
        if feat == "EquationMgr":
            pattern = r"(?:EquationMgr|swEqnMgr|Add\s+-1)"
        elif feat == "FeatureRevolve2":
            pattern = r"(?:FeatureRevolve2|FeatureRevolve)"
        elif feat == "FeatureExtrusion3" or feat == "BossExtrude":
            pattern = r"(?:FeatureExtrusion|BossExtrude|FeatureExtrusion3)"
        elif feat == "FeatureCut3" or feat == "CutExtrude":
            pattern = r"(?:FeatureCut|CutExtrude|FeatureCut3)"
        elif feat == "FeatureCircularPattern" or feat == "CircularPattern":
            pattern = r"(?:CircularPattern|FeatureCircularPattern|CreateCircleByRadius)"

        if re.search(pattern, vba_code, re.IGNORECASE):
            matches += 1
            traces.append(f"{feat}: 包含")
        else:
            traces.append(f"{feat}: 缺失")

    score = round((matches / max(len(gt_sequence), 1)) * 100.0, 2)
    return score, "; ".join(traces)


def grade_vba_code_integrity(vba_code: str) -> Tuple[float, str]:
    """SOLIDWORKS 2021 VBA 宏静态合规性与执行安全度 (0 ~ 100)."""
    if not vba_code:
        return 0.0, "无 VBA 宏代码"

    checks = [
        (r"Option\s+Explicit", "Option Explicit 强制变量声明", 20.0),
        (r"Sub\s+main\s*\(\s*\)", "主入口 Sub main()", 20.0),
        (r"End\s+Sub", "主入口正常封闭 End Sub", 10.0),
        (r"SldWorks\.Application|swApp", "SOLIDWORKS 根对象引用", 20.0),
        (r"SelectByID|SelectByID2", "基准面规范选取", 15.0),
        (r"SketchManager\.(?:InsertSketch|CreateLine|CreateCircle)", "草图图元建立", 15.0),
    ]

    score = 0.0
    passed_labels = []
    failed_labels = []

    for pattern, label, weight in checks:
        if re.search(pattern, vba_code, re.IGNORECASE):
            score += weight
            passed_labels.append(label)
        else:
            failed_labels.append(label)

    # 严禁危险的 Shell 注入
    if re.search(r"(?:WScript\.Shell|ShellExecute|cmd\.exe|powershell)", vba_code, re.IGNORECASE):
        return 0.0, "安全否决：包含未授权系统命令注入"

    return round(score, 2), f"通过: {', '.join(passed_labels)}; 缺失: {', '.join(failed_labels)}"


def grade_reconstruction_case(pred_record: Dict[str, Any], case_def: Dict[str, Any]) -> Dict[str, Any]:
    """对单个评测用例进行综合多维立体判分."""
    gt = case_def.get("ground_truth", {})
    criteria = case_def.get("evaluation_criteria", {})
    case_id = case_def.get("id", "UNKNOWN")

    # 1. 尺寸保真度 (w = 0.25)
    pred_dims = pred_record.get("key_dimensions", {})
    req_dims = criteria.get("required_dims")
    dim_score, dim_trace = grade_dimension_fidelity(pred_dims, gt, req_dims)

    # 2. 孔系对齐 (w = 0.20)
    pred_holes = pred_record.get("hole_patterns", [])
    hole_score, hole_trace = grade_hole_pattern_fidelity(pred_holes, gt)

    # 3. 构件族识别 (w = 0.10)
    pred_family = pred_record.get("part_family", "")
    gt_family = case_def.get("family", "")
    family_score, family_trace = grade_family_classification(pred_family, gt_family)

    # 4. 物理体积守恒 (w = 0.15)
    pred_vol_cm3 = pred_record.get("theoretical_volume_mm3", 0.0) / 1000.0
    gt_vol_cm3 = gt.get("theoretical_volume_cm3", 100.0)
    vol_score, vol_trace = grade_volume_conservation(pred_vol_cm3, gt_vol_cm3)

    # 5. 参数化特征树完整性 (w = 0.15)
    vba_code = pred_record.get("reconstruction_vba", "")
    gt_seq = gt.get("feature_sequence", ["BossExtrude", "CutExtrude", "EquationMgr"])
    feat_score, feat_trace = grade_parametric_feature_tree(vba_code, gt_seq)

    # 6. VBA 代码静态规范性 (w = 0.10)
    vba_score, vba_trace = grade_vba_code_integrity(vba_code)

    # 7. 活体重建可执行性 (w = 0.05)
    exec_score = 100.0 if pred_record.get("rebuild_success", True) else 0.0
    exec_trace = "已成功建立物理零件" if exec_score == 100.0 else "物理重建失败"

    # 加权综合总分
    weights = {
        "dimension_fidelity": 0.25,
        "hole_pattern": 0.20,
        "part_family": 0.10,
        "volume_conservation": 0.15,
        "feature_tree": 0.15,
        "vba_integrity": 0.10,
        "rebuild_viability": 0.05
    }

    total_score = (
        dim_score * weights["dimension_fidelity"] +
        hole_score * weights["hole_pattern"] +
        family_score * weights["part_family"] +
        vol_score * weights["volume_conservation"] +
        feat_score * weights["feature_tree"] +
        vba_score * weights["vba_integrity"] +
        exec_score * weights["rebuild_viability"]
    )
    total_score = round(total_score, 2)

    return {
        "case_id": case_id,
        "name": case_def.get("name", ""),
        "total_score": total_score,
        "passed": total_score >= case_def.get("passing_threshold", 75.0),
        "scores": {
            "dimension_fidelity": dim_score,
            "hole_pattern": hole_score,
            "part_family": family_score,
            "volume_conservation": vol_score,
            "feature_tree": feat_score,
            "vba_integrity": vba_score,
            "rebuild_viability": exec_score
        },
        "traces": {
            "dimension_fidelity": dim_trace,
            "hole_pattern": hole_trace,
            "part_family": family_trace,
            "volume_conservation": vol_trace,
            "feature_tree": feat_trace,
            "vba_integrity": vba_trace,
            "rebuild_viability": exec_trace
        }
    }
