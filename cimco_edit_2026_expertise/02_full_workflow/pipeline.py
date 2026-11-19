"""CIMCO Edit 2026 标准化全流程工程验证管线 (Standard Workflow Verification Pipeline).

这是"阶段2 全流程操作熟练度"的可核验工程化实现：
把 导入→编辑校验→工艺配置→仿真验证→合格输出 固化为确定性管线，
连续运行 N 次，每一步都产生带时间戳的日志与判定，任何步骤失败即判该次 FAIL。

诚实声明（见 00_sources/CAPABILITY_BOUNDARIES.md B-06）：
- 这是"工程化等价验证"，不是人工 GUI 点击 20 次，也不是真人计时。
- "仿真验证"= 本地静态 G00 哨兵 + 语法校验（cimco_bridge），非机床仿真 add-on 真实碰撞。
- 运行: python pipeline.py --runs 10
"""
import sys, os, json, time, hashlib, argparse, re
sys.path.insert(0, r"D:\Virtu模型")
from bridges.cimco_bridge import CIMCOBridge

ROOT = r"D:\Virtu模型\cimco_edit_2026_expertise\02_full_workflow"
LOGDIR = os.path.join(ROOT, "logs")
os.makedirs(LOGDIR, exist_ok=True)

# ---- 全流程的标准化测试输入：覆盖合规件与多种故障件 ----
GOOD_PROGRAM = """%
O1100 (BZJ-A-01 LAYER MILL)
G90 G54 G17 G40 G49 G80 G21
T01 M06
M03 S2400
G43 H01 Z50.0 M08
#100=400.00 (LENGTH_X)
#101=300.00 (WIDTH_Y)
#102=-20.00 (TARGET_Z)
#103=2.00 (AP_STEP)
#104=0.0 (CURRENT_Z)
G00 X0.0 Y0.0
G00 Z5.0
WHILE [#104 GT #102] DO1
#104=#104-#103
IF [#104 LT #102] THEN #104=#102
G01 Z#104 F180.
G01 X#100 F650.
G01 Y#101
G01 X0.0
G01 Y0.0
END1
G00 Z50.0 M09
G91 G28 Z0.
G49
M05
M30
%"""

# 各阶段故障注入样本：用于证明管线能拦截错误（负面测试）
FAULT_CASES = {
    "unclosed_loop": GOOD_PROGRAM.replace("END1\n", ""),
    "no_m05": GOOD_PROGRAM.replace("M05\n", ""),
    "no_m30": GOOD_PROGRAM.replace("M30\n", ""),
    # 桥接器 G/M 合法范围为 0~999；G999 仍在范围内，故用 G1005 制造明确越界
    "bad_gcode": GOOD_PROGRAM.replace("G01 Z#104 F180.", "G1005 Z#104 F180."),
}

def sha(txt):
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]

def ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def g00_plunge_check(nc_text, stock_top_z=0.0, safe_clearance=1.0):
    """静态 G00 扎料哨兵（项目公理 §2.E）：提取 G00 段的 Z 终点，判断是否扎入毛坯。
    这是几何静态哨兵，不等同机床仿真真实碰撞检测。"""
    alerts = []
    cur_z = None
    for i, line in enumerate(nc_text.splitlines(), 1):
        s = re.sub(r"\([^)]*\)", "", line).strip().upper()
        if not s or s.startswith("%") or s.startswith("O"):
            continue
        m = re.search(r"G00\b", s)
        if not m:
            # 跟踪模态坐标（简化：任意含 Z 的行的最后一个 Z 值）
            zs = re.findall(r"Z(-?\d+(?:\.\d+)?)", s)
            if zs:
                cur_z = float(zs[-1])
            continue
        zs = re.findall(r"Z(-?\d+(?:\.\d+)?)", s)
        if zs:
            target_z = float(zs[-1])
            if target_z < stock_top_z - safe_clearance:
                alerts.append({"line": i, "target_z": target_z, "stock_top_z": stock_top_z,
                               "msg": f"L{i}: G00 rapid to Z{target_z} plunges into stock (top Z{stock_top_z})"})
            cur_z = target_z
    return alerts

