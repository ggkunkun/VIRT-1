"""M1 加工工艺类型识别引擎（单一铣削 / 单一车削 / 车铣复合）。

方法：特征级证据聚合（可解释的概率模型），不是黑箱。
  1. 每个特征依据其类型 + 所处包络（回转体/棱柱体）+ 精度/粗糙度，给出
     p_turn = P(该特征必须车削) 与 p_mill = P(该特征必须铣削/动力刀)；
  2. P(需要车) = 1 - Π(1 - p_turn_i)，P(需要铣) = 1 - Π(1 - p_mill_i)；
     包络本身也作为一条证据（回转体毛坯/外形→需要车）；
  3. P(TURN)=Pt(1-Pm)，P(MILL)=(1-Pt)Pm，P(TURN_MILL)=Pt·Pm，归一化后取最大者，置信度=其概率；
  4. 置信度 < 阈值（默认 0.90）⇒ low_confidence=True，并进入异常处理策略。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import Feature, ProcessType, RecognitionResult, WorkpieceSpec

ENGINE_VERSION = "m1-evidence-1.0.0"
DEFAULT_THRESHOLD = 0.90

TURN_NATIVE = {"face", "od_cylinder", "od_taper", "groove_od", "thread_od", "chamfer_od", "bore_axial"}
MILL_NATIVE = {"planar_face", "pocket", "slot", "contour", "hole", "thread_hole", "keyway", "flat",
               "cross_hole", "polygon", "chamfer_edge"}


class LowConfidenceError(RuntimeError):
    """置信度不足且无安全兜底时抛出（策略=halt）。"""

    def __init__(self, result: RecognitionResult):
        super().__init__(f"process recognition confidence {result.confidence:.3f} below threshold")
        self.result = result


def _is_offset_axial_hole(f: Feature) -> bool:
    return f.type in ("hole", "thread_hole") and (f.on_axis is False or f.params.get("radius", 0) > 0.05)


def feature_evidence(f: Feature, env_type: str, part_d: float) -> Tuple[float, float, str]:
    """返回 (p_turn, p_mill, 说明)。数值为工艺规则的先验强度（可审计，非拟合）。"""
    t = f.type
    tight = (f.tolerance_mm is not None and f.tolerance_mm <= 0.025) or (f.ra_um is not None and f.ra_um <= 0.8)
    if env_type == "cylindrical":
        if t in ("od_cylinder", "od_taper", "groove_od", "thread_od"):
            return 0.995, 0.0, "回转体外圆/锥/槽/螺纹 → 车削"
        if t == "face":
            return 0.97, 0.0, "回转体端面 → 车削"
        if t == "chamfer_od":
            return 0.6, 0.0, "外圆倒角（弱证据）"
        if t == "bore_axial" or (t in ("hole", "thread_hole") and f.on_axis):
            return 0.9, 0.0, "同轴内孔 → 车削（钻/镗）"
        if _is_offset_axial_hole(f):
            return 0.0, 0.97, "回转体上偏心轴向孔（分布圆孔）→ 动力刀 + C 轴"
        if t in ("keyway", "flat", "cross_hole", "polygon", "slot", "pocket"):
            return 0.0, 0.99, f"回转体上非回转特征 {t} → 动力刀铣/钻"
        if t == "planar_face":
            d = f.params.get("depth", 0.0)
            return 0.0, (0.95 if d >= 0.3 else 0.35), "回转体上平面（浅则弱证据）"
        if t == "contour":
            return 0.0, 0.9, "回转体上轮廓 → 铣"
        if t == "chamfer_edge":
            return 0.0, 0.2, "棱边倒角（弱证据，可能去毛刺）"
        return 0.0, 0.5, f"未知特征 {t}"
    # prismatic 包络
    if t in MILL_NATIVE:
        weak = t == "chamfer_edge"
        return 0.0, (0.3 if weak else 0.99), f"棱柱体 {t} → 铣削"
    if t == "bore_axial":
        return (0.3 if tight else 0.04), 0.9, "棱柱体上镗孔 → 铣床镗/圆弧插补"
    if t in ("od_cylinder", "od_taper"):
        return (0.85 if tight else 0.6), 0.2, "棱柱体上外圆凸台：可车可铣（矛盾证据）"
    if t in ("groove_od", "thread_od"):
        return 0.9, 0.0, "棱柱体上外圆槽/螺纹 → 需车削"
    if t == "face":
        return 0.05, 0.9, "棱柱体端面 → 面铣"
    if t == "chamfer_od":
        return 0.3, 0.3, "棱柱体上外圆倒角（弱）"
    return 0.0, 0.5, f"未知特征 {t}"


def envelope_evidence(wp: WorkpieceSpec) -> Tuple[float, float, List[str]]:
    env, stock = wp.envelope, wp.stock
    notes: List[str] = []
    if env.type == "cylindrical":
        p_turn = 0.97
        notes.append("包络为回转体")
        if stock.type in ("block", "plate"):
            p_turn = 0.75
            notes.append("但毛坯为方料：回转体由方料加工，证据减弱")
        d, l = env.diameter or 0, env.length or 0
        if d and l and d / l > 12:
            p_turn = min(p_turn, 0.6)
            notes.append(f"D/L={d / l:.1f} 极薄盘：也可能由板料铣出")
        return p_turn, 0.0, notes
    notes.append("包络为棱柱体")
    p_mill = 0.97 if stock.type in ("block", "plate", "casting") else 0.8
    if stock.type in ("bar", "tube"):
        notes.append("但毛坯为棒/管料：棱柱体由圆料加工，证据减弱")
    return 0.0, p_mill, notes


def recognize(wp: WorkpieceSpec, threshold: float = DEFAULT_THRESHOLD) -> RecognitionResult:
    env_t = wp.envelope.type
    part_d = wp.envelope.diameter or 0.0
    pt_env, pm_env, rationale = envelope_evidence(wp)
    log_not_t = math.log(max(1e-12, 1 - pt_env))
    log_not_m = math.log(max(1e-12, 1 - pm_env))
    votes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for f in wp.features:
        pt, pm, why = feature_evidence(f, env_t, part_d)
        votes.append({"feature": f.id, "type": f.type, "p_turn": pt, "p_mill": pm, "why": why})
        log_not_t += math.log(max(1e-12, 1 - pt))
        log_not_m += math.log(max(1e-12, 1 - pm))
    p_need_t = 1 - math.exp(log_not_t)
    p_need_m = 1 - math.exp(log_not_m)
    raw = {
        ProcessType.TURNING.value: p_need_t * (1 - p_need_m),
        ProcessType.MILLING.value: (1 - p_need_t) * p_need_m,
        ProcessType.TURN_MILL.value: p_need_t * p_need_m,
    }
    z = sum(raw.values())
    if z <= 1e-12:
        probs = {k: 1 / 3 for k in raw}
        warnings.append("无有效证据：三类等概率")
    else:
        probs = {k: v / z for k, v in raw.items()}
    label = max(probs, key=probs.get)
    conf = probs[label]
    rationale.append(f"P(需车削)={p_need_t:.4f}, P(需铣削)={p_need_m:.4f}")
    # 工艺附注（不改变判定）
    if env_t == "cylindrical" and wp.envelope.diameter and wp.envelope.length:
        ld = wp.envelope.length / wp.envelope.diameter
        if ld > 3:
            warnings.append(f"L/D={ld:.1f} > 3：建议尾座顶尖支撑（>6 需中心架）")
    hb = wp.material.hardness_hb or 0
    if hb > 480:
        warnings.append(f"硬度 {hb} HB（约 >50 HRC）：建议硬车/磨削，刀具参数需专项核验")
    if any(f.ra_um and f.ra_um < 0.4 for f in wp.features):
        warnings.append("存在 Ra<0.4 µm 要求：超出常规切削能力，建议增加磨削/研磨工序")
    result = RecognitionResult(
        part_id=wp.part_id, process_type=ProcessType(label), confidence=round(conf, 6),
        probabilities={k: round(v, 6) for k, v in probs.items()}, low_confidence=conf < threshold,
        rationale=rationale, feature_votes=votes, warnings=warnings, engine_version=ENGINE_VERSION,
    )
    return result


def handle_low_confidence(result: RecognitionResult, policy: str = "conservative_fallback") -> RecognitionResult:
    """异常处理机制。

    policy=halt：直接抛 LowConfidenceError（上游阻断）。
    policy=conservative_fallback：若前两名之一是 TURN_MILL 且二者合计 ≥ 0.97，取能力超集 TURN_MILL
      （车铣复合机能完成单一车/铣，安全但可能更贵）；否则仍阻断。所有动作写入 result.exception。
    """
    if not result.low_confidence:
        return result
    ranked = sorted(result.probabilities.items(), key=lambda kv: -kv[1])
    top2 = {ranked[0][0], ranked[1][0]}
    event: Dict[str, Any] = {"code": "LOW_CONFIDENCE", "confidence": result.confidence,
                             "policy": policy, "ranked": ranked}
    if policy == "conservative_fallback" and ProcessType.TURN_MILL.value in top2 \
            and ranked[0][1] + ranked[1][1] >= 0.97:
        event["action"] = "FALLBACK_TO_SUPERSET_TURN_MILL"
        event["resolved"] = True
        return result.model_copy(update={"process_type": ProcessType.TURN_MILL, "exception": event})
    event["action"] = "HALT"
    event["resolved"] = False
    blocked = result.model_copy(update={"exception": event})
    raise LowConfidenceError(blocked)


def evaluate(dataset: List[Dict[str, Any]], threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """在带标签数据集上测识别精度。样本：{"workpiece": {...}, "label": "MILLING|TURNING|TURN_MILL|AMBIGUOUS"}。"""
    n = correct = flagged = 0
    amb_n = amb_flagged = 0
    confusion: Dict[str, Dict[str, int]] = {}
    errors: List[Dict[str, Any]] = []
    for item in dataset:
        wp = WorkpieceSpec.model_validate(item["workpiece"])
        r = recognize(wp, threshold)
        label = item["label"]
        if label == "AMBIGUOUS":
            amb_n += 1
            amb_flagged += int(r.low_confidence)
            continue
        n += 1
        ok = r.process_type.value == label
        correct += int(ok)
        flagged += int(r.low_confidence)
        confusion.setdefault(label, {}).setdefault(r.process_type.value, 0)
        confusion[label][r.process_type.value] += 1
        if not ok:
            errors.append({"part_id": wp.part_id, "label": label, "pred": r.process_type.value,
                           "confidence": r.confidence})
    return {
        "n_labeled": n, "accuracy": (correct / n) if n else None, "correct": correct,
        "flagged_low_confidence": flagged, "n_ambiguous": amb_n,
        "ambiguous_flag_rate": (amb_flagged / amb_n) if amb_n else None,
        "confusion": confusion, "errors": errors, "threshold": threshold, "engine_version": ENGINE_VERSION,
    }


def recognize_dict(payload: Dict[str, Any], threshold: Optional[float] = None) -> Dict[str, Any]:
    wp = WorkpieceSpec.model_validate(payload)
    return recognize(wp, threshold or DEFAULT_THRESHOLD).model_dump(mode="json")
