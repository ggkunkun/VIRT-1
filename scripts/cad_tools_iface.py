# -*- coding: utf-8 -*-
"""Shared interface layer for the CAD tool schema.

Two measured reasons the tool-calling model failed, both fixable without weights:
  1. the registered tool description ships concrete example numbers
     ({'d_outer': 53.0, 'd_inner': 14.0, 'overall_len': 45.0}), and the model copied
     them verbatim into a real job -> the geometry it asked for was self-inconsistent;
  2. nothing in the prompt states the contract "a claim needs a tool result behind it".

Both the corpus builder and the supervision harness import this, so the training
data and the runtime see the same schema.
"""

import re

# '<key>': 53.0  /  'key': 14  ->  '<key>': <mm>
EXAMPLE_NUMBER = re.compile(r"(['\"][A-Za-z_][A-Za-z0-9_]*['\"]\s*:\s*)-?\d+(?:\.\d+)?")

REPAIR_CONTRACT = (
    "契约（必须遵守）：\n"
    "1. 你要为零件自己选一套自洽的尺寸。禁止照抄工具描述里的示例数字，也禁止照抄下面演示里\n"
    "   出现过的任何尺寸组合——演示只教走法，不给你答案；请给出一套与演示不同的、工程上合理的尺寸。\n"
    "2. 只有拿到工具返回的实测数值后才能谈结果；没有工具返回值时，不得声称已完成、"
    "不得报出任何体积数字，只能继续调用工具或如实说明失败原因。\n"
    "3. 工具返回 status=rejected 时，violations 明确指出了几何冲突原因。"
    "严禁盲目猜数或在解空间中随机漫步穷举！必须依据不等式边界推导合规区间，"
    "仅针对违规尺寸做确定性修正后再调用，禁止原样重发同一组参数。\n"
    "4. 汇报体积时必须原样引用工具返回的 volume_mm3，不得改写、估算或取整；"
    "单个特征的 dv 不是最终体积，禁止把 dv 相加当作体积汇报。\n"
    "5. 法兰盘尺寸必须同时满足：d_bore < d_hub < d_outer；overall_len > thickness；"
    "pcd/2 - d_bolt/2 > d_hub/2 + 1；pcd/2 + d_bolt/2 < d_outer/2 - 2；"
    "chamfer < (d_hub - d_bore)/2；n_bolts >= 2。\n"
    "6. 本会话只有 cadcam_solidworks_model 真正连着 SOLIDWORKS；"
    "cadcam_extreme_chain / cadcam_universal_geometry / cadcam_run_full_chain 这类链式工具不会建模，"
    "调用它们只会浪费一轮，第一步就直接调 cadcam_solidworks_model。\n"
    "7. 工具返回 status=incomplete/blocked/executor_failure 表示执行器失败（不是你的参数错），"
    "错误原因在 error 字段里；此时必须重新调用同一个工具，而不是宣称完成。\n"
    "8. 任务拆解与熔断：在执行动作前，明确分解为【基准底板 -> 凸台颈部 -> 轴孔切除 -> 螺栓孔系 -> 倒角修饰 -> 工程图与公差】；"
    "若连续 2 次同一参数违规或 3 次尝试失败，立即停止修改，说明几何冲突根因，坚决不进行无限穷举。"
)


def sanitize_tool_defs(tools):
    """Strip copyable concrete numbers out of tool descriptions (shape stays)."""
    out = []
    for t in tools:
        t2 = json_clone(t)
        fn = t2.get("function", {})
        desc = fn.get("description", "")
        if desc:
            fn["description"] = EXAMPLE_NUMBER.sub(r"\1<mm>", desc)
        params = fn.get("parameters", {})
        for spec in (params.get("properties") or {}).values():
            d = spec.get("description")
            if d:
                spec["description"] = EXAMPLE_NUMBER.sub(r"\1<mm>", d)
        out.append(t2)
    return out


def json_clone(obj):
    import json
    return json.loads(json.dumps(obj))


# Actions/fields the supervised executor refuses: the schema may offer them to other
# consumers, but in the supervision ring they are a decoy - measured 2026-11-03, the
# LoRA answered "annotate the drawing" with a vba_code macro (a key not even in the
# schema) twice and never filled `annotation`, because writing a macro is what the
# corpus taught for that phrase.
SUPERVISION_FORBIDDEN_ACTIONS = ("execute_vba",)
SUPERVISION_FORBIDDEN_PROPERTIES = ("vba_code",)


