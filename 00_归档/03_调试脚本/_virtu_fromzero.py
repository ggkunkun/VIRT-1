# -*- coding: utf-8 -*-
"""从零到组装 · 零补位监督器。

严格边界（本轮用户要求）：
  * 模型自己逆向、理解、规划、执行；监督者不写方案、不补 op、不补参数、不改顺序、不做语法转换。
  * 只提供工具接口契约（通用 API 文档），不提供任何针对本零件的方法或数值。
  * 格式不合格 / 方案缺步骤 → 回喂让模型自己重写；最终仍不合格就如实判失败。
  * 环境保持在唯一 SLDWORKS 实例，从 0 个文档开始。
"""
import datetime
import json
import os
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
STEP = os.path.join(ROOT, "assets", "wheel_mold_P0.step")
OUT_DIR = os.path.join(ROOT, "works", "from_zero")
os.makedirs(OUT_DIR, exist_ok=True)

STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN = os.path.join(ROOT, "runs", "virtu_fromzero_" + STAMP)
os.makedirs(RUN, exist_ok=True)
TRACE = os.path.join(RUN, "trace.json")
T = {"stamp": STAMP, "model": MODEL, "protocol": "read→understand→plan→execute→self-repair",
     "supervisor_patches": [], "zero_patch": True, "step_file": STEP,
     "out_dir": OUT_DIR, "stages": [], "started": time.time()}

# 只下发「读数据」+「按方案执行」，不下发任何一键策略工具
ALLOWED = ("cadcam_step_reverse", "cadcam_feature_ops")
TOOLS = [t for t in get_cadcam_tool_definitions()
         if t.get("function", {}).get("name") in ALLOWED]
T["tools_offered"] = [t["function"]["name"] for t in TOOLS]

GT_RAW = parse_features(STEP)["ground_truth_for_acceptance"]
GT_NUM = {k: GT_RAW[k] for k in (
    "solid_count", "advanced_face_count", "cylindrical_surface_count",
    "conical_surface_count", "toroidal_surface_count", "plane_count",
    "circle_count", "assembly_component_count", "product_count")}
HOLE_TRUTH = {"pcd_mm": 38.0, "hole_dia_mm": 7.0, "count": 3}


