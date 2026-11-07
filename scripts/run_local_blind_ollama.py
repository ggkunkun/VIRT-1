# -*- coding: utf-8 -*-
r"""
run_local_blind_ollama.py — 本机 Ollama 盲测跑测器（多 arm 对比）

与远程 run_blind_test_evaluator.py 的差别：
  - 判分函数直接 import 原文件，不改口径（保证与已发布的 94.4% 可比）
  - 额外加两个原判分器看不见的指标：prompt 尺寸保真率 / 幻觉尺寸数
    （原判分器只查关键字，blind_001 把内孔 16.3mm 写成 14.0mm 仍得 100 分）
  - 贪心解码 temperature=0，同题同参只换模型，避免采样噪声混进 arm 差值
  - 逐题 append-only 落盘，可断点续跑

用法：
  python scripts/run_local_blind_ollama.py --arm delta5 --model virtu-eval:delta5 --limit 1
  python scripts/run_local_blind_ollama.py --arm delta5 --model virtu-eval:delta5
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "benchmarks", "cad_cam_blind_test_results.json")
EVALUATOR = os.path.join(ROOT, "scripts", "run_blind_test_evaluator.py")
BASE_DIR = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
OUT_DIR = os.path.join(ROOT, "work")
OLLAMA = "http://127.0.0.1:11434/api/generate"

IM_START = chr(60) + chr(124) + "im_start" + chr(124) + chr(62)
IM_END = chr(60) + chr(124) + "im_end" + chr(124) + chr(62)

AFTER_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:mm|MM|毫米|MPa|N·m|rpm|RPM|HRC|um|μm|°|度)")
BEFORE_RE = re.compile(r"(?:Φ|φ|直径|外径|内孔|内径|孔径|长度|宽度|厚度|深度|高度|总长|高|长|宽|深|R|r)\s*[=::]?\s*(?<![\d.])(\d+(?:\.\d+)?)")


def load_grader():
    spec = importlib.util.spec_from_file_location("remote_evaluator", EVALUATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate_response


def build_cases():
    d = json.load(open(CASES, encoding="utf-8"))
    out = []
    for c in d["results"]:
        out.append({"test_id": c["test_id"], "software": c["software"], "prompt": c["prompt"],
                    "ref_score": c.get("score"), "ref_passed": c.get("passed")})
    return out


def dims(text, software):
    """抽取带单位锚定的设计尺寸；中文语境下不能用 \\w 做左边界（汉字本身算 \\w）。"""
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
        return 1.0, 0, []
    got = [v for v in need if re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d.])", response)]
    pset = set(need) | set(re.findall(r"\d+(?:\.\d+)?", software or ""))
    fab = sorted({m.group(1) for m in AFTER_RE.finditer(response) if m.group(1) not in pset},
                 key=len)[:8]
    return len(got) / len(need), len(fab), fab


class Prompter:
    """优先用基座 tokenizer 的 chat template，与远程判分口径一致。"""

    def __init__(self):
        self.mode = "chatml"
        self.tok = None
        try:
            from transformers import AutoTokenizer
            self.tok = AutoTokenizer.from_pretrained(BASE_DIR, trust_remote_code=False)
            if getattr(self.tok, "chat_template", None):
                self.mode = "hf_template"
        except Exception as e:
            print("[prompter] tokenizer 不可用，回落手工 ChatML:", repr(e)[:120])

    def render(self, prompt):
        if self.tok is not None and self.mode == "hf_template":
            msgs = [{"role": "system", "content": "你是一名精通 SOLIDWORKS/NX/AutoCAD/Vericut/CIMCO/斯沃的 CAM 编程与参数化建模工程师。"},
                    {"role": "user", "content": prompt}]
            try:
                return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            except Exception:
                pass
        sysmsg = "你是一名精通 SOLIDWORKS/NX/AutoCAD/Vericut/CIMCO/斯沃的 CAM 编程与参数化建模工程师。"
        return (f"{IM_START}system\n{sysmsg}{IM_END}\n{IM_START}user\n{prompt}{IM_END}\n{IM_START}assistant\n")


def generate(model, text, num_predict, num_ctx, timeout=1200):
    body = json.dumps({"model": model, "prompt": text, "raw": True, "stream": False,
                       "options": {"temperature": 0, "top_p": 1.0, "num_predict": num_predict,
                                   "num_ctx": num_ctx, "seed": 1234}}).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    n = d.get("eval_count") or 0
    return d.get("response", ""), n, dt


def done_ids(path):
    ids = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ids.add(json.loads(line)["test_id"])
                except Exception:
                    pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--num-predict", type=int, default=900)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    out_path = os.path.join(OUT_DIR, f"_eval_blind_{args.arm}.jsonl")
    os.makedirs(OUT_DIR, exist_ok=True)
    grade = load_grader()
    prompter = Prompter()
    print(f"[arm={args.arm}] model={args.model} prompter={prompter.mode} out={out_path}")

    cases = build_cases()
    skip = set() if args.no_resume else done_ids(out_path)
    todo = [c for c in cases if c["test_id"] not in skip]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[arm={args.arm}] total={len(cases)} done={len(skip)} todo={len(todo)}")

    with open(out_path, "a", encoding="utf-8") as f:
        for i, c in enumerate(todo, 1):
            text = prompter.render(c["prompt"])
            try:
                resp, n, dt = generate(args.model, text, args.num_predict, args.num_ctx)
            except Exception as e:
                print(f"  {c['test_id']} ERROR {repr(e)[:150]}")
                continue
            g = grade(c["software"], c["prompt"], resp)
            fid, fab_n, fab = fidelity(c["prompt"], c["software"], resp)
            rec = {"arm": args.arm, "test_id": c["test_id"], "software": c["software"],
                   "keyword_score": g.get("score"), "keyword_passed": g.get("passed"),
                   "keyword_errors": g.get("errors", []), "ref_score": c["ref_score"],
                   "fidelity": round(fid, 4), "fabricated_dims": fab_n, "fabricated_values": fab,
                   "chars": len(resp), "tokens": n, "sec": round(dt, 1),
                   "tok_per_s": round(n / dt, 2) if dt > 0 else None,
                   "response_full": resp}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            print(f"  [{i}/{len(todo)}] {c['test_id']} kw={rec['keyword_score']} "
                  f"fid={fid:.2f} fab={fab_n} ref={c['ref_score']} {rec['tok_per_s']} tok/s")
    print(f"[arm={args.arm}] DONE {out_path}")


if __name__ == "__main__":
    main()
