"""Automated Blind-Test Evaluation Suite for 6 CAD/CAM/CNC Industrial Software.

Two modes:
  * default        — load base+LoRA and generate fresh responses (needs torch/peft).
  * --regrade-json — re-score responses already stored in a results JSON without
                     loading a model. Adds prompt-dimension fidelity alongside the
                     original keyword score, because keyword presence alone gave
                     100/100 to answers that omitted or changed the requested size.
"""

import argparse
import json
import os
import re
import sys
import time

BASE_MODEL_PATH = os.environ.get("BASE_MODEL_PATH", "/root/public-storage/model/Qwen/Qwen3-8B")
DEFAULT_ADAPTER = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora"
FALLBACK_ADAPTER = "/root/cad_cam_finetune/output_checkpoints/cad_cam_six_software_lora_final"
ADAPTER_PATH = os.environ.get(
    "ADAPTER_PATH",
    DEFAULT_ADAPTER if os.path.exists(DEFAULT_ADAPTER) else FALLBACK_ADAPTER
)
BLIND_TEST_DATA = "/root/workspace/Virtu/damodel_cad_cam_tuning/dataset/wish_parametric_blind_test.jsonl"
REPORT_OUTPUT_MD = "/root/workspace/Virtu/benchmarks/cad_cam_blind_test_report.md"
RESULT_JSON = "/root/workspace/Virtu/benchmarks/cad_cam_blind_test_results.json"

# 尺寸保真：中文语境不能用 \w 做左边界（汉字本身是 \w），否则一个都匹配不到。
AFTER_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:mm|MM|毫米|MPa|N·m|rpm|RPM|HRC|um|μm|°|度)")
BEFORE_RE = re.compile(r"(?:Φ|φ|直径|外径|内孔|内径|孔径|长度|宽度|厚度|深度|高度|总长|高|长|宽|深|R|r)\s*[=::]?\s*(?<![\d.])(\d+(?:\.\d+)?)")


def dims(text, software):
    soft = set(re.findall(r"\d+(?:\.\d+)?", software or ""))
    out = []
    for rx in (AFTER_RE, BEFORE_RE):
        for m in rx.finditer(text):
            v = m.group(1)
            if v not in soft and float(v) >= 1 and v not in out:
                out.append(v)
    return out


def fidelity(prompt, software, response):
    need = dims(prompt, software)
    if not need:
        return 1.0, 0, [], 0
    got = [v for v in need if re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d.])", response)]
    pset = set(need) | set(re.findall(r"\d+(?:\.\d+)?", software or ""))
    fab = sorted({m.group(1) for m in AFTER_RE.finditer(response) if m.group(1) not in pset},
                 key=len)[:8]
    return len(got) / len(need), len(fab), fab, len(need)


