# -*- coding: utf-8 -*-
"""飞轮难度校准 + 修复前基线：模型试做 24 题，探针判分，得每族 pass 率与 solver 轨迹。

用作权重修复前的基线（修复后重跑同题对比 delta）。非模型锚=探针/尺子。
"""
import sys
import json
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as proc
import build_impeller_flywheel_tasks as fw

TASKS = ROOT / "data" / "impeller_flywheel_tasks.jsonl"
OUT = ROOT / "data" / "impeller_flywheel_baseline.json"
SYSTEM = "你是航空叶轮设计工程师。按题目要求计算或设计，只输出一个规定的 JSON 代码块。"


def call_model(problem, model):
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM},
               {"role": "user", "content": problem}], "stream": False,
               "options": {"temperature": 0.3, "num_predict": 900, "num_ctx": 8192}}
    req = urllib.request.Request(proc.OLLAMA + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    return res.get("message", {}).get("content", "")


def score(task, sub):
    fam = task["family"][:2]
    ver = task["verification"]
    if fam == "T1":
        return fw.probe_T1(sub, ver["ground_truth"])
    if fam == "T2":
        return fw.probe_T2(sub, ver["bad_params"])
    if fam == "T3":
        return fw.probe_T3(sub, ver["returned"])
    return fw.probe_T4(sub, ver["constraints"])


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=proc.MODEL, help="被测 Ollama 标签")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    model = args.model
    out_path = Path(args.out)
    tasks = [json.loads(l) for l in open(TASKS, encoding="utf-8")]
    results = []
    fam_stat = {}
    for t in tasks:
        fam = t["family"]
        try:
            resp = call_model(t["problem"], model)
            sub = proc.extract_json(resp)
            res = score(t, sub) if sub is not None else {"passed": False, "fail_to_pass": ["无 JSON"]}
        except Exception as e:
            resp, sub, res = "", None, {"passed": False, "fail_to_pass": [f"call_error: {e}"]}
        passed = bool(res.get("passed"))
        results.append({"id": t["id"], "family": fam, "passed": passed,
                        "fail_to_pass": res.get("fail_to_pass", []), "response": resp[:1500]})
        s = fam_stat.setdefault(fam, {"pass": 0, "n": 0})
        s["n"] += 1
        s["pass"] += int(passed)
        print(f"[{t['id']}] {'PASS' if passed else 'FAIL'} {res.get('fail_to_pass', [])[:2]}", flush=True)
    rates = {k: round(v["pass"] / v["n"], 3) for k, v in fam_stat.items()}
    report = {"model": model, "weight_digest": proc.WEIGHT_DIGEST, "phase": "post_fix",
              "per_family": fam_stat, "pass_rates": rates, "difficulty_band": [0.2, 0.8],
              "results": results, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[CALIBRATION]", json.dumps({"model": model, "pass_rates": rates, "counts": fam_stat}, ensure_ascii=False))


if __name__ == "__main__":
    main()