def restrict_actions_for_supervision(tools):
    """Hide the routes this session will not run, so a turn is not spent discovering them."""
    out = []
    for t in tools:
        t2 = json_clone(t)
        params = (t2.get("function") or {}).get("parameters") or {}
        props = params.get("properties") or {}
        for key in list(props):
            if key in SUPERVISION_FORBIDDEN_PROPERTIES:
                del props[key]
        spec = props.get("action")
        if isinstance(spec, dict):
            enum = spec.get("enum")
            if isinstance(enum, list):
                dropped = [a for a in enum if a in SUPERVISION_FORBIDDEN_ACTIONS]
                spec["enum"] = [a for a in enum if a not in SUPERVISION_FORBIDDEN_ACTIONS]
                if dropped and spec.get("description"):
                    spec["description"] = re.sub(
                        r"[、，,]?\s*(?:或\s*)?%s（[^）]*）" % "|".join(re.escape(a) for a in dropped),
                        "", spec["description"]).strip()
        out.append(t2)
    return out


def mask_dims(call):
    """Keep the walk, withhold the answer: numeric dimension values become <mm>."""
    import json
    c = json.loads(json.dumps(call))
    args = (c.get("function") or {}).get("arguments")
    if isinstance(args, dict):
        dims = args.get("dimensions")
        if isinstance(dims, dict):
            args["dimensions"] = {k: ("<整数>" if k == "n_bolts" else "<mm>") for k in dims}
        if "part_name" in args:
            args["part_name"] = "<你起的名字>"
    return c


def mask_tool_payload(content):
    """Strip the numbers a model could copy out of a demonstrated tool *response*.

    Masking only the assistant call is not enough: the response echoes built_params
    and the per-feature measured deltas, which together are a complete, valid answer.
    """
    import json
    raw = str(content or "")
    try:
        obj = json.loads(raw)
    except Exception:
        return mask_prose(raw)
    if not isinstance(obj, dict):
        return mask_prose(raw)
    if isinstance(obj.get("built_params"), dict):
        obj["built_params"] = {k: ("<整数>" if k == "n_bolts" else "<mm>")
                               for k in obj["built_params"]}
    if isinstance(obj.get("requested"), dict):
        obj["requested"] = {k: ("<整数>" if k == "n_bolts" else "<mm>")
                            for k in obj["requested"]}
    if "volume_mm3" in obj:
        obj["volume_mm3"] = "<实测体积>"
    if "volume_error_pct" in obj:
        obj["volume_error_pct"] = "<误差>"
    steps = obj.get("steps")
    if isinstance(steps, list):
        obj["steps"] = [{"f": s.get("f") or s.get("tag"), "dv": "<实测>",
                         "want": "<解析>", "ok": s.get("ok", True)} for s in steps]
    if isinstance(obj.get("artifacts"), dict):
        obj["artifacts"] = {k: ("<已保存>" if v else None) for k, v in obj["artifacts"].items()}
    if obj.get("violations"):
        obj["violations"] = [mask_prose(str(v)) for v in obj["violations"]]
    for drop in ("wall_s", "rc", "final"):
        obj.pop(drop, None)
    return json.dumps(obj, ensure_ascii=False)


NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def mask_prose(text):
    """Numbers in narrated results are the answer too (外径 77.0 … 体积 106062.262 mm³)."""
    return NUMBER.sub("<数值>", str(text or ""))


def render_fewshot(records, k=2, mask_values=True):
    """Render the first k repair records as an explicit demonstration block."""
    import json
    lines = ["下面 %d 个例子只演示走法（被拒绝→改尺寸→重发→据实汇报），"
             "其中的尺寸数值、实测数值和零件名已全部隐去：标准与数值必须你自己选，"
             "照抄演示不会被计分。" % k]
    for i, rec in enumerate(records[:k], 1):
        lines.append("【例 %d】" % i)
        for m in rec.get("messages", []):
            role = m.get("role")
            if m.get("tool_calls"):
                for c in m["tool_calls"]:
                    shown = mask_dims(c) if mask_values else c
                    lines.append("assistant 调用 %s %s" % (
                        shown["function"]["name"],
                        json.dumps(shown["function"]["arguments"], ensure_ascii=False)))
            elif role == "tool":
                lines.append("tool 返回 %s" % (mask_tool_payload(m.get("content"))
                                               if mask_values else str(m.get("content"))[:300]))
            elif role == "assistant":
                lines.append("assistant 答复 %s" % (mask_prose(m.get("content"))[:220]
                                                    if mask_values else str(m.get("content"))[:220]))
            elif role == "user":
                lines.append("user 请求 %s" % str(m.get("content"))[:160])
    return "\n".join(lines)
