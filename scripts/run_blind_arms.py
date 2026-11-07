# -*- coding: utf-8 -*-
r"""
run_blind_arms.py — Virtu 合并 A/B 全链编排（等合并→完整性门→转GGUF→注册arm→资源闸→盲测→汇总）

arm 设计（唯一变量=合并配方，基座/量化/题集/判分/解码参数全部固定）：
  base    Qwen3-8B 裸基座，不挂任何 LoRA
  single  只挂 virtu_cad_cam_production_lora（专才）
  delta5  5 个 LoRA 干净任务向量求和  delta_w = sum_i w_i * s_i * (B_i @ A_i)
  lin5    同 5 个 LoRA 走 peft linear（含 i!=j 交叉项）

判分两条口径同时出：
  keyword  = 远程 run_blind_test_evaluator.evaluate_response 原函数（ast 抠出，不加载 torch）
  fidelity = prompt 里带单位锚定的尺寸是否出现在回答里 + 回答中凭空出现的尺寸数

用法：
  python scripts/run_blind_arms.py                 # 跑全链
  python scripts/run_blind_arms.py --only prep     # 只做题集渲染
  python scripts/run_blind_arms.py --only run      # 只做盲测（产物已就绪）
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import glob
import json
import os
import re
import statistics as st
import struct
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CKPT = os.path.join(ROOT, "checkpoints")
WORK = os.path.join(ROOT, "work")
CASES_JSON = os.path.join(ROOT, "benchmarks", "cad_cam_blind_test_results.json")
EVALUATOR = os.path.join(ROOT, "scripts", "run_blind_test_evaluator.py")
MERGE_LOG = os.path.join(WORK, "_eval_merge_chain.log")
PROMPTS = os.path.join(WORK, "_eval_prompts.jsonl")
OLLAMA = "http://127.0.0.1:11434/api/generate"

ARMS = [
    {"arm": "base", "src": "_base_qwen3_8b", "gguf": "_eval_base-q4_0.gguf", "name": "virtu-eval:base"},
    {"arm": "single", "src": "_eval_single", "gguf": "_eval_single-q4_0.gguf", "name": "virtu-eval:single"},
    {"arm": "delta5", "src": "_eval_delta5", "gguf": "_eval_delta5-q4_0.gguf", "name": "virtu-eval:delta5"},
    {"arm": "lin5", "src": "_eval_lin5", "gguf": "_eval_lin5-q4_0.gguf", "name": "virtu-eval:lin5"},
]

OPEN_TOK, CLOSE_TOK = chr(60) + chr(124), chr(124) + chr(62)
IM_START, IM_END = OPEN_TOK + "im_start" + CLOSE_TOK, OPEN_TOK + "im_end" + CLOSE_TOK
SYSTEM = "你是一名精通 SOLIDWORKS/NX/AutoCAD/Vericut/CIMCO/斯沃的 CAM 编程与参数化建模工程师。"

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import run_local_blind_ollama as LB  # noqa: E402  torch-free helpers (dims/fidelity/build_cases)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(os.path.join(WORK, "_eval_chain2.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_grader():
    src = open(EVALUATOR, encoding="utf-8").read()
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "evaluate_response")
    ns = {"re": re, "json": json}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 "<grader>", "exec"), ns)
    return ns["evaluate_response"]


class MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_ram_mb():
    m = MemStatus()
    m.dwLength = ctypes.sizeof(MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1048576.0


def gpu_used_mib():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return 99999


def wait_merges(max_wait=4 * 3600):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        txt = open(MERGE_LOG, encoding="utf-8", errors="replace").read() if os.path.exists(MERGE_LOG) else ""
        if "CHAIN_END" in txt:
            log(f"merge chain finished after {(time.time()-t0)/60:.1f} min")
            return True
        log(f"waiting merges... gpu={gpu_used_mib()}MiB ram={free_ram_mb():.0f}MB")
        time.sleep(120)
    log("GATE_TIMEOUT merges")
    return False


def shard_tensor_names(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        h = json.loads(f.read(n))
    return {k: v for k, v in h.items() if k != "__metadata__"}


def data_start(path, hdr):
    """safetensors 数据段起点不保证对齐；用 文件大小 - 全部张量字节数 反推，最稳。"""
    total = sum(v["data_offsets"][1] - v["data_offsets"][0] for v in hdr.values())
    return os.path.getsize(path) - total


def head_vals(path, key, hdr=None, n=96):
    import numpy as np
    hdr = hdr or shard_tensor_names(path)
    off = hdr[key]["data_offsets"][0]
    with open(path, "rb") as f:
        f.seek(data_start(path, hdr) + off)
        raw = f.read(n * 2)
    return list(np.frombuffer(raw, dtype=np.uint16))


def integrity_gate():
    """合并产物必须 5 分片、键集/尺寸与基座一致；
    负对照 = embed_tokens 必须逐位不变（它不是 LoRA target）；
    正对照 = 抽样 target 张量必须有改动。"""
    ok = True
    base = os.path.join(CKPT, "_base_qwen3_8b")
    base_idx = json.load(open(os.path.join(base, "model.safetensors.index.json"), encoding="utf-8"))
    targets = [k for k in base_idx["weight_map"] if re.search(r"\.(q|k|v|o|gate|up|down)_proj\.weight$", k)]
    emb = "model.embed_tokens.weight"
    for a in ARMS:
        if a["arm"] == "base":
            continue
        d = os.path.join(CKPT, a["src"])
        shards = sorted(glob.glob(os.path.join(d, "model-*.safetensors")))
        if len(shards) != 5:
            log(f"  [GATE FAIL] {a['arm']}: shards={len(shards)} (需要 5)")
            ok = False
            continue
        idx = json.load(open(os.path.join(d, "model.safetensors.index.json"), encoding="utf-8"))
        if set(idx["weight_map"]) != set(base_idx["weight_map"]):
            log(f"  [GATE FAIL] {a['arm']}: 键集与基座不一致")
            ok = False
            continue
        if idx["metadata"].get("total_size") != base_idx["metadata"].get("total_size"):
            log(f"  [GATE FAIL] {a['arm']}: total_size 与基座不等")
            ok = False
            continue
        hc = {}

        def hdr_cached(p):
            if p not in hc:
                hc[p] = shard_tensor_names(p)
            return hc[p]

        emb_same = head_vals(os.path.join(base, base_idx["weight_map"][emb]), emb, hdr_cached(os.path.join(base, base_idx["weight_map"][emb]))) == \
            head_vals(os.path.join(d, idx["weight_map"][emb]), emb, hdr_cached(os.path.join(d, idx["weight_map"][emb])))
        step = max(1, len(targets) // 40)
        changed = same = 0
        for key in targets[::step]:
            sp, bp = idx["weight_map"][key], base_idx["weight_map"][key]
            if sp != bp:
                continue
            hs, hb = hdr_cached(os.path.join(d, sp)), hdr_cached(os.path.join(base, sp))
            if head_vals(os.path.join(base, sp), key, hb) == head_vals(os.path.join(d, sp), key, hs):
                same += 1
            else:
                changed += 1
        rate = changed / max(1, changed + same)
        log(f"  [GATE] {a['arm']}: 抽样 target changed={changed} unchanged={same} (rate={rate:.2f}) | embed 负对照={'一致' if emb_same else '被改动!'}")
        if not emb_same or rate < 0.9:
            log(f"  [GATE FAIL] {a['arm']}: 合并未真正落到权重上")
            ok = False
    return ok


def prep_prompts():
    cases = LB.build_cases()
    tmpl = None
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(os.path.join(CKPT, "_base_qwen3_8b"), trust_remote_code=False)
        if getattr(tok, "chat_template", None):
            tmpl = tok
    except Exception as e:
        log(f"  [prep] transformers 不可用: {repr(e)[:100]} → 手工 ChatML")
    with open(PROMPTS, "w", encoding="utf-8") as f:
        for c in cases:
            if tmpl is not None:
                try:
                    text = tmpl.apply_chat_template(
                        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": c["prompt"]}],
                        tokenize=False, add_generation_prompt=True)
                    mode = "hf_template"
                except Exception:
                    text, mode = manual(c["prompt"]), "chatml"
            else:
                text, mode = manual(c["prompt"]), "chatml"
            f.write(json.dumps({"test_id": c["test_id"], "software": c["software"],
                                "prompt": c["prompt"], "rendered": text, "render_mode": mode,
                                "ref_score": c["ref_score"],
                                "n_dims": len(LB.dims(c["prompt"], c["software"]))},
                               ensure_ascii=False) + "\n")
    log(f"  [prep] wrote {PROMPTS} render_mode={mode}")
    return mode


def manual(prompt):
    return (f"{IM_START}system\n{SYSTEM}{IM_END}\n"
            f"{IM_START}user\n{prompt}{IM_END}\n{IM_START}assistant\n")


def run(cmd, timeout=None):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p, time.time() - t0


def convert_and_register(only_arm=None):
    for a in ARMS:
        if only_arm and a["arm"] != only_arm:
            continue
        gguf = os.path.join(CKPT, a["gguf"])
        if not os.path.exists(gguf):
            if os.path.exists(gguf + ".part"):
                os.remove(gguf + ".part")
            p, dt = run([sys.executable, "-u", os.path.join(ROOT, "scripts", "hf_to_gguf_numpy.py"),
                         "--model", os.path.join(CKPT, a["src"]), "--out", gguf], timeout=7200)
            log(f"  [convert] {a['arm']} rc={p.returncode} {dt/60:.1f}min errtail={p.stderr[-200:] if p.returncode else ''}")
            if p.returncode != 0 or not os.path.exists(gguf):
                log(f"  [GATE FAIL] convert {a['arm']}")
                return False
        else:
            log(f"  [convert] {a['arm']} 已存在 {os.path.getsize(gguf)/1e9:.2f}GB")
        mf = os.path.join(WORK, f"Modelfile.{a['arm']}")
        with open(mf, "w", encoding="utf-8") as f:
            f.write("FROM " + gguf.replace("\\", "/") + "\n")
            f.write("TEMPLATE {{ .Prompt }}\n")
            f.write("PARAMETER num_ctx 4096\n")
            f.write("PARAMETER temperature 0\n")
        p, dt = run(["ollama", "create", "-f", mf, a["name"]], timeout=1800)
        log(f"  [ollama create] {a['name']} rc={p.returncode} {dt/60:.1f}min {p.stdout.strip()[-80:]}{p.stderr.strip()[-150:]}")
        if p.returncode != 0:
            return False
    return True


def resource_gate(need_ram_mb=4200, need_gpu_free_mib=4000, max_wait=3 * 3600):
    t0 = time.time()
    streak = 0
    while time.time() - t0 < max_wait:
        used, ram = gpu_used_mib(), free_ram_mb()
        if used <= need_gpu_free_mib and ram >= need_ram_mb:
            streak += 1
            log(f"  [resgate] ok {streak}/3 gpu_used={used}MiB ram_free={ram:.0f}MB")
            if streak >= 3:
                return True
        else:
            streak = 0
            log(f"  [resgate] busy gpu_used={used}MiB ram_free={ram:.0f}MB (需 used<= {need_gpu_free_mib} 且 ram>={need_ram_mb})")
        time.sleep(60)
    log("GATE_TIMEOUT resources")
    return False


def load_prompts():
    rows = []
    with open(PROMPTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def done_ids(path):
    ids = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                ids.add(json.loads(line)["test_id"])
            except Exception:
                pass
    return ids


def gen(name, text, num_predict=900, num_ctx=4096, timeout=1800):
    body = json.dumps({"model": name, "prompt": text, "raw": True, "stream": False,
                       "options": {"temperature": 0, "top_p": 1.0, "num_predict": num_predict,
                                   "num_ctx": num_ctx, "seed": 1234}}).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("response", ""), d.get("eval_count") or 0, time.time() - t0


def run_arm(a, grade, limit=0, smoke=False):
    out = os.path.join(WORK, f"_eval_blind_{a['arm']}.jsonl")
    rows = load_prompts()
    if smoke:
        rows = rows[:1]
    skip = set() if smoke else done_ids(out)
    todo = [c for c in rows if c["test_id"] not in skip]
    if limit:
        todo = todo[:limit]
    log(f"  [run {a['arm']}] todo={len(todo)} model={a['name']}")
    mode = "a" if not smoke else "w"
    with open(out, mode, encoding="utf-8") as f:
        for i, c in enumerate(todo, 1):
            try:
                resp, ntok, dt = gen(a["name"], c["rendered"])
            except Exception as e:
                log(f"    {c['test_id']} ERROR {repr(e)[:140]}")
                time.sleep(10)
                continue
            fid, nfab, fab = LB.fidelity(c["prompt"], c["software"], resp)
            g = grade(c["software"], c["prompt"], resp)
            rec = {"arm": a["arm"], "test_id": c["test_id"], "software": c["software"],
                   "keyword_score": g.get("score"), "keyword_passed": g.get("passed"),
                   "keyword_errors": g.get("errors", []), "ref_score": c["ref_score"],
                   "n_dims": c["n_dims"], "fidelity": round(fid, 4), "fabricated": nfab,
                   "fabricated_values": fab, "chars": len(resp), "tokens": ntok,
                   "sec": round(dt, 1), "tok_per_s": round(ntok / dt, 2) if dt else None,
                   "response_full": resp}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            if smoke or i % 6 == 0 or i == len(todo):
                log(f"    [{a['arm']}] {i}/{len(todo)} {c['test_id']} kw={rec['keyword_score']} "
                    f"fid={fid:.2f} fab={nfab} tps={rec['tok_per_s']}")
    return out


def summarize():
    per = {}
    for a in ARMS:
        p = os.path.join(WORK, f"_eval_blind_{a['arm']}.jsonl")
        if os.path.exists(p):
            per[a["arm"]] = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    if not per:
        log("[summary] 无数据")
        return
    keys = list(per)
    tbl, md = [], [""
                   "# Virtu 合并 A/B 盲测结果", "",
                   f"生成时间 {time.strftime('%Y-%m-%d %H:%M')} | arms={keys} | 题集=36 道 CAD/CAM 盲测 | 解码 temperature=0 seed=1234", ""]
    md.append("| arm | 题数 | keyword 均分 | keyword 通过率 | 尺寸保真(仅可判题) | 保真<1 题数 | 幻觉尺寸数 | 中位 tok/s |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for k in keys:
        rs = per[k]
        fjud = [r for r in rs if r["n_dims"] > 0]
        row = {"n": len(rs),
               "kw_mean": round(st.mean([r["keyword_score"] for r in rs]), 2),
               "kw_pass": round(100 * sum(1 for r in rs if r["keyword_passed"]) / len(rs), 1),
               "fid_mean": round(st.mean([r["fidelity"] for r in fjud]), 4) if fjud else None,
               "fid_judged": len(fjud),
               "fid_bad": sum(1 for r in fjud if r["fidelity"] < 0.999),
               "fab_total": sum(r["fabricated"] for r in rs),
               "tps_median": round(st.median([r["tok_per_s"] for r in rs if r["tok_per_s"]]), 2),
               "sec_total": round(sum(r["sec"] for r in rs) / 60, 1)}
        tbl.append({"arm": k, **row})
        md.append(f"| {k} | {row['n']} | {row['kw_mean']} | {row['kw_pass']}% | {row['fid_mean']} "
                  f"({row['fid_judged']}/{row['n']} 题可判) | {row['fid_bad']} | {row['fab_total']} | {row['tps_median']} |")
    md += ["", "## 逐题相对 base 的差值", "",
           "| test_id | " + " | ".join(keys) + " |", "|---|" + "---:|" * len(keys)]
    ids = sorted({r["test_id"] for k in keys for r in per[k]})
    idx = {k: {r["test_id"]: r for r in per[k]} for k in keys}
    for t in ids:
        md.append(f"| {t} | " + " | ".join(
            (f"{idx[k][t]['keyword_score']}/{idx[k][t]['fidelity']:.2f}" if t in idx[k] else "-") for k in keys) + " |")
    json.dump({"arms": tbl}, open(os.path.join(WORK, "_eval_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(WORK, "_eval_summary.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    log("[summary] wrote work/_eval_summary.json + _eval_summary.md")
    for r in tbl:
        log(f"  {r['arm']}: kw={r['kw_mean']} pass={r['kw_pass']}% fid={r['fid_mean']} "
            f"bad={r['fid_bad']} fab={r['fab_total']} tps={r['tps_median']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, choices=["wait", "gate", "prep", "convert", "resgate", "run", "summary"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-resgate", action="store_true")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    steps = ["wait", "gate", "prep", "convert", "resgate", "run", "summary"] if not args.only else [args.only]
    for s in steps:
        if s == "wait":
            if not wait_merges():
                return 1
        elif s == "gate":
            if not integrity_gate():
                log("[STOP] 完整性门未过，不进盲测")
                return 1
        elif s == "prep":
            prep_prompts()
        elif s == "convert":
            if not convert_and_register():
                return 1
        elif s == "resgate":
            if not args.skip_resgate and not resource_gate():
                return 1
        elif s == "run":
            grade = load_grader()
            for a in ARMS:
                if not convert_and_register(a["arm"]):
                    continue
                run_arm(a, grade, limit=args.limit)
        elif s == "summary":
            summarize()
    return 0


if __name__ == "__main__":
    sys.exit(main())
