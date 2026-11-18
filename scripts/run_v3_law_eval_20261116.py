# -*- coding: utf-8 -*-
"""Virtu 测评法律首次适用：virtu-six-software:v3 四板块实测（2026-11-16）。

被测对象按内容寻址；判分器版本写进每份 manifest；未测项写「未测」不补分。
只跑 gates / targeted / sanity / domain24 / generic；留出集因基线标签已不在库中
无法配对，按法律第四条标「未测」。

用法（D:\\Virtu模型 下）：
  .venv\\Scripts\\python.exe scripts\\run_v3_law_eval_20261116.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
from virtu_eval import provenance as P  # noqa: E402
import deploy_trained_adapter as D  # noqa: E402

# 命令行可指定被测对象（强化链会依次验 v4 / 后续候选），默认仍是 v3
import argparse as _ap
_ap0 = _ap.ArgumentParser(add_help=False)
_ap0.add_argument("--model", default="virtu-six-software:v3")
_ap0.add_argument("--out-dir", default="runs/eval_v3_law_20261116")
_args, _ = _ap0.parse_known_args()
MODEL = _args.model
OUT = ROOT / _args.out_dir
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)
API = "http://127.0.0.1:11434"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def tags():
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return {m["model"]: m["digest"] for m in
            json.loads(op.open(API + "/api/tags", timeout=30).read()).get("models", [])}


def write_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run(argv, timeout=5400):
    log("RUN " + " ".join(str(x) for x in argv))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(ROOT), env=env, timeout=timeout)
        return {"exit_code": p.returncode}
    except Exception as exc:  # noqa: BLE001
        return {"exit_code": -1, "error": f"{type(exc).__name__}:{exc}"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    start = tags()
    if MODEL not in start:
        raise SystemExit(f"[FATAL] {MODEL} 不在库中，当前库={list(start)}")
    ident = P.RunIdentity.capture(
        model_ids=[MODEL],
        case_dirs=["data/benchmark/virtu_eval_v1", "data/sft/vericut_e_training"],
        ruler_files=["virtu_eval/graders.py", "virtu_eval/runner.py", "virtu_eval/arms.py",
                     "scripts/run_domain_ab.py", "cloud_train_pack/deploy_trained_adapter.py",
                     ".agents/rules/virtu-evaluation-law.md"],
        extra={"evaluation_law": ".agents/rules/virtu-evaluation-law.md",
               "tags_digest": start[MODEL]})
    ident.write(OUT / "identity.json")
    log(f"identity run_id={ident.run_id} digest={str(start[MODEL])[:12]}")

    phases = {}
    # 1. 闸门：反证测试 + gold 满分自检
    phases["gates"] = {
        "probe_mutation": run([PY, "-m", "pytest",
                               "tests/test_cloud_and_deploy_hardening.py",
                               "tests/test_six_software_probe_measurement_fix.py",
                               "-q", "--disable-warnings"], timeout=900),
        "gold_selftest": run([PY, "scripts/eval_vericut_e_training.py", "--selftest"],
                             timeout=900),
    }
    phases["gates"]["passed"] = (phases["gates"]["probe_mutation"]["exit_code"] == 0 and
                                  phases["gates"]["gold_selftest"]["exit_code"] == 0)
    write_json(OUT / "gates.json", phases["gates"])
    log(f"gates passed={phases['gates']['passed']}")
    if not phases["gates"]["passed"]:
        raise SystemExit("[FATAL] 闸未通过，按法律第二条停止测评")

    # 2. 训练目标探针（用修复后的判分器，记录 measurement_version + grader_sha256）
    probes = D.verify_deployed_model(MODEL, probe_profile="all", think=False)
    # 保留完整响应（不是 400 字片段）：§8.2 要求先复现原始输出再判模型缺陷/测量缺陷
    items = [{"key": k, "passed": bool(v.get("passed")), "reason": v.get("reason"),
              "sample": (v.get("sample") or v.get("raw_snippet") or "")[:400],
              "full_response": (v.get("sample") or v.get("raw_snippet") or ""),
              "detail": {kk: vv for kk, vv in v.items() if kk not in ("sample", "raw_snippet")}}
             for k, v in probes.items() if isinstance(v, dict) and "passed" in v]
    phases["targeted"] = {
        "basis": "measured", "n": len(items),
        "passed": sum(1 for i in items if i["passed"]),
        "failed": [i["key"] for i in items if not i["passed"]],
        "measurement_version": getattr(D, "MEASUREMENT_VERSION", "unknown"),
        "grader_sha256": P.sha256_file(str(ROOT / "cloud_train_pack" / "deploy_trained_adapter.py")),
        "items": items,
    }
    write_json(OUT / "targeted.json", phases["targeted"])
    log(f"targeted {phases['targeted']['passed']}/{len(items)}")

    # 3. 健全性探针
    d = OUT / "sanity"
    r = run([PY, "scripts/eval_model_sanity.py", "--models", MODEL,
             "--out-dir", str(d.relative_to(ROOT)), "--no-warmup"], timeout=1800)
    phases["sanity"] = {"cmd": r, "status": "measured" if r["exit_code"] == 0 else "failed",
                        "evidence": str(d.relative_to(ROOT))}

    # 4. 24 案例关键词基准（口径：slot_exact_v2，只作同尺相对比较）
    d = OUT / "domain24"
    r = run([PY, "scripts/run_domain_ab.py", "--models", MODEL,
             "--out", str(d.relative_to(ROOT)), "--num-predict", "260",
             "--num-ctx", "4096", "--temperature", "0", "--seed", "1234"], timeout=3600)
    summ = json.loads((d / "summary.json").read_text(encoding="utf-8")) if (d / "summary.json").is_file() else {}
    phases["domain24"] = {
        "cmd": r, "basis": summ.get("basis"), "n": summ.get("n"),
        "run_id": summ.get("run_id"), "grader_version": summ.get("grader_version"),
        "per_model": {k: {"n": v.get("n"), "mean_score": v.get("mean_score"),
                          "median_score": v.get("median_score"),
                          "mean_tok_s": v.get("mean_tok_s"),
                          "transport_errors": v.get("n_transport_errors")}
                      for k, v in (summ.get("summary") or {}).items()},
        "evidence": str((d / "summary.json").relative_to(ROOT)),
        "note": "slot_exact_v2 绝对分不可作能力结论，详见法律第二条",
    }
    write_json(OUT / "domain24.json", phases["domain24"])
    log(f"domain24 mean={list(phases['domain24']['per_model'].values())[0].get('mean_score')}")

    # 5. 通用 7 维题板（雷达图唯一数据源；每条腿自带 seal/run_id/served_layers）
    d = OUT / "generic"
    r = run([PY, "scripts/eval_all_models_live.py", "--only", MODEL,
             "--per-dim", "2", "--tiers", "easy,medium", "--max-tokens", "384",
             "--num-ctx", "4096", "--timeout", "180",
             "--out-root", str(d.relative_to(ROOT))], timeout=5400)
    summ = json.loads((d / "summary.json").read_text(encoding="utf-8")) if (d / "summary.json").is_file() else {}
    v = (summ.get("models") or {}).get(MODEL, {})
    det = v.get("detail") or {}
    phases["generic"] = {
        "cmd": r, "status": v.get("status"), "digest": v.get("digest"),
        "run_id": det.get("run_id"), "gate": det.get("gate"),
        "dimensions": {k: x["score"] for k, x in (det.get("dimensions") or {}).items()},
        "overall_weighted": det.get("overall_weighted"),
        "leg_dir": v.get("leg_dir"),
        "evidence": str((d / "summary.json").relative_to(ROOT)),
    }
    write_json(OUT / "generic.json", phases["generic"])
    log(f"generic overall={phases['generic']['overall_weighted']}")

    phases["holdout"] = {"basis": "未测",
                         "reason": "基线 virtu-master-fixed:latest 已不在库中，无法构成同轮配对；"
                                   "按法律第四条不引用历史腿顶替"}
    end = tags()
    # 测评法律第一条：只有【被测对象】的 digest 变化才作废该腿。
    # 库里新增/删除无关标签是共享状态变更，必须记录，但不得误判成被测对象漂移。
    subject_drift = ([] if start.get(MODEL) == end.get(MODEL)
                     else [f"{MODEL}: {str(start.get(MODEL))[:12]} -> {str(end.get(MODEL))[:12]}"])
    library_changes = sorted(
        f"{t}: {str(start.get(t))[:12]} -> {str(end.get(t))[:12]}"
        for t in set(start) | set(end)
        if t != MODEL and start.get(t) != end.get(t))
    phases["library_changes"] = {"basis": "measured", "changes": library_changes,
                                 "note": "共享库变更已记录；按测评法律第一条不使被测腿作废"}
    report = {
        "basis": "measured" if not subject_drift else "voided_due_to_drift",
        "model": MODEL, "run_id": ident.run_id, "identity": ident.to_dict(),
        "artifact_drift": subject_drift, "phases": phases,
        "law": ".agents/rules/virtu-evaluation-law.md",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    write_json(OUT / "report.json", report)
    log(f"DONE drift={drift}")


if __name__ == "__main__":
    main()
