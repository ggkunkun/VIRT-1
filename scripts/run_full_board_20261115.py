# -*- coding: utf-8 -*-
"""训练完成后主力模型的全面测评编排器（2026-11-15）。

设计约束（AGENTS.md §8 测量宪法）：
  1. 不另立判分器：24 案例走 run_domain_ab.score(slot_exact_v2)，通用/留出集走
     virtu_eval.graders.score_case，训练目标探针走 deploy_trained_adapter 既有判据；
  2. 被测对象按内容寻址：/api/tags digest + served_layers，起链/收链各拍一次快照，
     drift 非空则该腿作废；
  3. 闸必须能被证伪：起链先跑探针判据反证单测 + holdout gold 满分自检；
  4. 数字必须可归因：每个板块保留原始 raw.jsonl / summary.json，报告只引用带
     run_id / n / evidence / basis 的数；没测就写「未测」；
  5. 测量链独占资源：所有板块严格串行，不并发多个模型抢显存。

用法（在 D:\\Virtu模型 下）：
  .venv\\Scripts\\python.exe scripts\\run_full_board_20261115.py
  .venv\\Scripts\\python.exe scripts\\run_full_board_20261115.py --boards targeted
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))

from virtu_eval import provenance as P  # noqa: E402
from virtu_eval.arms import OllamaNativeArm  # noqa: E402

API = "http://127.0.0.1:11434"
PRIMARY = "virtu-vericut96:v2"
BASELINE = "virtu-master-fixed:latest"
MODELS = [PRIMARY, "virtu-vericut-e:latest", "virtu-six-software:v1",
          BASELINE, "qwen3:8b"]
BOARD_ORDER = ["gates", "targeted", "sanity", "domain24", "generic", "holdout"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def tags_snapshot():
    with opener().open(API + "/api/tags", timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return {m["model"]: m.get("digest") for m in data.get("models", [])}


def served_layers(tag):
    try:
        return OllamaNativeArm(model_id=tag).served_layers
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}:{exc}"}


def sha256(path):
    return P.sha256_file(str(path))


def run_cmd(argv, cwd=ROOT, timeout=7200):
    """串行执行一个阶段，stdout 实时透传；失败只记录不掩盖。"""
    log("RUN " + " ".join(str(a) for a in argv))
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        p = subprocess.run([str(a) for a in argv], cwd=str(cwd), env=env,
                           timeout=timeout)
        return {"exit_code": p.returncode}
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": -9, "error": f"timeout {exc.timeout}s"}
    except Exception as exc:  # noqa: BLE001
        return {"exit_code": -1, "error": f"{type(exc).__name__}:{exc}"}


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def capture_identity(out):
    """起链身份：标签 -> digest -> served_layers，全部按内容寻址。"""
    tags = tags_snapshot()
    ident = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "primary": PRIMARY,
        "baseline": BASELINE,
        "models": {},
        "training_receipts": {},
        "ruler_sha256": {},
    }
    for tag in MODELS:
        layers = served_layers(tag)
        ident["models"][tag] = {"tags_digest": tags.get(tag), "served_layers": layers}
    receipt_dir = ROOT / "checkpoints"
    for f in sorted(receipt_dir.glob("deployment_receipt_*.json")):
        d = read_json(f) or {}
        ident["training_receipts"][f.name] = {
            "tag": d.get("tag"), "status": d.get("status"),
            "deployed_at": d.get("deployed_at"),
            "gguf_sha256": d.get("gguf_sha256"),
            "adapter_sha256": d.get("adapter_sha256"),
            "dataset_sha256": d.get("dataset_sha256"),
        }
    for rel in ("virtu_eval/graders.py", "virtu_eval/runner.py", "virtu_eval/arms.py",
                "scripts/run_domain_ab.py", "scripts/eval_all_models_live.py",
                "scripts/eval_vericut_e_training.py",
                "cloud_train_pack/deploy_trained_adapter.py"):
        p = ROOT / rel
        if p.is_file():
            ident["ruler_sha256"][rel] = sha256(p)
    write_json(out / "identity.json", ident)
    return ident, tags


def phase_gates(out, progress):
    """§8.4：判据必须能被证伪；§8.5：gold 必须被判满分，否则闸空转。"""
    res = {}
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    py = py if py.is_file() else Path(sys.executable)
    r1 = run_cmd([py, "-m", "pytest", "tests/test_cloud_and_deploy_hardening.py",
                  "-q", "--disable-warnings"], timeout=600)
    r2 = run_cmd([py, "scripts/eval_vericut_e_training.py", "--selftest"], timeout=600)
    res["probe_mutation_tests"] = r1
    res["holdout_gold_selftest"] = r2
    res["passed"] = r1["exit_code"] == 0 and r2["exit_code"] == 0
    res["status"] = "measured" if res["passed"] else "failed"
    write_json(out / "gates.json", res)
    log(f"gates passed={res['passed']} pytest={r1['exit_code']} gold={r2['exit_code']}")
    return res


def phase_targeted(out, progress):
    """复用部署验收的同一套探针判据（profile=all），不改判据、不改已有凭证。"""
    import deploy_trained_adapter as D

    res = {"probe_profile": "all", "think": False, "models": {},
           "grader_source": "cloud_train_pack/deploy_trained_adapter.py",
           "grader_sha256": sha256(ROOT / "cloud_train_pack" / "deploy_trained_adapter.py")}
    for tag in MODELS:
        t0 = time.time()
        try:
            probes = D.verify_deployed_model(tag, probe_profile="all", think=False)
        except Exception as exc:  # noqa: BLE001
            res["models"][tag] = {"status": "error", "error": f"{type(exc).__name__}:{exc}"}
            log(f"targeted {tag} ERROR {exc}")
            continue
        items = [{"key": k, "passed": bool(v.get("passed")),
                  "reason": v.get("reason"), "sample": (v.get("sample") or v.get("raw_snippet") or "")[:400]}
                 for k, v in probes.items() if isinstance(v, dict) and "passed" in v]
        passed = sum(1 for x in items if x["passed"])
        res["models"][tag] = {
            "status": "measured", "n": len(items), "passed": passed,
            "pass_rate_pct": round(100.0 * passed / len(items), 2) if items else None,
            "items": items, "elapsed_s": round(time.time() - t0, 1),
            "served_layers": served_layers(tag),
        }
        log(f"targeted {tag}: {passed}/{len(items)} probes passed")
        write_json(out / "targeted.json", res)  # 每臂落盘，断链可续
    res["status"] = ("measured" if all(v.get("status") == "measured"
                                       for v in res["models"].values()) else "partial")
    return res


def phase_sanity(out, progress):
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    py = py if py.is_file() else Path(sys.executable)
    d = out / "sanity"
    d.mkdir(parents=True, exist_ok=True)
    r = run_cmd([py, "scripts/eval_model_sanity.py", "--models"] + MODELS +
                ["--out-dir", str(d.relative_to(ROOT)), "--no-warmup"], timeout=3600)
    files = sorted(str(p.relative_to(ROOT)) for p in d.glob("*.json"))
    return {"cmd": r, "evidence_files": files, "status": "measured" if r["exit_code"] == 0 else "failed"}


def phase_domain24(out, progress):
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    py = py if py.is_file() else Path(sys.executable)
    d = out / "domain24"
    d.mkdir(parents=True, exist_ok=True)
    r = run_cmd([py, "scripts/run_domain_ab.py", "--models", ",".join(MODELS),
                 "--out", str(d.relative_to(ROOT)), "--num-predict", "260",
                 "--num-ctx", "4096", "--temperature", "0", "--seed", "1234"],
                timeout=5400)
    summary = read_json(d / "summary.json") or {}
    return {"cmd": r, "summary_path": str((d / "summary.json").relative_to(ROOT)),
            "raw_path": str((d / "raw.jsonl").relative_to(ROOT)),
            "run_id": summary.get("run_id"), "basis": summary.get("basis"),
            "n": summary.get("n"), "grader_version": summary.get("grader_version"),
            "per_model": {k: {kk: v.get(kk) for kk in
                              ("n", "mean_score", "median_score", "mean_tok_s",
                               "n_transport_errors", "basis", "served_layers")}
                          for k, v in (summary.get("summary") or {}).items()},
            "status": "measured" if r["exit_code"] == 0 and summary.get("basis") == "measured" else "failed"}


def phase_generic(out, progress):
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    py = py if py.is_file() else Path(sys.executable)
    d = out / "generic"
    d.mkdir(parents=True, exist_ok=True)
    r = run_cmd([py, "scripts/eval_all_models_live.py", "--only", ",".join(MODELS),
                 "--per-dim", "2", "--tiers", "easy,medium", "--max-tokens", "384",
                 "--num-ctx", "4096", "--timeout", "180",
                 "--out-root", str(d.relative_to(ROOT))], timeout=5400)
    summary = read_json(d / "summary.json") or {}
    per = {}
    for tag, v in (summary.get("models") or {}).items():
        det = v.get("detail") or {}
        per[tag] = {"status": v.get("status"), "digest": v.get("digest"),
                    "run_id": det.get("run_id"), "dimensions": det.get("dimensions"),
                    "overall_weighted": det.get("overall_weighted"),
                    "gate": det.get("gate"),
                    "leg_dir": v.get("leg_dir"), "wall_s": v.get("wall_s")}
    return {"cmd": r, "summary_path": str((d / "summary.json").relative_to(ROOT)),
            "meta": summary.get("meta"), "per_model": per,
            "status": "measured" if r["exit_code"] == 0 else "failed"}


def phase_holdout(out, progress):
    """105 题去污染留出集，主测 vs 训练前主力基线（同题、同 seed、同判分器）。"""
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    py = py if py.is_file() else Path(sys.executable)
    d = out / "holdout"
    d.mkdir(parents=True, exist_ok=True)
    r = run_cmd([py, "scripts/eval_vericut_e_training.py",
                 "--baseline", BASELINE, "--candidate", PRIMARY,
                 "--out-dir", str(d.relative_to(ROOT)),
                 "--sanity-per-file", "0", "--max-tokens", "512",
                 "--num-ctx", "4096"], timeout=7200)
    rep = read_json(d / "comparison_report.json") or {}
    return {"cmd": r, "report_path": str((d / "comparison_report.json").relative_to(ROOT)),
            "identity_path": str((d / "identity.json").relative_to(ROOT)),
            "basis": rep.get("basis"), "run_id": rep.get("run_id"),
            "identity_drift": rep.get("identity_drift"),
            "holdout": rep.get("holdout"),
            "status": "measured" if r["exit_code"] == 0 and rep.get("basis") == "measured" else "failed"}


PHASES = {"gates": phase_gates, "targeted": phase_targeted, "sanity": phase_sanity,
          "domain24": phase_domain24, "generic": phase_generic, "holdout": phase_holdout}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/eval_full_board_20261115")
    ap.add_argument("--boards", default=",".join(BOARD_ORDER))
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    boards = [b.strip() for b in args.boards.split(",") if b.strip()]
    progress_path = out / "progress.json"
    progress = read_json(progress_path) or {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                            "boards": {}, "primary": PRIMARY,
                                            "baseline": BASELINE, "models": MODELS}

    ident, snap_start = capture_identity(out)
    progress["identity"] = str((out / "identity.json").relative_to(ROOT))
    write_json(progress_path, progress)

    for board in boards:
        if board not in PHASES:
            log(f"unknown board {board}, skip")
            continue
        if progress["boards"].get(board, {}).get("status") in ("measured", "passed"):
            log(f"{board} already done, skip")
            continue
        log(f"=== PHASE {board} start ===")
        t0 = time.time()
        try:
            result = PHASES[board](out, progress)
        except Exception as exc:  # noqa: BLE001 - 单阶段失败不得伪装成通过
            result = {"status": "error", "error": f"{type(exc).__name__}:{exc}"}
            log(f"{board} ERROR {result['error']}")
        result["elapsed_s"] = round(time.time() - t0, 1)
        progress["boards"][board] = result
        write_json(out / f"{board}_phase.json", result)
        write_json(progress_path, progress)
        log(f"=== PHASE {board} done status={result.get('status') or result.get('passed')} "
            f"{result['elapsed_s']}s ===")

    snap_end = tags_snapshot()
    drift = []
    for tag in MODELS:
        if snap_start.get(tag) != snap_end.get(tag):
            drift.append(f"{tag}: {str(snap_start.get(tag))[:12]} -> {str(snap_end.get(tag))[:12]}")
    progress["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    progress["tag_snapshot_start"] = snap_start
    progress["tag_snapshot_end"] = snap_end
    progress["artifact_drift"] = drift
    progress["chain_voided"] = bool(drift)
    write_json(progress_path, progress)
    log(f"ALL DONE drift={drift}")


if __name__ == "__main__":
    main()
