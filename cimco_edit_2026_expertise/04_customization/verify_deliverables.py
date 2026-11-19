"""验证阶段4全部开发成果（3后处理 + 2宏脚本）的结构合法性与可运行性。"""
import os, sys, re, json, subprocess, tempfile, time
BASE = r"D:\Virtu模型\cimco_edit_2026_expertise\04_customization"
PP = os.path.join(BASE, "post_processors")
MAC = os.path.join(BASE, "macros")
results = []

# --- 后处理 JS 结构验证：对照官方 fanuc.js 的必需契约 ---
REQUIRED_TOKENS = ["globals", "PostInfo", "propertyNames", "function onOpen", "function onClose",
                   "function onComment", "function onLinear", "function onToolChange",
                   "function onDrillingHeader", "function onDrillingPoint", "function onDrillingFooter",
                   "function getParameter", "function setParameter"]
# 派生件与其官方基线的配对：校验原则是"派生件的函数集必须与基线一致，且元数据已改为定制值"
PP_PAIRS = [
    ("PP_CASE1_Fanuc_NOK_Increment.js", "_base_fanuc_reference.js"),
    ("PP_CASE2_Huazhong_ISO_Generic.js", "_base_fanuc_reference.js"),
    ("PP_CASE3_Heidenhain_Metric_Finish.js", "_base_heidenhain_reference.js"),
]
def funcs(txt):
    return sorted(set(re.findall(r'^function\s+([A-Za-z_0-9]+)', txt, re.M)))
for f, base in PP_PAIRS:
    p = os.path.join(PP, f)
    txt = open(p, encoding="utf-8", errors="ignore").read()
    btxt = open(os.path.join(PP, base), encoding="utf-8", errors="ignore").read()
    base_funcs = funcs(btxt)
    # 通用契约：globals/PostInfo/propertyNames + 至少一个 onDrilling 回调 + get/setParameter
    generic = ["globals", "PostInfo", "propertyNames", "function onDrillingHeader",
               "function onDrillingPoint", "function onDrillingFooter",
               "function getParameter", "function setParameter"]
    missing = [t for t in generic if t not in txt]
    # 关键：派生件函数集必须与官方基线完全一致（证明派生干净、未误删回调）
    fset_diff = sorted(set(base_funcs) - set(funcs(txt)))
    meta = {}
    for k in ["title", "version", "description", "author", "type"]:
        m = re.search(k + r'\s*:\s*"([^"]*)"', txt) or re.search(k + r'\s*:\s*(\w+)', txt)
        meta[k] = m.group(1) if m else None
    customized = "(Custom)" in (meta.get("title") or "") or "(B-03" in (meta.get("title") or "")
    brace_bal = txt.count("{") - txt.count("}")
    ok = (not missing) and not fset_diff and customized and all(meta[k] for k in ["title", "version", "description"]) and abs(brace_bal) <= 2
    results.append({"type": "post_processor", "file": f, "base": base, "bytes": len(txt),
                    "missing_generic": missing, "funcs_lost_vs_base": fset_diff,
                    "func_count": len(funcs(txt)), "meta": meta, "brace_balance": brace_bal,
                    "status": "PASS" if ok else "FAIL"})
    print(f"[PP] {f}: {'PASS' if ok else 'FAIL'} missing={missing} funcs_lost={fset_diff} meta_title={meta.get('title')}")

# --- 派生修改核验：读取 _derive_report.json 确认每处修改都 applied ---
try:
    dr = json.load(open(os.path.join(PP, "_derive_report.json"), encoding="utf-8"))
    not_applied = []
    for case, edits in dr["cases"].items():
        not_applied += [f"{case}:{e}" for e in edits if e.startswith("!!NOT_APPLIED")]
    results.append({"type": "derive_report", "status": "PASS" if not not_applied else "FAIL",
                    "not_applied": not_applied})
    print(f"[DERIVE] not_applied={not_applied} -> {'PASS' if not not_applied else 'FAIL'}")
except Exception as e:
    results.append({"type": "derive_report", "status": "FAIL", "error": str(e)})

# --- 宏脚本可运行性验证 ---
# 宏1：造两个 NC（一好一坏）跑批量校验
with tempfile.TemporaryDirectory() as td:
    good = "%\nO1000\nG90 G54 G21\nM03 S1000\nG01 X10 F100\nM05\nM30\n%"
    bad = "%\nO1001\nG90 G54 G21\nM03 S1000\nWHILE [#100 GT 0] DO1\nG01 X10 F100\nM30\n%"
    open(os.path.join(td, "good.nc"), "w").write(good)
    open(os.path.join(td, "bad.nc"), "w").write(bad)
    out = os.path.join(BASE, "macros", "_verify_batch_report.json")
    r = subprocess.run([sys.executable, os.path.join(MAC, "macro1_batch_validate.py"),
                        "--dir", td, "--out", out], capture_output=True, text=True, timeout=90)
    ok = r.returncode == 0 and os.path.exists(out)
    rep = json.load(open(out, encoding="utf-8")) if ok else {}
    verdicts = {os.path.basename(x["file"]): x.get("verdict") for x in rep.get("rows", [])}
    m1ok = ok and verdicts.get("good.nc") == "PASS" and verdicts.get("bad.nc") == "FAIL"
    results.append({"type": "macro1_batch_validate", "status": "PASS" if m1ok else "FAIL",
                    "returncode": r.returncode, "verdicts": verdicts, "stdout": r.stdout.strip(),
                    "stderr": r.stderr.strip()[:300]})
    print(f"[MACRO1] {r.stdout.strip()} verdicts={verdicts} -> {'PASS' if m1ok else 'FAIL'}")

# 宏2：重编号功能验证
with tempfile.TemporaryDirectory() as td:
    src = os.path.join(td, "r.nc")
    open(src, "w").write("%\nO2000\nG90 G54 G21\nG01 X10 F100\nG01 Y20\nM30\n%")
    dst = os.path.join(td, "r_out.nc")
    rep2 = os.path.join(BASE, "macros", "_verify_renum_report.json")
    r = subprocess.run([sys.executable, os.path.join(MAC, "macro2_renumber_format.py"),
                        "--input", src, "--out", dst, "--start", "100", "--step", "10",
                        "--report", rep2], capture_output=True, text=True, timeout=60)
    content = open(dst, encoding="utf-8").read() if os.path.exists(dst) else ""
    lines = [l for l in content.splitlines() if l.strip()]
    renum_ok = len(lines) >= 6 and lines[2].startswith("N100") and lines[3].startswith("N110")
    results.append({"type": "macro2_renumber_format", "status": "PASS" if (r.returncode == 0 and renum_ok) else "FAIL",
                    "returncode": r.returncode, "sample_lines": lines[2:5],
                    "stdout": r.stdout.strip(), "stderr": r.stderr.strip()[:300]})
    print(f"[MACRO2] {r.stdout.strip()} lines={lines[2:5]} -> {'PASS' if renum_ok else 'FAIL'}")

summary = {"run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "total": len(results), "passed": sum(1 for r in results if r.get("status") == "PASS"),
           "all_pass": all(r.get("status") == "PASS" for r in results), "results": results}
json.dump(summary, open(os.path.join(BASE, "verification_report.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("=" * 60)
print(f"SUMMARY: {summary['passed']}/{summary['total']} PASS all_pass={summary['all_pass']}")
sys.exit(0 if summary["all_pass"] else 1)