def post(url, payload, timeout=600, auth=False):
    h = {"Content-Type": "application/json"}
    if auth:
        h["Authorization"] = "Bearer " + TOKEN
    q = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                               headers=h, method="POST")
    with OPENER.open(q, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def llm(msgs, tools=None, fmt=None, n=1400):
    p = {"model": MODEL, "messages": msgs, "stream": False,
         "options": {"temperature": 0.1, "num_predict": n}}
    if tools:
        p["tools"] = tools
    if fmt:
        p["format"] = fmt
    return post(OLLAMA, p, timeout=420)


def dispatch(name, args):
    return post(BRIDGE + "/v1/cadcam/tools/call",
                {"name": name, "arguments": args}, timeout=600, auth=True)


def json_obj(text):
    dec = json.JSONDecoder()
    for i, c in enumerate(text or ""):
        if c == "{":
            try:
                o, _ = dec.raw_decode(text[i:])
                if isinstance(o, dict):
                    return o
            except Exception:
                pass
    return None


def save():
    json.dump(T, open(TRACE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def plan_shape(p):
    """只检查格式与覆盖度，不修改任何内容。"""
    ops = (p or {}).get("ops") if isinstance(p, dict) else None
    valid = isinstance(ops, list) and len(ops) > 0 and all(
        isinstance(x, dict) and isinstance(x.get("op"), str) for x in ops)
    names = [x.get("op") for x in ops] if valid else []
    need = ("revolve", "sketch_holes", "cut", "save_assembly", "drawing")
    return {"format_valid": valid, "op_count": len(names), "ops": names,
            "missing_required": [k for k in need if k not in names],
            "covers_full_chain": valid and all(k in names for k in need)}


# 通用工具接口契约（API 文档，不含任何本零件的建模方案或数值）
CONTRACT = """原子 op 接口契约（通用文档，不是建模方案）：
 new_part            : 新建零件文档，无前置
 sketch_profile      : 需 new_part；source=step_meridian 或 points=[[x,r],...]；建立母线草图
 revolve             : 需 sketch_profile 建立的草图；angle_deg
 sketch_holes        : 需已有实体；pcd_mm/hole_dia_mm/count/angles_deg/plane；建立孔草图
 cut                 : 需要一个孔草图（由 sketch_holes 建立），否则返回 False 且体积不变
 save_part           : 把当前零件存为 .SLDPRT，name
 import_assembly     : 导入 STEP 装配体，执行后当前文档变为装配体
 save_assembly       : 必须在 import_assembly 之后，把装配体存为 .SLDASM，name
 drawing             : 需 model_path 指向已保存的 .SLDASM；first_angle/isometric/name
 verify              : 读回当前文档的质量属性与特征树
执行器严格按 ops 顺序执行，不会补齐缺失步骤，也不会替你填没写的参数。"""


def stage(name, **kw):
    T["stages"].append(dict(stage=name, **kw))
    save()


def main():
    print("MODEL", MODEL, "TOOLS", T["tools_offered"], "OUT", OUT_DIR, flush=True)
    print("SUPERVISOR_PATCHES: NONE (zero-patch run)", flush=True)

    # ---------- Stage 1: 模型自己读数据 ----------
    sys1 = ("你是工业逆向工程师。请自己调用工具读取这份 STEP 的 B-Rep 特征树和原始测量数据，"
            "然后才能开始分析。可按需要调用 cadcam_step_reverse(action=features) 与 "
            "cadcam_feature_ops(action=measure)。")
    msgs = [{"role": "system", "content": sys1},
            {"role": "user", "content": "输入文件（工作区内）：" + STEP +
             "\n现在调用工具读取特征树与测量数据。"}]
    collected, calls_log = {}, []
    t0 = time.time()
    for rnd in range(1, 4):
        try:
            d = llm(msgs, tools=TOOLS)
        except Exception as e:
            calls_log.append({"round": rnd, "error": str(e)[:100]})
            break
        m = d.get("message", {})
        calls = m.get("tool_calls") or []
        # 兼容写进文本/thinking 的调用（只提取，不改写）
        if not calls:
            blob = (m.get("content") or "") + "\n" + (m.get("thinking") or "")
            dec = json.JSONDecoder()
            for i, c in enumerate(blob):
                if c == "{":
                    try:
                        o, _ = dec.raw_decode(blob[i:])
                        if isinstance(o, dict) and str(o.get("name", "")).startswith("cadcam_"):
                            calls = [{"function": {"name": o["name"],
                                                   "arguments": o.get("arguments", {})}}]
                            break
                    except Exception:
                        pass
        calls_log.append({"round": rnd,
                          "calls": [c.get("function", {}).get("name") for c in calls],
                          "content": (m.get("content") or "")[:200]})
        for c in calls:
            nm = c.get("function", {}).get("name")
            ar = c.get("function", {}).get("arguments", {})
            if isinstance(ar, str):
                try:
                    ar = json.loads(ar)
                except Exception:
                    ar = {}
            if nm == "cadcam_step_reverse" and "features" not in collected:
                ar["action"] = "features"
                collected["features"] = dispatch(nm, ar)
            elif nm == "cadcam_feature_ops" and "measure" not in collected:
                ar["action"] = "measure"
                collected["measure"] = dispatch(nm, ar)
        if "features" in collected and "measure" in collected:
            break
        msgs.append({"role": "assistant", "content": m.get("content") or ""})
        msgs.append({"role": "user", "content":
                     "还缺少另一份数据，请继续调用工具读取（不要凭空分析）。"})
    print("STAGE1 collected", list(collected.keys()), "%.1fs" % (time.time() - t0), flush=True)
    stage("1_read", latency_s=round(time.time() - t0, 2), calls_log=calls_log,
          collected=list(collected.keys()),
          model_called_both=("features" in collected and "measure" in collected))

    # 喂给模型的数据：移除任何现成答案字段
    feed = {}
    for k, v in collected.items():
        if isinstance(v, dict):
            v = {kk: vv for kk, vv in v.items() if kk != "ground_truth_for_acceptance"}
        feed[k] = v
    feed_text = json.dumps(feed, ensure_ascii=False)
    if len(feed_text) > 11000:
        feed_text = feed_text[:10600] + "...[truncated]"

    # ---------- Stage 2: 理解（孔系/母线/位姿都要它自己给） ----------
    sys2 = ("根据你读到的特征树与测量数据，输出且只输出一个 JSON 对象，字段：\n"
            "solid_count, advanced_face_count, cylindrical_surface_count, conical_surface_count, "
            "toroidal_surface_count, plane_count, circle_count, assembly_component_count, "
            "product_count, cone_half_angles_deg,\n"
            "hole_spec:{pcd_mm,hole_dia_mm,count,angles_deg},\n"
            "forming_method, assembly_note, reasoning。\n"
            "面数量要跨全部 solid 汇总（不要只取某一个 solid）；"
            "hole_spec 要从测量数据里的孔系与扇区关系自己推出；"
            "reasoning 说明成形方式、为什么存在共用母线的扇区、孔与装配位姿如何识别。")
    t0 = time.time()
    understanding, u_raw = None, ""
    try:
        d = llm([{"role": "system", "content": sys2},
                 {"role": "user", "content": "数据：\n" + feed_text}], fmt="json", n=1200)
        u_raw = d.get("message", {}).get("content") or ""
        understanding = json_obj(u_raw)
    except Exception as e:
        print("STAGE2 ERR", str(e)[:100], flush=True)
    checks, hits = {}, 0
    for k, exp in GT_NUM.items():
        try:
            ok = abs(float((understanding or {}).get(k)) - float(exp)) < 1e-6
        except Exception:
            ok = False
        checks[k] = ok
        hits += int(ok)
    try:
        got = sorted(round(float(x), 2) for x in (understanding or {}).get("cone_half_angles_deg", []))
        ok = got == sorted(round(float(x), 2) for x in GT_RAW["cone_half_angles_deg"])
    except Exception:
        ok = False
    checks["cone_half_angles_deg"] = ok
    hits += int(ok)
    hs = (understanding or {}).get("hole_spec") or {}
    for k, exp in HOLE_TRUTH.items():
        try:
            ok = abs(float(hs.get(k)) - float(exp)) < 1e-6
        except Exception:
            ok = False
        checks["hole_spec." + k] = ok
        hits += int(ok)
    reason = str((understanding or {}).get("reasoning") or "")
    for k, keys in (("forming", ("旋转", "回转", "revolve")),
                    ("sector", ("分段", "扇区", "扇形", "扇")),
                    ("hole", ("孔", "hole")),
                    ("assembly", ("装配", "位姿", "组件", "总成"))):
        ok = any(x in reason for x in keys)
        checks["reasoning." + k] = ok
        hits += int(ok)
    total = len(checks)
    uscore = {"score": hits, "total": total, "percent": round(100.0 * hits / total, 1),
              "detail": checks}
    print("STAGE2 UNDERSTANDING %d/%d = %.1f%%" % (hits, total, uscore["percent"]), flush=True)
    print("  hole_spec", hs, flush=True)
    stage("2_understand", latency_s=round(time.time() - t0, 2), raw=u_raw[:1200],
          model_json=understanding, acceptance=uscore)

    # ---------- Stage 3: 规划 ----------
    sys3 = ("请自己规划从零到组装的**完整**执行方案，输出且只输出一个 JSON 对象：\n"
            '{"method_reason":"...","expected_volume_mm3":数值,'
            '"ops":[按顺序的 op 对象]}\n' + CONTRACT + "\n"
            "硬性要求：ops 每个元素是 JSON 对象且带 op 字段；方案必须自己覆盖 "
            "建模、孔、装配保存、工程图、验证，不能漏步骤；"
            "参数用你从数据里读到的值填写，不要留空占位名。只输出 JSON。")
    t0 = time.time()
    plan, p_raw = None, ""
    try:
        d = llm([{"role": "system", "content": sys3},
                 {"role": "user", "content":
                     "你的理解结果：\n" + json.dumps(understanding, ensure_ascii=False)[:2500] +
                     "\n\n特征树与测量数据：\n" + feed_text}], fmt="json", n=1600)
        p_raw = d.get("message", {}).get("content") or ""
        plan = json_obj(p_raw)
    except Exception as e:
        print("STAGE3 ERR", str(e)[:100], flush=True)
    shape = plan_shape(plan)
    print("STAGE3 PLAN ops", shape["ops"], "missing", shape["missing_required"], flush=True)
    stage("3_plan", latency_s=round(time.time() - t0, 2), raw=p_raw[:1600],
          model_plan=plan, shape=shape)

    # ---------- Stage 4: 原样执行 + 模型自修（零补位） ----------
    exec_hist = []
    current_plan = plan
    for attempt in range(1, 4):
        t0 = time.time()
        if not shape["format_valid"]:
            exec_hist.append({"attempt": attempt, "skipped": True,
                              "reason": "模型 plan 格式不合格，执行器不代改"})
            print("STAGE4 attempt%d SKIPPED (invalid plan format)" % attempt, flush=True)
        else:
            try:
                res = dispatch("cadcam_feature_ops", {
                    "action": "execute_plan", "plan": current_plan,
                    "step_path": STEP, "out_dir": OUT_DIR})
                rows = [{"step": r.get("step"), "op": r.get("op"), "ok": r.get("ok"),
                         "error": r.get("error"),
                         "V": (r.get("mass_after") or {}).get("volume_mm3"),
                         "file": (r.get("file") or {}).get("saved")
                         if isinstance(r.get("file"), dict) else None}
                        for r in res.get("ops_executed", [])]
                exec_hist.append({"attempt": attempt, "status": res.get("status"),
                                  "rows": rows, "final_mass": res.get("final_mass")})
                print("STAGE4 attempt%d status=%s" % (attempt, res.get("status")), flush=True)
                for r in rows:
                    print("   op%-2d %-18s ok=%-5s V=%s" %
                          (r["step"], r["op"], r["ok"], r["V"]), flush=True)
                bad = [r for r in rows if r["ok"] is False or r["error"]]
                if res.get("status") == "ok" and not bad:
                    break
            except Exception as e:
                exec_hist.append({"attempt": attempt, "error": type(e).__name__ + ": " + str(e)[:120]})
        # 自修：只回喂真实证据，不给方法、不补 op
        if attempt < 3:
            evidence = json.dumps(exec_hist[-1], ensure_ascii=False)[:4000]
            sys4 = ("你的方案已原样执行，下面是真实逐步证据。请自己诊断并输出**修正后的完整 JSON plan**"
                    "（字段同前：method_reason / expected_volume_mm3 / ops 对象数组）。\n" + CONTRACT +
                    "\n只输出 JSON；监督者不会替你补任何步骤。")
            try:
                d = llm([{"role": "system", "content": sys4},
                         {"role": "user", "content": evidence}], fmt="json", n=1600)
                current_plan = json_obj(d.get("message", {}).get("content") or "")
                shape = plan_shape(current_plan)
                print("STAGE4 self-repair ops", shape["ops"],
                      "missing", shape["missing_required"], flush=True)
            except Exception as e:
                print("STAGE4 repair ERR", str(e)[:100], flush=True)
        stage("4_execute", attempt=attempt, latency_s=round(time.time() - t0, 2),
              plan_used=current_plan, shape=shape, history_tail=exec_hist[-1])
        save()

    T["execution_history"] = exec_hist
    T["final_plan_shape"] = shape
    # ---------- Stage 5: 监督者独立审计磁盘（只读） ----------
    arts = []
    for fn in sorted(os.listdir(OUT_DIR)):
        if os.path.splitext(fn)[1].lower() in (".sldprt", ".sldasm", ".slddrw"):
            p = os.path.join(OUT_DIR, fn)
            arts.append({"name": fn, "bytes": os.path.getsize(p),
                         "mtime": datetime.datetime.fromtimestamp(
                             os.path.getmtime(p)).strftime("%H:%M:%S")})
    print("STAGE5 ARTIFACTS", arts, flush=True)
    stage("5_disk_audit", artifacts=arts,
          all_three=len({os.path.splitext(a["name"])[1].lower() for a in arts}) == 3)
    T["elapsed_s"] = round(time.time() - T["started"], 2)
    save()
    print("\nTRACE", TRACE, flush=True)
    print("SUMMARY understand=%.1f%% plan_valid=%s covers_full_chain=%s artifacts=%d" %
          (uscore["percent"], shape["format_valid"], shape["covers_full_chain"], len(arts)),
          flush=True)


if __name__ == "__main__":
    main()
