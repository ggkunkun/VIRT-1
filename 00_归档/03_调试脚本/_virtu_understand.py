# -*- coding: utf-8 -*-
"""三阶段监督协议：理解 → 方法 → 执行。

监督者只做：下发工具、派发模型自己的调用、用 ground truth 验收理解、
把模型自己写出的方案原样交给原子执行器、留 trace。不下发一键 full 工具，
不替模型选方法、不补方案缺项。
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.request

ROOT = r"D:\Virtu模型"
sys.path.insert(0, ROOT)
from bridges.bridge_security import ensure_bridge_token
from bridges.tool_calling_specs import get_cadcam_tool_definitions
from bridges.step_features import features as parse_features

OLLAMA = "http://127.0.0.1:11434/api/chat"
BRIDGE = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = ensure_bridge_token().strip()
MODEL = os.environ.get("VIRTU_SELF_MODEL", "virtu-master:latest")
STEP = r"D:\Virtu模型\assets\wheel_mold_P0.step"
OUT_DIR = os.path.join(ROOT, "works", "model_understand")

STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN = os.path.join(ROOT, "runs", "virtu_understand_" + STAMP)
os.makedirs(RUN, exist_ok=True)
TRACE = os.path.join(RUN, "trace.json")
trace: dict = {"stamp": STAMP, "model": MODEL, "protocol": "understand→method→execute",
               "step_file": STEP, "phases": [], "started": time.time()}

# 只下发「读数据」与「按方案执行」两类能力；不给一键 full 策略工具
ALLOWED = ("cadcam_step_reverse", "cadcam_feature_ops")
TOOLS = [t for t in get_cadcam_tool_definitions()
         if t.get("function", {}).get("name") in ALLOWED]
trace["tools_offered"] = [t["function"]["name"] for t in TOOLS]

TRUTH = parse_features(STEP)["ground_truth_for_acceptance"]
GT = {
    "solid_count": TRUTH["solid_count"],
    "advanced_face_count": TRUTH["advanced_face_count"],
    "cylindrical_surface_count": TRUTH["cylindrical_surface_count"],
    "conical_surface_count": TRUTH["conical_surface_count"],
    "toroidal_surface_count": TRUTH["toroidal_surface_count"],
    "plane_count": TRUTH["plane_count"],
    "circle_count": TRUTH["circle_count"],
    "assembly_component_count": TRUTH["assembly_component_count"],
    "product_count": TRUTH["product_count"],
}
GT_LISTS = {"cone_half_angles_deg": TRUTH["cone_half_angles_deg"]}


def http(url, payload, timeout=600, auth=False):
    h = {"Content-Type": "application/json"}
    if auth:
        h["Authorization"] = "Bearer " + TOKEN
    q = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                               headers=h, method="POST")
    with OPENER.open(q, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def llm(messages, tools=None, fmt=None, npredict=1200):
    p = {"model": MODEL, "messages": messages, "stream": False,
         "options": {"temperature": 0.1, "num_predict": npredict}}
    if tools:
        p["tools"] = tools
    if fmt:
        p["format"] = fmt
    return http(OLLAMA, p, timeout=420)


def dispatch(name, args):
    return http(BRIDGE + "/v1/cadcam/tools/call",
                {"name": name, "arguments": args}, timeout=600, auth=True)


def extract_json(text):
    """从模型输出里稳健取第一个完整 JSON 对象。"""
    if not text:
        return None
    dec = json.JSONDecoder()
    i = 0
    while i < len(text):
        if text[i] == "{":
            try:
                obj, end = dec.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
                i += end
                continue
            except Exception:
                pass
        i += 1
    return None


def save():
    with open(TRACE, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)


def grade(answer):
    """与 STEP 解析出的 ground truth 逐项比对，返回可量化理解得分。"""
    hits, detail = 0, {}
    for k, exp in GT.items():
        got = answer.get(k) if isinstance(answer, dict) else None
        try:
            ok = (got is not None) and (abs(float(got) - float(exp)) < 1e-6)
        except (TypeError, ValueError):
            ok = False
        detail[k] = {"expected": exp, "model": got, "pass": bool(ok)}
        hits += int(ok)
    for k, exp in GT_LISTS.items():
        got = answer.get(k) if isinstance(answer, dict) else None
        try:
            ok = (isinstance(got, list)
                  and sorted(round(float(x), 2) for x in got)
                  == sorted(round(float(x), 2) for x in exp))
        except (TypeError, ValueError):
            ok = False
        detail[k] = {"expected": exp, "model": got, "pass": bool(ok)}
        hits += int(ok)
    # 推理题：检查是否只抄数字，还是真从拓扑推出了结构结论
    reasoning = str((answer or {}).get("reasoning") or "")
    kw = {
        "旋转/回转": any(k in reasoning for k in ("旋转", "回转", "revolve")),
        "分段/扇区": any(k in reasoning for k in ("分段", "扇区", "扇形", "扇")),
        "孔": "孔" in reasoning or "hole" in reasoning.lower(),
        "装配/位姿": any(k in reasoning for k in ("装配", "位姿", "组件", "总成")),
    }
    detail["reasoning_keywords"] = kw
    hits += sum(kw.values())
    total = len(GT) + len(GT_LISTS) + len(kw)
    return {"score": hits, "total": total,
            "percent": round(100.0 * hits / total, 1), "detail": detail,
            "passed": hits >= total * 0.7,
            "numeric_subscore": "%s/%s" % (sum(1 for k, v in detail.items()
                                             if k in GT or k in GT_LISTS if v.get("pass")),
                                          len(GT) + len(GT_LISTS))}


def normalize_ops(raw_ops):
    """无损语法规范化：把模型写出的「op(参数)」文本转成等价 JSON 对象。

    只解析模型**已经写出**的 op 名与 key=value；纯占位参数名不填值，
    由执行器用其公开默认值处理（会在 notes 里逐项标注）。
    不新增、不删除、不重排任何操作 —— 方法决策完全保留模型原样。
    """
    out, notes = [], []
    for i, x in enumerate(raw_ops or []):
        if isinstance(x, dict) and isinstance(x.get("op"), str):
            out.append(x)
            notes.append({"idx": i, "source": "model_json_object"})
            continue
        if isinstance(x, str):
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\((.*)\))?\s*$", x)
            if not m:
                notes.append({"idx": i, "source": "unparseable", "raw": x})
                continue
            o = {"op": m.group(1)}
            for k, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,)]+)", m.group(2) or ""):
                v = v.strip()
                if v in ("true", "false"):
                    o[k] = (v == "true")
                else:
                    try:
                        o[k] = float(v) if any(c in v for c in ".eE") else int(v)
                    except ValueError:
                        o[k] = v
            out.append(o)
            placeholders = [p.strip() for p in (m.group(2) or "").split(",")
                            if p.strip() and "=" not in p]
            notes.append({"idx": i, "source": "normalized_from_model_text", "raw": x,
                          "parsed": o,
                          "unfilled_placeholders_use_executor_default": placeholders})
        else:
            notes.append({"idx": i, "source": "unknown_type", "raw": repr(x)[:80]})
    return out, notes


def main():
    print("MODEL", MODEL, "TOOLS", trace["tools_offered"], flush=True)
    print("GROUND_TRUTH", json.dumps(GT, ensure_ascii=False), flush=True)

    # ---------- Phase A: 让模型自己读特征树 ----------
    sys_a = ("你是工业逆向工程师。必须先调用 cadcam_step_reverse 的 features 动作读取 "
             "STEP 的 B-Rep 特征树内容，再开始分析。不要凭空猜。")
    usr_a = ("输入文件在工作区内：" + STEP +
             "\n请调用工具读取它的特征树内容（产品层级、实体、面类型与参数、装配位姿）。")
    msgs = [{"role": "system", "content": sys_a}, {"role": "user", "content": usr_a}]
    feat_payload = None
    t0 = time.time()
    try:
        d = llm(msgs, tools=TOOLS)
        m = d.get("message", {})
        calls = m.get("tool_calls") or []
        content = m.get("content") or ""
        thinking = m.get("thinking") or ""
        # 兼容把调用写在文本/thinking 里的 Qwen3 系
        if not calls:
            blob = content + "\n" + thinking
            dec = json.JSONDecoder()
            for i, ch in enumerate(blob):
                if ch == "{":
                    try:
                        obj, _ = dec.raw_decode(blob[i:])
                        nm = obj.get("name")
                        if isinstance(nm, str) and nm.startswith("cadcam_"):
                            calls = [{"function": {"name": nm,
                                                   "arguments": obj.get("arguments", {})}}]
                            break
                    except Exception:
                        pass
        print("PHASE_A calls", [c.get("function", {}).get("name") for c in calls],
              "%.1fs" % (time.time() - t0), flush=True)
        for c in calls:
            nm = c.get("function", {}).get("name")
            ar = c.get("function", {}).get("arguments", {})
            if isinstance(ar, str):
                try:
                    ar = json.loads(ar)
                except Exception:
                    ar = {}
            if nm == "cadcam_step_reverse":
                # 无论模型写了哪个 action，第一阶段一律给它特征树数据
                ar["action"] = "features"
                feat_payload = dispatch(nm, ar)
        if feat_payload is None:
            # 模型没调用工具：监督者补喂数据，但不替它做任何推断
            print("PHASE_A model did not call tool; supervisor supplies raw data", flush=True)
            feat_payload = dispatch("cadcam_step_reverse", {"action": "features"})
            trace["phase_a_supervisor_feed"] = True
    except Exception as e:
        print("PHASE_A ERR", type(e).__name__, str(e)[:120], flush=True)
        feat_payload = dispatch("cadcam_step_reverse", {"action": "features"})
        trace["phase_a_supervisor_feed"] = True
    trace["phases"].append({"phase": "A_read_features", "latency_s": round(time.time() - t0, 2),
                            "model_called_tool": feat_payload is not None,
                            "features_status": feat_payload.get("status") if feat_payload else None})
    save()

    # ---------- Phase B: 结构化理解 + 自动验收 ----------
    # 关键：不要把 ground_truth 答案字段喂给模型，否则「验收」只是在考它会不会复制。
    feed = dict(feat_payload or {})
    feed.pop("ground_truth_for_acceptance", None)
    compact = json.dumps(feed, ensure_ascii=False)
    if len(compact) > 9000:
        compact = compact[:8600] + "...[truncated]"
    sys_b = ("下面是 STEP 的 B-Rep 特征树解析结果（已移除任何现成答案字段）。请输出且只输出一个 JSON 对象，"
             "字段固定为：solid_count, advanced_face_count, cylindrical_surface_count, "
             "conical_surface_count, toroidal_surface_count, plane_count, circle_count, "
             "assembly_component_count, product_count, cone_half_angles_deg, "
             "face_types_seen, reasoning。"
             "数值必须自己从 global_topology / solids 的统计中汇总，不要编造。"
             "reasoning 里请说明：这些面类型说明零件是什么成形方式、"
             "为什么有实体共用母线（分段模扇区）、孔与装配位姿如何识别。")
    msgs_b = [{"role": "system", "content": sys_b},
              {"role": "user", "content": "特征树数据：\n" + compact}]
    t0 = time.time()
    answer = None
    try:
        d = llm(msgs_b, fmt="json", npredict=900)
        raw = d.get("message", {}).get("content") or ""
        answer = extract_json(raw)
        print("PHASE_B raw", raw[:400].replace("\n", " "), flush=True)
    except Exception as e:
        print("PHASE_B ERR", type(e).__name__, str(e)[:120], flush=True)
    g = grade(answer)
    print("PHASE_B UNDERSTANDING_SCORE %s/%s = %s%%  PASS=%s" %
          (g["score"], g["total"], g["percent"], g["passed"]), flush=True)
    first_answer, first_grade, retest = answer, g, False
    if not g["passed"]:
        # 反馈复测：只指出「你只读了单个实体」，不给任何正确数值
        retest = True
        print("PHASE_B retest (hint: global vs per-solid, no answers given)", flush=True)
        try:
            msgs_b2 = msgs_b + [
                {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)[:1500]},
                {"role": "user", "content":
                    "你的若干面数量看起来只取了某一个 solid 的统计，而不是全文件汇总。"
                    "请重新阅读 global_topology.entity_type_counts 与 face_type_counts，"
                    "跨全部 solid 汇总后重新输出完整 JSON。不要编造数值。"}]
            d2 = llm(msgs_b2, fmt="json", npredict=900)
            answer = extract_json(d2.get("message", {}).get("content") or "")
            g = grade(answer)
            print("PHASE_B RETEST SCORE %s/%s = %s%% PASS=%s" %
                  (g["score"], g["total"], g["percent"], g["passed"]), flush=True)
        except Exception as e:
            print("PHASE_B RETEST ERR", type(e).__name__, str(e)[:100], flush=True)
    trace["phases"].append({"phase": "B_understanding", "latency_s": round(time.time() - t0, 2),
                            "first_answer": first_answer, "first_acceptance": first_grade,
                            "retest_used": retest, "model_json": answer, "acceptance": g})
    save()

    # ---------- Phase C: 模型自己推导建模方法 ----------
    sys_c = ("你已读过特征树。请自己决定最省特征、最快的建模/拼装/出图方法，"
             "输出且只输出一个 JSON 对象。\n"
             "【格式示例（仅示范 JSON 形状，里面的操作与本任务无关，禁止照抄）】\n"
             '{"method_reason":"为什么这样排序","expected_volume_mm3":null,'
             '"ops":[{"op":"new_part"},{"op":"verify"}]}\n'
             "【硬性格式要求】ops 的每个元素必须是 JSON **对象**，必须带 op 字段；"
             "不要写成字符串，不要写成函数调用文本。\n"
             "可用 op：new_part；sketch_profile(source=step_meridian 或 points=[[x,r],...])；"
             "revolve(angle_deg)；sketch_holes(pcd_mm,hole_dia_mm,count,angles_deg)；"
             "cut(type=through_all)；save_part(name)；import_assembly；save_assembly(name)；"
             "drawing(first_angle,isometric,name)；verify。"
             "特征顺序与参数全由你决定；执行器不会替你补步骤。"
             "expected_volume_mm3 要按母线尺寸估算量级，不要填随意小数。")
    ctx = ("你的理解验收结果：%s/%s (%s%%)。\n"
           "关键事实：%s\n"
           "母线测量点列在 cadcam_feature_ops(action=measure) 里，也可用 source=step_meridian 引用。"
           % (g["score"], g["total"], g["percent"], json.dumps(GT, ensure_ascii=False)))
    msgs_c = [{"role": "system", "content": sys_c}, {"role": "user", "content": ctx}]
    t0 = time.time()
    plan, first_plan, correction_used = None, None, False
    try:
        d = llm(msgs_c, fmt="json", npredict=1400)
        raw = d.get("message", {}).get("content") or ""
        plan = extract_json(raw)
        first_plan = plan
    except Exception as e:
        print("PHASE_C ERR", type(e).__name__, str(e)[:120], flush=True)

    def plan_valid(p):
        oo = (p or {}).get("ops") if isinstance(p, dict) else None
        return isinstance(oo, list) and len(oo) > 0 and all(
            isinstance(x, dict) and isinstance(x.get("op"), str) for x in oo)

    if not plan_valid(plan):
        # 只指出 JSON 格式问题并让它自己重写；不提示任何方法、参数或顺序
        correction_used = True
        print("PHASE_C format invalid -> ask model to re-emit (no engineering hint)", flush=True)
        try:
            msgs_c2 = msgs_c + [
                {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)[:1500]},
                {"role": "user", "content":
                    "格式不合格：ops 必须是 JSON 对象数组，每个元素形如 {\"op\":\"...\",\"参数\":值}，"
                    "不能是字符串。请重新输出完整 JSON。方法、顺序、参数仍全部由你自己决定。"}]
            d2 = llm(msgs_c2, fmt="json", npredict=1400)
            plan = extract_json(d2.get("message", {}).get("content") or "")
        except Exception as e:
            print("PHASE_C CORRECTION ERR", type(e).__name__, str(e)[:120], flush=True)

    # 无损语法规范化：模型用函数调用文本表达，转成等价 JSON；顺序与选择不变
    norm_notes = []
    if isinstance(plan, dict) and plan.get("ops"):
        norm_ops, norm_notes = normalize_ops(plan["ops"])
        plan = dict(plan)
        plan["ops"] = norm_ops
    print("PHASE_C ops(normalized)", [o.get("op") for o in ((plan or {}).get("ops") or [])
                                     if isinstance(o, dict)], flush=True)
    print("PHASE_C reason", (((plan or {}).get("method_reason")) or "")[:260], flush=True)
    print("PHASE_C normalization_notes", len(norm_notes), flush=True)
    ops = [o.get("op") for o in ((plan or {}).get("ops") or []) if isinstance(o, dict)]
    plan_check = {
        "has_revolve": "revolve" in ops,
        "has_cut": "cut" in ops,
        "has_sketch": "sketch_profile" in ops,
        "has_assembly": "import_assembly" in ops or "save_assembly" in ops,
        "has_drawing": "drawing" in ops,
        "op_count": len(ops),
        "expected_volume_mm3": (plan or {}).get("expected_volume_mm3"),
        "method_reason_present": bool((plan or {}).get("method_reason")),
    }
    trace["phases"].append({"phase": "C_method", "latency_s": round(time.time() - t0, 2),
                            "first_plan": first_plan, "correction_used": correction_used,
                            "normalization_notes": norm_notes,
                            "normalization_note": "仅语法转换，未增删或重排任何 op；未填参数由执行器公开默认值处理",
                            "model_plan": plan, "plan_valid": plan_valid(plan),
                            "plan_check": plan_check})
    save()

    # ---------- Phase D: 原样派发模型方案 ----------
    t0 = time.time()
    exec_res = None
    if plan and plan.get("ops"):
        try:
            exec_res = dispatch("cadcam_feature_ops", {
                "action": "execute_plan", "plan": plan,
                "step_path": STEP, "out_dir": OUT_DIR})
            print("PHASE_D status", exec_res.get("status"),
                  "final", exec_res.get("final_mass"), flush=True)
            for r in exec_res.get("ops_executed", []):
                print("   op%-2d %-18s ok=%s err=%s" %
                      (r["step"], r["op"], r.get("ok"), r.get("error", "")), flush=True)
        except Exception as e:
            exec_res = {"status": "error", "detail": type(e).__name__ + ": " + str(e)[:150]}
            print("PHASE_D ERR", str(exec_res)[:160], flush=True)
    else:
        exec_res = {"status": "skipped", "reason": "模型未输出可用 plan；监督者不代写方案"}
        print("PHASE_D SKIPPED (no model plan)", flush=True)
    trace["phases"].append({"phase": "D_execute_model_plan",
                            "latency_s": round(time.time() - t0, 2),
                            "execution": exec_res})
    save()

    # ---------- Phase E: 把真实失败证据回喂，让模型自己诊断并修正方案 ----------
    exec_rows = (exec_res or {}).get("ops_executed") or []
    failed = [r for r in exec_rows if r.get("ok") is False or r.get("error")]
    if failed:
        t0 = time.time()
        evidence = [{"step": r.get("step"), "op": r.get("op"), "ok": r.get("ok"),
                     "error": r.get("error"), "mass_after": r.get("mass_after"),
                     "file_saved": (r.get("file") or {}).get("saved")
                     if isinstance(r.get("file"), dict) else None}
                    for r in exec_rows]
        sys_e = ("你的方案已被逐步原样执行，下面是每一步的真实证据。"
                 "请自己诊断：哪一步没有达到预期、为什么、需要在它前面补什么。"
                 "然后输出修正后的**完整** JSON plan，字段为 method_reason / "
                 "expected_volume_mm3 / ops（对象数组，每元素带 op 字段）。"
                 "可用 op 与上一阶段相同：new_part, sketch_profile, revolve, sketch_holes, "
                 "cut, save_part, import_assembly, save_assembly, drawing, verify。"
                 "只输出 JSON 对象，不要输出解释文字。")
        usr_e = ("逐步执行证据：\n" + json.dumps(evidence, ensure_ascii=False) +
                 "\n你原来的 ops 顺序：" +
                 json.dumps([o.get("op") for o in ((plan or {}).get("ops") or [])],
                            ensure_ascii=False))
        fixed_plan, fix_err = None, None
        try:
            d = llm([{"role": "system", "content": sys_e},
                     {"role": "user", "content": usr_e}], fmt="json", npredict=1400)
            fixed_plan = extract_json(d.get("message", {}).get("content") or "")
        except Exception as e:
            fix_err = type(e).__name__ + ": " + str(e)[:120]
        norm2 = []
        if isinstance(fixed_plan, dict) and fixed_plan.get("ops"):
            fixed_plan["ops"], norm2 = normalize_ops(fixed_plan["ops"])
        fixed_ops = [o.get("op") for o in ((fixed_plan or {}).get("ops") or [])
                     if isinstance(o, dict)]
        print("PHASE_E self-repair ops", fixed_ops, flush=True)
        exec2 = None
        if fixed_ops:
            try:
                exec2 = dispatch("cadcam_feature_ops", {
                    "action": "execute_plan", "plan": fixed_plan,
                    "step_path": STEP, "out_dir": OUT_DIR})
                print("PHASE_E status", exec2.get("status"),
                      "final", exec2.get("final_mass"), flush=True)
                for r in exec2.get("ops_executed", []):
                    print("   op%-2d %-18s ok=%s V=%s" %
                          (r["step"], r["op"], r.get("ok"),
                           (r.get("mass_after") or {}).get("volume_mm3")), flush=True)
            except Exception as e:
                exec2 = {"status": "error", "detail": type(e).__name__ + ": " + str(e)[:150]}
        trace["phases"].append({
            "phase": "E_self_repair", "latency_s": round(time.time() - t0, 2),
            "evidence_fed_back": evidence, "model_fixed_plan": fixed_plan,
            "normalization_notes": norm2, "fix_error": fix_err,
            "execution": exec2})
        save()

    trace["elapsed_s"] = round(time.time() - trace["started"], 2)
    save()
    print("\nTRACE", TRACE, flush=True)
    print("SUMMARY understand=%s%% plan=%s exec=%s" %
          (g["percent"], plan_check, exec_res.get("status")), flush=True)


if __name__ == "__main__":
    main()