class Step:
    def __init__(self, name, fn):
        self.name, self.fn = name, fn

def run_once(run_id, bridge, program):
    """执行单次全流程，返回 (passed, 步骤记录列表)。"""
    rec = []
    ctx = {"raw": program, "run_id": run_id}

    def s1_import(ctx):
        # 阶段1：多格式导入（此处以 ISO G-code 文本为规范化入口；文件级导入用临时 .nc 落盘）
        assert isinstance(ctx["raw"], str) and len(ctx["raw"]) > 50, "空程序"
        ctx["norm"] = ctx["raw"].replace("\r\n", "\n").strip()
        assert ctx["norm"].startswith("%"), "缺少 ISO 程序起始符 %"
        return {"bytes": len(ctx["norm"]), "sha16": sha(ctx["norm"]), "format": "ISO_G-Code"}

    def s2_edit_validate(ctx):
        # 阶段2：程序编辑与校验（FANUC Macro B + 语法哨兵）
        r = bridge.validate_fanuc_macro_b(ctx["norm"])
        ctx["validate"] = r
        assert r["status"] == "success", f"校验器状态异常:{r['status']} {r.get('syntax_check_error')}"
        assert r["syntax_checked"] is True, "语法哨兵未运行(CHECK_UNAVAILABLE)，不得判通过"
        assert r["is_valid"] is True, f"校验失败:{r['errors']}"
        # 安全类 error 即使被桥接器判为非 critical，也必须在全流程门处拦截：
        # 实测发现桥接器把"主轴未停""G/M超范围"仅列入 errors 而 is_valid 仍 True。
        # 作为"合格程序输出"门，任何安全/语法 error 都不放行。
        safety_errs = [e for e in r["errors"] if not e.startswith("CHECK_UNAVAILABLE")]
        assert not safety_errs, f"存在安全/语法错误，禁止放行:{safety_errs}"
        return {"status": r["status"], "is_valid": r["is_valid"], "syntax_checked": r["syntax_checked"],
                "vars": r["variables"], "lines": r["line_count"], "errors": r["errors"]}

    def s3_process_config(ctx):
        # 阶段3：工艺参数配置（从程序提取宏观工艺参数，核对完整性）
        txt = ctx["norm"]
        cfg = {
            "units": "mm(G21)" if "G21" in txt else ("inch(G20)" if "G20" in txt else "UNSPECIFIED"),
            "work_offset": "G54" if "G54" in txt else "UNSPECIFIED",
            "length_comp": bool(re.search(r"G43\s+H\d+", txt)),
            "spindle": bool(re.search(r"M0?3\s+S\d+", txt)),
            "coolant": bool(re.search(r"M0[78]", txt)),
            "macro_layers": len(re.findall(r"WHILE\b", txt)),
            "program_end": bool(re.search(r"M0?[23]0", txt)),
        }
        missing = [k for k in ["length_comp", "spindle", "program_end"] if not cfg[k]]
        assert cfg["units"] == "mm(G21)", f"单位非 mm: {cfg['units']}"
        assert not missing, f"工艺参数缺失:{missing}"
        ctx["process_cfg"] = cfg
        return cfg

    def s4_sim_verify(ctx):
        # 阶段4：仿真验证（静态 G00 扎料哨兵 + 背绘前置条件检查）
        alerts = g00_plunge_check(ctx["norm"])
        ctx["g00_alerts"] = alerts
        assert not alerts, f"G00 扎料哨兵报警:{alerts}"
        # 背绘所需 Control Type 可判定（G 代码族）
        ctrl = "FANUC(ISO_G-Code)" if "#" in ctx["norm"] or "WHILE" in ctx["norm"] else "ISO_G-Code"
        ctx["control_type"] = ctrl
        return {"g00_alerts": len(alerts), "control_type": ctrl,
                "note": "静态哨兵；机床仿真 add-on 未验证(B-01)"}

    def s5_export(ctx):
        # 阶段5：合格程序输出（生成交付件与清单）
        out_name = f"O1100_run{run_id:02d}.nc"
        out_path = os.path.join(LOGDIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(ctx["norm"])
        manifest = {
            "output_file": out_name,
            "sha16": sha(ctx["norm"]),
            "verdict": "PASS",
            "validate_ref": {k: ctx["validate"][k] for k in ["status", "is_valid", "syntax_checked"]},
            "g00_alerts": len(ctx["g00_alerts"]),
            "control_type": ctx["control_type"],
        }
        ctx["manifest"] = manifest
        return manifest

    steps = [Step("S1_导入与规范化", s1_import), Step("S2_编辑与校验", s2_edit_validate),
             Step("S3_工艺参数配置", s3_process_config), Step("S4_仿真验证", s4_sim_verify),
             Step("S5_合格输出", s5_export)]
    passed = True
    for st in steps:
        t0 = time.perf_counter()
        try:
            detail = st.fn(ctx)
            rec.append({"step": st.name, "status": "PASS", "ms": round((time.perf_counter()-t0)*1000, 2),
                        "detail": detail})
        except Exception as e:
            rec.append({"step": st.name, "status": "FAIL", "ms": round((time.perf_counter()-t0)*1000, 2),
                        "error": str(e)})
            passed = False
            break
    return passed, rec

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()
    bridge = CIMCOBridge()
    t_start = time.time()
    results = []
    for i in range(1, args.runs + 1):
        ok, rec = run_once(i, bridge, GOOD_PROGRAM)
        results.append({"run": i, "ts": ts(), "result": "PASS" if ok else "FAIL", "steps": rec})
        print(f"RUN {i:02d}: {'PASS' if ok else 'FAIL'}  steps={len(rec)}")
    # 负面测试：证明管线能拦截故障（不是只会说 PASS）
    neg = {}
    for name, code in FAULT_CASES.items():
        ok, rec = run_once(99, bridge, code)  # run_id 99 仅为测试，不落同名交付件
        fail_step = next((r["step"] for r in rec if r["status"] == "FAIL"), None)
        neg[name] = {"blocked": not ok, "failed_at": fail_step,
                     "reason": next((r.get("error") for r in rec if r["status"] == "FAIL"), None)}
        print(f"NEG {name}: {'BLOCKED' if not ok else 'MISSED'} at {fail_step}")
    elapsed = time.time() - t_start
    pass_count = sum(1 for r in results if r["result"] == "PASS")
    summary = {
        "pipeline": "CIMCO Edit 2026 Standard Full Workflow v1.0",
        "run_at": ts(),
        "runs": args.runs,
        "pass_count": pass_count,
        "fail_count": args.runs - pass_count,
        "zero_step_fault": pass_count == args.runs,
        "total_wall_seconds": round(elapsed, 2),
        "avg_wall_seconds_per_run": round(elapsed / args.runs, 3),
        "negative_tests": neg,
        "negative_all_blocked": all(v["blocked"] for v in neg.values()),
        "honest_note": "工程化静态验证，非人工GUI实操/非真人计时/非机床仿真add-on(B-06,B-01)",
        "results": results,
    }
    logpath = os.path.join(LOGDIR, f"workflow_run_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(logpath, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("=" * 60)
    print(f"SUMMARY: {pass_count}/{args.runs} PASS | zero_step_fault={summary['zero_step_fault']} | "
          f"negative_all_blocked={summary['negative_all_blocked']}")
    print(f"LOG: {logpath}")
    return 0 if (summary["zero_step_fault"] and summary["negative_all_blocked"]) else 1

if __name__ == "__main__":
    sys.exit(main())
