# -*- coding: utf-8 -*-
"""run_wm_holdout.py — 世界模型留出集封缄评测器（model_raw 口径）。

特性（测量宪法）：
  - 被测对象按权重 blobs 内容哈希寻址，不按标签名；
  - 每例立即 append JSONL + flush，支持断点续跑；
  - 逐例判分与模型原生输出分离，护栏/求解器不得计入模型能力分；
  - 统一记录 transport error，>5% 整腿判废；
  - 收尾写 summary + SEAL（raw.jsonl/summary 的 sha256 与 run_id）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

import eval_worldmodel as E  # noqa: E402
import wm_eval  # noqa: E402
import wm_contract as C  # noqa: E402

API = "http://127.0.0.1:11434"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def server_alive(timeout=3.0):
    try:
        with urllib.request.urlopen(API + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server(max_wait=120.0, restart=False):
    if not restart and server_alive():
        return True
    if restart:
        subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], capture_output=True)
        subprocess.run(["taskkill", "/IM", "ollama app.exe", "/F"], capture_output=True)
        time.sleep(2)
    subprocess.Popen(["cmd", "/c", os.path.join(ROOT, "start_virtu_ollama.bat")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < max_wait:
        time.sleep(3)
        if server_alive():
            time.sleep(5)
            return True
    return False


def model_identity(tag):
    mf = subprocess.check_output(["ollama", "show", tag, "--modelfile"], text=True,
                                 encoding="utf-8", errors="replace")
    blob = ""
    for line in mf.splitlines():
        if line.startswith("FROM "):
            blob = line.split(" ", 1)[1].strip()
            break
    blob_sha = sha256_file(blob) if blob and os.path.isfile(blob) else ""
    return {"model_tag": tag, "weight_blob": blob, "weight_blob_sha256": blob_sha,
            "modelfile_sha256": sha256_text(mf),
            "system_sha256": sha256_text(C.SYSTEM), "system_chars": len(C.SYSTEM)}


def call(model, prompt, timeout, num_ctx, num_gpu, num_batch, num_predict, keep_alive):
    body = {
        "model": model, "prompt": prompt, "system": C.SYSTEM, "stream": False,
        "think": False, "format": "json", "keep_alive": keep_alive,
        "options": {"temperature": 0, "num_predict": num_predict, "num_ctx": num_ctx,
                    "num_gpu": num_gpu, "num_batch": num_batch},
    }
    req = urllib.request.Request(API + "/api/generate", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            obj = json.loads(r.read().decode("utf-8"))
        obj["_sec"] = round(time.time() - t0, 2)
        obj["_error"] = None
        return obj
    except Exception as e:  # noqa: BLE001
        return {"response": "", "_sec": round(time.time() - t0, 2),
                "_error": f"{type(e).__name__}: {e}"}


def wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - r) / d, 4), round((c + r) / d, 4)]


def _cmp_num(e, p, tol=0.08):
    try:
        if isinstance(e, (list, tuple)) or isinstance(p, (list, tuple)):
            if not isinstance(e, (list, tuple)) or not isinstance(p, (list, tuple)) or len(e) != len(p):
                return False
            return all(_cmp_num(a, b, tol) for a, b in zip(e, p))
        ev, pv = float(e), float(p)
        if abs(ev) < 1e-9:
            return abs(pv) <= 1e-6
        return abs(pv - ev) / abs(ev) <= tol
    except (TypeError, ValueError):
        return False


def summarize(raw_path, cases_by_id, meta):
    recs = [json.loads(l) for l in open(raw_path, encoding="utf-8") if l.strip()]
    per = defaultdict(lambda: {"n": 0, "pass": 0, "transport": 0, "parse_fail": 0,
                                "shape": 0, "num_exp": 0, "num_pres": 0, "num_ok": 0,
                                "txt_exp": 0, "txt_pres": 0, "txt_ok": 0,
                                "gate_exp": 0, "gate_ok": 0,
                                "claim_checked": 0, "claim_bad": 0,
                                "gate_checked": 0, "gate_bad": 0,
                                "miss": Counter()})
    for r in recs:
        fam = r["task"]
        P = per[fam]
        P["n"] += 1
        if r.get("error"):
            P["transport"] += 1
            continue
        raw_obj = E.extract_json(r.get("raw") or "")
        if raw_obj is None:
            P["parse_fail"] += 1
        exp = r["expected"]
        ok, fmt, miss = E.judge(fam, exp, raw_obj) if raw_obj is not None else (False, False, ["<parse_fail>"])
        P["pass"] += 1 if ok else 0
        P["shape"] += 1 if fmt else 0
        for m in miss:
            P["miss"][m] += 1
        if fam == "invalid":
            continue
        ws = E._ws(raw_obj) if isinstance(raw_obj, dict) else {}
        ews = E._merge_nested(fam, exp, E._flatten((exp or {}).get("world_state") or {}))
        pws = E._merge_nested(fam, raw_obj, E._flatten(ws))
        for k in E.NUM_KEYS.get(fam, []):
            if k in ews:
                P["num_exp"] += 1
                if k in pws:
                    P["num_pres"] += 1
                    P["num_ok"] += 1 if _cmp_num(ews[k], pws[k]) else 0
        for k in list(E.TEXT_KEYS.get(fam, [])) + list(E.BOOL_KEYS.get(fam, [])):
            if k in ews:
                P["txt_exp"] += 1
                if k in pws:
                    P["txt_pres"] += 1
                    good = (E._to_bool(ews[k]) == E._to_bool(pws[k]) if k in E.BOOL_KEYS.get(fam, [])
                            else E._norm_text(ews[k]) == E._norm_text(pws[k]))
                    P["txt_ok"] += 1 if good else 0
        for k in E.GATE_KEYS.get(fam, []):
            if k in ews:
                P["gate_exp"] += 1
                P["gate_ok"] += 1 if (k in pws and C.normalize_gate(k, ews[k]) == C.normalize_gate(k, pws[k])) else 0
        der = raw_obj.get("derivation") if isinstance(raw_obj, dict) else None
        if isinstance(der, dict):
            for k, expr in der.items():
                if k in ws and isinstance(ws.get(k), (int, float)) and not isinstance(ws.get(k), bool):
                    v = wm_eval.safe_eval(str(expr))
                    if v is not None and v != 0:
                        P["claim_checked"] += 1
                        if abs(float(ws[k]) - v) / abs(v) > 0.08:
                            P["claim_bad"] += 1
        sf, fg = ws.get("safety_factor"), ws.get("fos_gate")
        if isinstance(sf, (int, float)) and not isinstance(sf, bool) and isinstance(fg, str):
            P["gate_checked"] += 1
            if (fg.lower() == "pass" and sf < 1.5) or (fg.lower() == "fail" and sf >= 1.5):
                P["gate_bad"] += 1
        dv, vc = ws.get("delta_volume_mm3"), ws.get("volume_conservation")
        if isinstance(dv, (int, float)) and not isinstance(dv, bool) and isinstance(vc, str):
            P["gate_checked"] += 1
            if (vc.lower() == "pass" and dv > 0) or (vc.lower() == "fail" and dv <= 0):
                P["gate_bad"] += 1
    n = len(recs)
    k = sum(v["pass"] for v in per.values())
    transport = sum(v["transport"] for v in per.values())
    lat = sorted(r.get("sec") or 0 for r in recs)
    tok_s = [r["eval_count"] / (r["eval_duration_ns"] / 1e9) for r in recs
             if r.get("eval_count") and r.get("eval_duration_ns")]
    tok_s.sort()
    overall = {
        "n": n, "pass": k, "pass_rate": round(k / n, 4) if n else 0,
        "wilson95": wilson(k, n), "transport_errors": transport,
        "transport_rate": round(transport / n, 4) if n else 0,
        "valid": bool(n and transport / n <= 0.05),
        "latency_median_sec": lat[len(lat) // 2] if lat else None,
        "latency_p90_sec": lat[int(len(lat) * 0.9)] if lat else None,
        "decode_tok_per_sec_median": round(tok_s[len(tok_s) // 2], 2) if tok_s else None,
        "num_fields_expected": sum(v["num_exp"] for v in per.values()),
        "num_fields_present": sum(v["num_pres"] for v in per.values()),
        "num_fields_correct": sum(v["num_ok"] for v in per.values()),
        "text_fields_expected": sum(v["txt_exp"] for v in per.values()),
        "text_fields_present": sum(v["txt_pres"] for v in per.values()),
        "text_fields_correct": sum(v["txt_ok"] for v in per.values()),
        "gate_fields_expected": sum(v["gate_exp"] for v in per.values()),
        "gate_fields_correct": sum(v["gate_ok"] for v in per.values()),
        "claim_checked_fields": sum(v["claim_checked"] for v in per.values()),
        "claim_mismatch_fields": sum(v["claim_bad"] for v in per.values()),
        "gate_checked": sum(v["gate_checked"] for v in per.values()),
        "gate_inconsistent_cases": sum(v["gate_bad"] for v in per.values()),
    }
    return {"meta": meta, "overall": overall, "per_family": dict(per),
            "case_count": len(cases_by_id)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=os.path.join(ROOT, "data", "holdout", "wm_holdout_v2.jsonl"))
    ap.add_argument("--model", default="virtu-wm-v3:chatml")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "runs", "wm_holdout_v2"))
    ap.add_argument("--per-family", type=int, default=0, help="每族取前 N 例（0=全部）")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--num-ctx", type=int, default=5120)
    ap.add_argument("--num-gpu", type=int, default=16)
    ap.add_argument("--num-batch", type=int, default=128)
    ap.add_argument("--num-predict", type=int, default=512)
    ap.add_argument("--keep-alive", default="30m")
    args = ap.parse_args()
    if "data" + os.sep + "holdout" not in os.path.abspath(args.cases):
        raise SystemExit("[FATAL] 只允许评测 data/holdout/** 下的冻结留出集（防止训练集自测）")
    cases = [json.loads(l) for l in open(args.cases, encoding="utf-8") if l.strip()]
    if args.per_family > 0:
        picked, cnt = [], Counter()
        for c in cases:
            if cnt[c["task"]] < args.per_family:
                picked.append(c)
                cnt[c["task"]] += 1
        cases = picked
    cases_by_id = {c["id"]: c for c in cases}
    os.makedirs(args.out_dir, exist_ok=True)
    raw_path = os.path.join(args.out_dir, "raw.jsonl")
    ident = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             "cases": os.path.relpath(args.cases, ROOT).replace("\\", "/"),
             "cases_sha256": sha256_file(args.cases),
             "runner_sha256": sha256_file(os.path.abspath(__file__)),
             "contract_sha256": sha256_text(C.SYSTEM),
             "n_selected": len(cases),
             "gpu": subprocess.check_output(
                 ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                  "--format=csv,noheader"], text=True, errors="replace").strip(),
             **model_identity(args.model)}
    run_id = sha256_text(json.dumps({k: ident[k] for k in
                                     ("weight_blob_sha256", "cases_sha256", "runner_sha256",
                                      "contract_sha256", "n_selected")}, sort_keys=True))[:16]
    ident["run_id"] = run_id
    json.dump(ident, open(os.path.join(args.out_dir, "identity.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    done = set()
    if os.path.exists(raw_path):
        for line in open(raw_path, encoding="utf-8"):
            try:
                done.add(json.loads(line)["case_id"])
            except Exception:
                pass
    mode = "a" if done else "w"
    with open(raw_path, mode, encoding="utf-8") as f:
        for i, c in enumerate(cases, 1):
            if c["id"] in done:
                continue
            if not ensure_server():
                raise SystemExit(f"Ollama 无法启动，停在第 {i}/{len(cases)} 例")
            obj = call(args.model, c["prompt"], args.timeout, args.num_ctx, args.num_gpu,
                       args.num_batch, args.num_predict, args.keep_alive)
            if obj.get("_error") or not obj.get("response"):
                if ensure_server(restart=True):
                    obj = call(args.model, c["prompt"], args.timeout, args.num_ctx, args.num_gpu,
                               args.num_batch, args.num_predict, args.keep_alive)
            raw = obj.get("response") or ""
            raw_obj = E.extract_json(raw)
            ok, fmt, miss = E.judge(c["task"], c["expected"], raw_obj) if raw_obj is not None else (False, False, ["<parse_fail>"])
            rec = {"case_id": c["id"], "task": c["task"], "prompt": c["prompt"],
                   "expected": c["expected"], "raw": raw, "pass": ok, "fmt": fmt,
                   "miss": miss, "sec": obj.get("_sec"), "error": obj.get("_error"),
                   "eval_count": obj.get("eval_count"), "eval_duration_ns": obj.get("eval_duration"),
                   "prompt_eval_count": obj.get("prompt_eval_count"),
                   "served_model": obj.get("model")}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i:3d}/{len(cases)}] {c['id']:<14} {c['task']:<14} "
                  f"{'PASS' if ok else 'FAIL'} {obj.get('_sec')}s err={obj.get('_error')}", flush=True)

    summary = summarize(raw_path, cases_by_id, ident)
    summary_path = os.path.join(args.out_dir, "summary.json")
    json.dump(summary, open(summary_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    seal = {"run_id": run_id, "raw_sha256": sha256_file(raw_path),
            "summary_sha256": sha256_file(summary_path),
            "recomputed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "valid": summary["overall"]["valid"], "n": summary["overall"]["n"]}
    json.dump(seal, open(os.path.join(args.out_dir, "SEAL.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    o = summary["overall"]
    print(f"\n=== {ident['run_id']} n={o['n']} 严格通过 {o['pass']}/{o['n']} "
          f"= {o['pass_rate']*100:.1f}% Wilson95 {o['wilson95']} | "
          f"transport {o['transport_rate']*100:.1f}% | valid={o['valid']}")
    print(f"数值字段 {o['num_fields_correct']}/{o['num_fields_expected']} | "
          f"文本 {o['text_fields_correct']}/{o['text_fields_expected']} | "
          f"闸门 {o['gate_fields_correct']}/{o['gate_fields_expected']} | "
          f"宣称≠参数 {o['claim_mismatch_fields']}/{o['claim_checked_fields']}")
    print(f"[ok] {args.out_dir}")


if __name__ == "__main__":
    main()