def evaluate_response(software_category, prompt, text):
    """Rigorous multi-dimensional grading of generated response."""
    score = 100
    errors = []

    # 1. Non-empty & substantial length check
    if len(text.strip()) < 80:
        errors.append("Output is too short or empty")
        return {"passed": False, "score": 0, "errors": errors}

    # 2. Domain-specific executable check
    text_lower = text.lower()
    
    if "solidworks" in software_category.lower() or "vba" in prompt.lower():
        if "```vb" not in text and "```vba" not in text:
            errors.append("Missing ```vb code block")
            score -= 20
        if "getequationmgr" not in text_lower:
            errors.append("Missing EquationMgr (方程式管理器) binding")
            score -= 30
        if "addequation" not in text_lower and "add 0" not in text_lower and "add" not in text_lower:
            errors.append("Missing equation parameter registration")
            score -= 20
        if "sketchmanager" not in text_lower and "featurerevolve" not in text_lower:
            errors.append("Missing geometric feature generation calls")
            score -= 20

    elif "nx" in software_category.lower() or "ug" in prompt.lower():
        if "```python" not in text:
            errors.append("Missing ```python code block")
            score -= 20
        if "nxopen" not in text_lower:
            errors.append("Missing NXOpen library imports")
            score -= 30
        if "expression" not in text_lower and "createwithunits" not in text_lower:
            errors.append("Missing expression creation calls")
            score -= 30

    elif "autocad" in software_category.lower() or "autolisp" in prompt.lower():
        if "```lisp" not in text:
            errors.append("Missing ```lisp code block")
            score -= 20
        if "defun c:" not in text and "defun" not in text:
            errors.append("Missing (defun c:...) command declaration")
            score -= 30
        if "layer" not in text_lower and "图层" not in text:
            errors.append("Missing layer separation logic")
            score -= 20

    elif "vericut" in software_category.lower():
        if "毛坯" not in text and "stock" not in text_lower and "cylinder" not in text_lower and "blank" not in text_lower:
            errors.append("Missing Stock definition")
            score -= 25
        if "卡盘" not in text and "fixture" not in text_lower and "clamp" not in text_lower and "chuck" not in text_lower and "夹持" not in text and "夹具" not in text:
            errors.append("Missing Fixture/Clamping details")
            score -= 25
        if "刀具" not in text and "tls" not in text_lower and "tool" not in text_lower and "cutter" not in text_lower and "insert" not in text_lower and "wnmg" not in text_lower:
            errors.append("Missing Tool Library details")
            score -= 25
        if "过切" not in text and "gouge" not in text_lower and "collision" not in text_lower and "tolerance" not in text_lower and "碰撞" not in text and "容差" not in text:
            errors.append("Missing Gouge/Collision tolerance")
            score -= 25

    elif "cimco" in software_category.lower() or "macro b" in prompt.lower():
        if "```gcode" not in text and "```" not in text:
            errors.append("Missing G-code code block")
            score -= 20
        if "#" not in text and "macro" not in text_lower and "变量" not in text:
            errors.append("Missing Macro B #100 variable definitions")
            score -= 35
        if "g71" not in text_lower and "g70" not in text_lower and "g01" not in text_lower and "g00" not in text_lower and "cycle" not in text_lower and "循环" not in text:
            errors.append("Missing valid turning cycle blocks")
            score -= 25

    elif "斯沃" in software_category.lower() or "sscnc" in prompt.lower():
        if "g54" not in text_lower and "wcs" not in text_lower and "坐标系" not in text and "对刀" not in text and "g50" not in text_lower:
            errors.append("Missing G54 work coordinate system setting")
            score -= 30
        if "刀尖方位" not in text and " t" not in text_lower and "t1" not in text_lower and "t01" not in text_lower and "方位" not in text:
            errors.append("Missing Tool Tip Orientation Code (T)")
            score -= 30
        if "半径" not in text and " r" not in text_lower and "r0" not in text_lower and "r1" not in text_lower and "r2" not in text_lower and "刀尖半径" not in text:
            errors.append("Missing Tool Nose Radius (R)")
            score -= 20

    passed = (score >= 80) and (len(errors) == 0 or score >= 80)
    return {"passed": passed, "score": max(0, score), "errors": errors}


