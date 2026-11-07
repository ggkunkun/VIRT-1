# -*- coding: utf-8 -*-
"""Build the Virtu text-capability SFT corpus (Day 1 of the cloud plan).

Outputs a ShareGPT ``messages`` corpus that ``train_virtu.py`` can consume
directly. Tool-call corpora are intentionally excluded: ``train_virtu.py`` only
reads the first user/assistant ``content`` and would skip ``tool_calls``. The
existing ``virtu-toolcall`` specialist stays separate.

Sources: existing six-software / parametric / drawing-chain / chat corpora plus
deterministic formula gold (n, Vf, MRR, T) and missing-parameter refusals.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sys
import time
from pathlib import Path

from tokenizers import Tokenizer

try:
    from knowledge_reasoning_seed import build_knowledge_reasoning
except ImportError:  # when imported as scripts.build_fix_text_corpus
    from scripts.knowledge_reasoning_seed import build_knowledge_reasoning

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "train" / "virtu_fix_v1"
TRAIN_DIR = OUT_DIR / "train"
REPORT_DIR = OUT_DIR / "reports"
OUT_JSONL = TRAIN_DIR / "virtu_fix_text_sft_v1.jsonl"
MANIFEST = OUT_DIR / "virtu_fix_text_sft_v1.manifest.json"
TOKENIZER_PATH = ROOT / "checkpoints" / "_base_qwen3_8b" / "tokenizer.json"
MAX_LEN = 2048
SEED = 1234

SYSTEM = ("你是 Virtu 工业级 CAD/CAM/CNC 与数控编程专家。回答要给出可执行步骤、"
          "公式、单位与必要的边界说明，不编造未执行的验证结论。")
FORMULA_SYSTEM = ("你是 Virtu 工业级 CAD/CAM/CNC 与数控编程专家。计算题必须写出公式、"
                  "代入过程和带单位的结果；缺少必要参数时要反问，不得臆造数值。")

FAKE_MARKERS = ("100% PASS", "沙箱仿真校验", "全部通过", "已验证通过")

SOURCES = [
    ("master_six", "damodel_cad_cam_tuning/dataset/master_cad_cam_six_software_train.jsonl", 1200),
    ("wish_parametric", "damodel_cad_cam_tuning/dataset/wish_parametric_train.jsonl", 800),
    ("comprehensive", "damodel_cad_cam_tuning/dataset/comprehensive_wish_cad_cam_sft_1200.jsonl", 500),
    ("drawing_chain", "data/virtu_drawing_to_machining_chain_train.jsonl", 700),
    ("turing_chat", "data/processed/turing_conversational_master_train.jsonl", 111),
]


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def sample_key(system: str, user: str, assistant: str) -> str:
    raw = "\x1f".join((norm_text(system), norm_text(user), norm_text(assistant)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_messages(item: dict):
    """Return (system, user, assistant) for text-only SFT, or None."""
    if isinstance(item.get("messages"), list) and item["messages"]:
        msgs = item["messages"]
        system = next((m.get("content") for m in msgs
                       if m.get("role") == "system" and isinstance(m.get("content"), str)), SYSTEM)
        user = next((m.get("content") for m in msgs
                     if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        assistant = next((m.get("content") for m in msgs
                          if m.get("role") == "assistant"
                          and isinstance(m.get("content"), str)
                          and m.get("content").strip()), "")
        if not user.strip() or not assistant.strip():
            return None
        return system.strip(), user.strip(), assistant.strip()
    if item.get("instruction"):
        user = item.get("instruction", "")
        if item.get("input"):
            user += "\n【输入参数与背景】: " + item["input"]
        assistant = item.get("output", "")
        if not user.strip() or not assistant.strip():
            return None
        return SYSTEM, user.strip(), assistant.strip()
    return None


def load_source(name: str, rel: str, cap: int, seen: set, stats: dict):
    path = ROOT / rel
    kept = []
    read = 0
    dropped = {"missing": 0, "duplicate": 0, "fake_claim": 0, "format": 0}
    if not path.exists():
        stats[name] = {"file": rel, "missing": True}
        return kept
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            read += 1
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                dropped["format"] += 1
                continue
            triplet = extract_messages(item)
            if triplet is None:
                dropped["missing"] += 1
                continue
            system, user, assistant = triplet
            if any(marker in assistant for marker in FAKE_MARKERS):
                dropped["fake_claim"] += 1
                continue
            key = sample_key(system, user, assistant)
            if key in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(key)
            kept.append({"messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ], "_source": name})
            if len(kept) >= cap:
                break
    stats[name] = {"file": rel, "read": read, "kept": len(kept), **dropped, "cap": cap}
    return kept


def fmt1(x: float) -> str:
    return f"{x:.1f}"


def fmt2(x: float) -> str:
    return f"{x:.2f}"


def _formula(kind: str, rng: random.Random, style: int, values: tuple):
    if kind == "n":
        vc, d = values
        n = 1000.0 * vc / (math.pi * d)
        user = rng.choice([
            f"工件直径 D={d:g} mm，切削速度 Vc={vc:g} m/min，求主轴转速 n。",
            f"已知 D={d:g} mm、Vc={vc:g} m/min，请计算主轴转速 n（r/min）。",
            f"车削外圆：直径 {d:g} mm，线速度 {vc:g} m/min，按公式求 n。",
        ])
        expr = f"n = 1000×{vc:g}/(π×{d:g})"
        result = f"{fmt1(n)} r/min"
        formula = "n = 1000·Vc/(π·D)"
    elif kind == "vf":
        f, z, n = values
        vf = f * z * n
        user = rng.choice([
            f"铣削参数：每齿进给 f={f:g} mm/z，齿数 z={z}，主轴转速 n={n:g} r/min，求进给速度 Vf。",
            f"已知 f={f:g} mm/z、z={z}、n={n:g} r/min，请计算 Vf（mm/min）。",
        ])
        expr = f"Vf = {f:g}×{z}×{n:g}"
        result = f"{fmt1(vf)} mm/min"
        formula = "Vf = f·z·n"
    elif kind == "mrr":
        ap, ae, vf = values
        mrr = ap * ae * vf
        user = rng.choice([
            f"铣削参数：轴向切深 ap={ap:g} mm，径向切宽 ae={ae:g} mm，进给速度 Vf={vf:g} mm/min，求材料去除率 MRR。",
            f"已知 ap={ap:g} mm、ae={ae:g} mm、Vf={vf:g} mm/min，请计算 MRR（mm³/min）。",
        ])
        expr = f"MRR = {ap:g}×{ae:g}×{vf:g}"
        result = f"{fmt1(mrr)} mm³/min"
        formula = "MRR = ap·ae·Vf"
    else:
        length, vf = values
        t = length / vf
        user = rng.choice([
            f"工件行程 L={length:g} mm，进给速度 Vf={vf:g} mm/min，求加工时间 T。",
            f"已知 L={length:g} mm、Vf={vf:g} mm/min，请计算加工时间 T（min）。",
        ])
        expr = f"T = {length:g}/{vf:g}"
        result = f"{fmt2(t)} min（约 {fmt1(t * 60)} s）"
        formula = "T = L/Vf"

    if style == 0:
        assistant = f"{formula}\n{expr} = {result}"
    elif style == 1:
        assistant = (f"使用公式：{formula}\n"
                     f"代入：{expr}\n"
                     f"结果：{result}")
    else:
        assistant = (f"计算依据：{formula}。\n"
                     f"先统一单位，再代入已知量：{expr}。\n"
                     f"结果为 {result}。\n"
                     f"注意：结果按输入有效数字保留；若 Vc、D、f、z 等参数变化，需要重新计算。")
    return {"messages": [
        {"role": "system", "content": FORMULA_SYSTEM},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ], "_source": f"formula_{kind}", "_formula": kind}


def build_formula(count_per_kind: int = 600, refusals: int = 300):
    rng = random.Random(SEED)
    out = []
    seen = set()

    def unique(values):
        if values in seen:
            return False
        seen.add(values)
        return True

    # n: Vc 60..260 step 5, D 6..160; skip the published eval pair (120, 16)
    made = 0
    while made < count_per_kind:
        vc = rng.randrange(60, 265, 5)
        d = rng.randint(6, 160)
        if (vc, d) == (120, 16) or not unique(("n", vc, d)):
            continue
        out.append(_formula("n", rng, made % 3, (vc, d)))
        made += 1

    made = 0
    while made < count_per_kind:
        f = rng.choice([0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5])
        z = rng.randint(2, 8)
        n = rng.randrange(400, 8001, 50)
        if not unique(("vf", f, z, n)):
            continue
        out.append(_formula("vf", rng, made % 3, (f, z, n)))
        made += 1

    made = 0
    while made < count_per_kind:
        ap = rng.choice([0.2, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
        ae = rng.choice([5, 10, 16, 20, 25, 32, 40, 50, 63, 80])
        vf = rng.randrange(100, 2501, 50)
        if not unique(("mrr", ap, ae, vf)):
            continue
        out.append(_formula("mrr", rng, made % 3, (ap, ae, vf)))
        made += 1

    made = 0
    while made < count_per_kind:
        length = rng.choice([20, 25, 40, 50, 60, 75, 80, 100, 120, 150,
                             200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500])
        vf = rng.randrange(100, 2501, 25)
        if not unique(("t", length, vf)):
            continue
        out.append(_formula("t", rng, made % 3, (length, vf)))
        made += 1

    # Missing-parameter refusals (no invented number)
    for i in range(refusals):
        kind = ("n", "vf", "mrr", "t")[i % 4]
        if kind == "n":
            user = "已知切削速度 Vc=180 m/min，求主轴转速 n。"
            answer = "缺少工件直径 D，无法唯一计算主轴转速 n。请补充 D（mm）后我再按 n=1000·Vc/(π·D) 计算。"
        elif kind == "vf":
            user = "已知每齿进给 f=0.15 mm/z、主轴转速 n=1200 r/min，求进给速度 Vf。"
            answer = "缺少齿数 z，无法唯一计算进给速度 Vf。请补充 z 后我再按 Vf=f·z·n 计算。"
        elif kind == "mrr":
            user = "已知轴向切深 ap=2 mm、进给速度 Vf=800 mm/min，求材料去除率 MRR。"
            answer = "缺少径向切宽 ae，无法唯一计算 MRR。请补充 ae（mm）后我再按 MRR=ap·ae·Vf 计算。"
        else:
            user = "已知工件行程 L=500 mm，求加工时间 T。"
            answer = "缺少进给速度 Vf，无法唯一计算加工时间 T。请补充 Vf（mm/min）后我再按 T=L/Vf 计算。"
        out.append({"messages": [
            {"role": "system", "content": FORMULA_SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer},
        ], "_source": "formula_refusal", "_formula": kind})
    return out


def chat_text(system: str, user: str, assistant: str):
    prompt = (f"<|im_start|>system\n{system}<|im_end|>\n"
              f"<|im_start|>user\n{user}<|im_end|>\n"
              f"<|im_start|>assistant\n")
    return prompt, prompt + assistant + "<|im_end|>"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not TOKENIZER_PATH.exists():
        raise SystemExit(f"missing tokenizer: {TOKENIZER_PATH}")
    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))

    seen = set()
    stats = {}
    rows = []
    for name, rel, cap in SOURCES:
        rows.extend(load_source(name, rel, cap, seen, stats))
        print(f"[source] {name}: kept={stats.get(name, {}).get('kept', 0)}", flush=True)

    formula_rows = build_formula()
    print(f"[formula] built={len(formula_rows)}", flush=True)

    kr_rows = build_knowledge_reasoning()
    kr_seen = set()
    deduped = []
    for row in kr_rows:
        msgs = row["messages"]
        key = sample_key(msgs[0]["content"], msgs[1]["content"], msgs[2]["content"])
        if key in seen or key in kr_seen:
            continue
        kr_seen.add(key)
        deduped.append(row)
    kr_rows = deduped
    print(f"[knowledge_reasoning] built={len(kr_rows)}", flush=True)
    rows.extend(kr_rows)
    rows.extend(formula_rows)
    stats["formula"] = {
        "n": sum(1 for r in formula_rows if r["_source"] == "formula_n"),
        "vf": sum(1 for r in formula_rows if r["_source"] == "formula_vf"),
        "mrr": sum(1 for r in formula_rows if r["_source"] == "formula_mrr"),
        "t": sum(1 for r in formula_rows if r["_source"] == "formula_t"),
        "refusal": sum(1 for r in formula_rows if r["_source"] == "formula_refusal"),
    }
    stats["knowledge_reasoning"] = {
        "knowledge": sum(1 for r in kr_rows if r["_source"] == "knowledge"),
        **{k: sum(1 for r in kr_rows if r["_source"] == k) for k in (
            "reasoning_multi_step", "reasoning_tolerance", "reasoning_taylor",
            "reasoning_cycle_time", "reasoning_roughness")},
    }

    random.Random(SEED).shuffle(rows)

    token_rows = []
    truncated = 0
    prompt_total = answer_total = full_total = capped_total = 0
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for row in rows:
            msgs = row["messages"]
            system = msgs[0]["content"]
            user = msgs[1]["content"]
            assistant = msgs[2]["content"]
            prompt, full = chat_text(system, user, assistant)
            p_ids = tokenizer.encode(prompt, add_special_tokens=False).ids
            f_ids = tokenizer.encode(full, add_special_tokens=False).ids
            a_ids = tokenizer.encode(assistant, add_special_tokens=False).ids
            capped = min(len(f_ids), MAX_LEN)
            if len(f_ids) > MAX_LEN:
                truncated += 1
            prompt_total += len(p_ids)
            answer_total += len(a_ids)
            full_total += len(f_ids)
            capped_total += capped
            token_rows.append((len(f_ids), len(p_ids), len(a_ids)))
            f.write(json.dumps({"messages": msgs, "_source": row.get("_source")},
                               ensure_ascii=False) + "\n")

    def pct(values, q):
        values = sorted(values)
        if not values:
            return 0
        idx = min(len(values) - 1, int(round(q * (len(values) - 1))))
        return values[idx]

    token_rows.sort()
    full_lengths = [x[0] for x in token_rows]
    total = len(rows)
    sha = hashlib.sha256(OUT_JSONL.read_bytes()).hexdigest()
    manifest = {
        "version": "virtu_fix_text_sft_v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": SEED,
        "format": "ShareGPT messages; train_virtu.py compatible",
        "toolcall_strategy": "excluded; keep the existing virtu-toolcall specialist",
        "max_len": MAX_LEN,
        "total": total,
        "sources": stats,
        "tokens": {
            "full_total": full_total,
            "capped_total": capped_total,
            "prompt_total": prompt_total,
            "answer_total": answer_total,
            "p50": pct(full_lengths, 0.50),
            "p90": pct(full_lengths, 0.90),
            "p99": pct(full_lengths, 0.99),
            "max": max(full_lengths) if full_lengths else 0,
            "truncated": truncated,
        },
        "sha256": sha,
        "eval_overlap": "run virtu_eval/contamination_check.py; see the .clean file",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "sources"},
                     ensure_ascii=False, indent=2))
    print("[sources]")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"[out] {OUT_JSONL}")
    print(f"[manifest] {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