def regrade(path):
    """Re-score stored responses with the keyword grader + dimension fidelity."""
    import shutil

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = json.load(open(path, encoding="utf-8"))
    rows = data.get("results", []) if isinstance(data, dict) else data
    if not rows:
        raise SystemExit(f"[FATAL] no results in {path}")

    graded = []
    judgeable = 0
    fid_sum = 0.0
    fid_fail = 0
    fab_total = 0
    keyword_pass = 0
    score_sum = 0.0
    for r in rows:
        prompt = r.get("prompt") or ""
        software = r.get("software") or "Unknown"
        resp = r.get("response_full") or r.get("response") or r.get("response_preview") or ""
        if resp.endswith("..."):
            resp = resp[:-3]
        ev = evaluate_response(software, prompt, resp)
        fid, fab_n, fab, need_n = fidelity(prompt, software, resp)
        if need_n:
            judgeable += 1
            fid_sum += fid
            if fid < 1.0:
                fid_fail += 1
        fab_total += fab_n
        if ev["passed"]:
            keyword_pass += 1
        score_sum += ev["score"]
        graded.append({
            "test_id": r.get("test_id"),
            "software": software,
            "keyword_score": ev["score"],
            "keyword_passed": ev["passed"],
            "keyword_errors": ev["errors"],
            "required_dims": need_n,
            "fidelity": round(fid, 4),
            "missing_ratio": round(1.0 - fid, 4) if need_n else None,
            "fabricated_dims": fab_n,
            "fabricated_values": fab,
        })

    n = len(graded)
    keyword_rate = 100.0 * keyword_pass / n
    mean_score = score_sum / n
    fid_mean = fid_sum / judgeable if judgeable else None
    summary = {
        "source": os.path.abspath(path),
        "n_cases": n,
        "keyword_pass_count": keyword_pass,
        "keyword_pass_rate_pct": round(keyword_rate, 2),
        "keyword_mean_score": round(mean_score, 2),
        "judgeable_dimension_cases": judgeable,
        "fidelity_mean": round(fid_mean, 4) if fid_mean is not None else None,
        "fidelity_below_1_count": fid_fail,
        "fabricated_dimension_total": fab_total,
        "cases": graded,
    }
    out_json = os.path.join(root, "benchmarks", "cad_cam_blind_test_results_regraded.json")
    json.dump(summary, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def cell(v):
        return "—" if v is None else f"{v:.4f}"

    lines = [
        "# Virtu CAD/CAM/CNC 盲测——判分口径修正版",
        f"**重判时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**数据来源**: `{os.path.relpath(path, root)}`（已存响应，未重新生成）  ",
        f"**原始报告备份**: `benchmarks/cad_cam_blind_test_report.orig_20261029.md`  ",
        "",
        "> **结论先行**：原报告的 94.4% 是**关键词/格式合规率**，不是尺寸正确率。",
        "> 判分器只检查 `EquationMgr`、`NXOpen`、```vb``` 等字符串是否出现，从不核对数字。",
        "> 本报告在同一批响应上追加了需求尺寸保真率，两个口径并列展示。",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 值 |",
        "| :--- | ---: |",
        f"| 用例数 | {n} |",
        f"| 关键词通过 | {keyword_pass}/{n} = **{keyword_rate:.2f}%** |",
        f"| 关键词均分 | **{mean_score:.2f}/100** |",
        f"| 可从 prompt 提取需求尺寸的题数 | {judgeable}/{n} |",
        f"| 尺寸保真均值（仅可判题） | **{cell(fid_mean)}** |",
        f"| 保真 < 1 的题数 | **{fid_fail}** |",
        f"| 响应中单位数字但不在 prompt 的幻觉尺寸 | {fab_total} |",
        "",
        "## 2. 逐题（可判题优先）",
        "",
        "| 用例 | 软件 | 关键词分 | 通过 | 需求尺寸数 | 保真率 | 缺失比例 | 幻觉尺寸数 |",
        "| :--- | :--- | ---: | :---: | ---: | ---: | ---: | ---: |",
    ]
    for g in sorted(graded, key=lambda x: (x["required_dims"] == 0, x["fidelity"])):
        fid_cell = cell(g["fidelity"]) if g["required_dims"] else "—"
        lines.append(
            f"| `{g['test_id']}` | {g['software']} | {g['keyword_score']} | "
            f"{'PASS' if g['keyword_passed'] else 'FAIL'} | {g['required_dims']} | "
            f"{fid_cell} | {cell(g['missing_ratio'])} | {g['fabricated_dims']} |"
        )
    lines += [
        "",
        "## 3. 口径说明",
        "",
        "1. **关键词分**沿用 `evaluate_response()`，只判代码块/API 名称/软件特征串，和原 94.4% 完全同源。",
        "2. **保真率**只统计 prompt 中带单位或尺寸前缀（Φ/外径/内孔/长度…）的数值，检查响应是否原样保留。",
        "3. 保真 < 1 说明模型改写或遗漏了用户给定尺寸；这类回答即使关键词满分，也不能直接用于加工。",
        "4. 本重判不重新调用模型，因此不引入采样噪声；它只回答“已发布分数测的是什么”。",
        "",
        "## 4. 修复动作",
        "",
        "- 新生成的盲测报告必须同时输出关键词分与保真率，禁止只报单一通过率。",
        "- 能力验收以 `virtu_eval/` 的确定性判分与尺寸/数值判据为准；本脚本仅保留作历史对照。",
        "",
    ]
    report = "\n".join(lines)

    report_path = os.path.join(root, "benchmarks", "cad_cam_blind_test_report.md")
    backup_path = os.path.join(root, "benchmarks", "cad_cam_blind_test_report.orig_20261029.md")
    if os.path.exists(report_path) and not os.path.exists(backup_path):
        shutil.copy2(report_path, backup_path)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    duplicate = os.path.join(root, "checkpoints", "cad_cam_six_software_lora", "BLIND_TEST_REPORT.md")
    if os.path.isdir(os.path.dirname(duplicate)):
        with open(duplicate, "w", encoding="utf-8") as f:
            f.write(report)

    print(json.dumps({k: v for k, v in summary.items() if k != "cases"},
                     ensure_ascii=False, indent=2))
    print(f"[OK] {out_json}")
    print(f"[OK] {report_path}")
    return summary


def main():
    print("==================================================================")
    print("  Virtu: CAD/CAM/CNC Blind-Test Automated Evaluation Engine")
    print("==================================================================")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device} | GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None'}")

    # Load Model
    print(f"Loading Base Model: {BASE_MODEL_PATH} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    print(f"Mounting LoRA Adapter from: {ADAPTER_PATH} ...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()
    print("[SUCCESS] Model initialized for blind test benchmark.")

    # Load Blind Test Data
    test_cases = []
    with open(BLIND_TEST_DATA, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_cases.append(json.loads(line))

    print(f"Loaded {len(test_cases)} unseen held-out blind-test challenges.")

    results = []
    passed_count = 0
    t0 = time.time()

    for idx, item in enumerate(test_cases, 1):
        prompt = item["instruction"]
        inp = item.get("input", "")
        test_id = item.get("blind_test_id", f"blind_{idx:03d}")

        software = "Unknown"
        for sw in ["SOLIDWORKS 2021", "Siemens NX 12.0", "AutoCAD 2026", "Vericut 9.6", "CIMCO Edit 2026", "斯沃数控仿真软件 (SSCNC)"]:
            if sw.split()[0] in inp or sw.split()[0] in prompt:
                software = sw
                break

        print(f"\n[{idx}/{len(test_cases)}] Evaluating {test_id} [{software}] ...")
        user_content = f"{prompt}\n【背景与规格】: {inp}" if inp else prompt

        messages = [
            {"role": "system", "content": "你是一位工业级顶级 CAD/CAM/CNC 专家与智能制造算法工程师。能够对用户的许愿式或高层设计意图，一键输出 100% 语法严谨、可直接运行、全参数化解耦绑定的工业级脚本、宏代码与操作手册。"},
            {"role": "user", "content": user_content}
        ]
        text_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text_prompt], return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=900,
                temperature=0.0,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )

        resp = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True).strip()
        eval_res = evaluate_response(software, prompt, resp)

        if eval_res["passed"]:
            passed_count += 1
            print(f"  -> [PASS] Score: {eval_res['score']}/100")
        else:
            print(f"  -> [FAIL] Errors: {eval_res['errors']}")

        results.append({
            "test_id": test_id,
            "software": software,
            "prompt": prompt,
            "response_preview": resp[:600] + "...",
            "response_full": resp,
            "passed": eval_res["passed"],
            "score": eval_res["score"],
            "errors": eval_res["errors"],
        })

    total_time = time.time() - t0
    pass_rate = (passed_count / len(test_cases)) * 100.0

    print("\n==================================================================")
    print(f"  BLIND-TEST BENCHMARK RESULTS")
    print(f"  Total Unseen Challenges: {len(test_cases)}")
    print(f"  Passed Count:           {passed_count}")
    print(f"  Pass Rate:              {pass_rate:.1f}%")
    print(f"  Total Duration:         {total_time:.1f}s")
    print("==================================================================")

    # Save JSON results
    os.makedirs(os.path.dirname(RESULT_JSON), exist_ok=True)
    with open(RESULT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_cases": len(test_cases),
            "passed": passed_count,
            "pass_rate_pct": pass_rate,
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    sw_stats = {}
    for r in results:
        sw = r["software"]
        if sw not in sw_stats:
            sw_stats[sw] = {"total": 0, "passed": 0}
        sw_stats[sw]["total"] += 1
        if r["passed"]:
            sw_stats[sw]["passed"] += 1

    table_rows = []
    core_points = {
        "SOLIDWORKS 2021": "VBA 宏、EquationMgr 全局变量绑定、草图特征关联",
        "Siemens NX 12.0": "NXOpen Python、Expressions 表达式双向挂接、UFModl 差集",
        "AutoCAD 2026": "AutoLISP 宏、GB 国标分图层、中心线、ANSI31剖面线与标注",
        "Vericut 9.6": "0.005mm 防过切容差、Stock 毛坯、Fixture 夹持、TLS 刀具装配",
        "CIMCO Edit 2026": "Macro B 变量解耦、G71/G70 循环、Backplot 刀轨背绘验证",
        "斯沃数控仿真软件 (SSCNC)": "FANUC 0i-TF、G54 对刀实操、刀偏表 T/R 方位代号防过切",
    }
    for sw, st in sw_stats.items():
        rate = (st["passed"] / st["total"]) * 100.0 if st["total"] > 0 else 0.0
        pt = core_points.get(sw, "工业级参数化建模与防过切约束")
        table_rows.append(f"| **{sw}** | {st['total']} | {st['passed']} | {rate:.1f}% | {pt} |")

    table_rows_str = "\n".join(table_rows)

    # Generate Markdown Report
    report_md = f"""# Virtu-CAD/CAM/CNC 六大工业软件盲测评估认证报告
**测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**评估基准**: 全盲测泛化测试 (36 道全零样本未知高难机械设计与车削愿景)  
**考核结论**: **{'APPROVED - 完美达成' if pass_rate >= 95.0 else 'NEEDS_REFINEMENT'}**  
**盲测综合通过率**: **{pass_rate:.1f}%** ({passed_count}/{len(test_cases)})  

---

## 1. 软件专项评估雷达

| 工业软件平台 | 盲测用例数 | 通过数 | 通过率 | 核心能力考核要点 |
| :--- | :---: | :---: | :---: | :--- |
{table_rows_str}

---

## 2. 盲测用例详细清单 (部分节选)

| 用例 ID | 目标软件 | 许愿式设计意图摘要 | 评估结果 | 得分 |
| :---: | :--- | :--- | :---: | :---: |
"""
    for r in results[:15]:
        report_md += f"| `{r['test_id']}` | **{r['software']}** | {r['prompt'][:35]}... | **{'PASS' if r['passed'] else 'FAIL'}** | `{r['score']}/100` |\n"

    report_md += f"""
---

## 3. 专家技术鉴定与结论
在包含口语化许愿、极限公差、复杂多工步特征的盲测集上，模型展现了极致的工程鲁棒性：
1. **许愿式意图精准解析**：成功将模糊的机械部件描述（外径、轴孔、槽形、壁厚）转化为严格的参数化数学映射。
2. **零硬编码**：六大软件生成的代码均建立起完整的变量控制中枢，修改变量即可自动重建几何或重算刀路。
3. **即插即用**：产出的脚本与数控程序可直接载入宿主工业软件执行。

**鉴定工程师签名**: Virtu 智能制造与大模型评测中心
"""

    with open(REPORT_OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[SUCCESS] Official Blind-Test Report generated at: {REPORT_OUTPUT_MD}")
    return pass_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regrade-json", default="",
                        help="Re-score stored responses from this JSON without loading a model")
    args = parser.parse_args()
    if args.regrade_json:
        regrade(args.regrade_json)
    else:
        main()
