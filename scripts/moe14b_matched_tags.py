# -*- coding: utf-8 -*-
"""
scripts/moe14b_matched_tags.py — 造出「只差路由权重」的两臂，让语义门控第一次可被判据评估

问题：现存的 `virtu-moe-14b:fast`（随机门）与 `virtu-moe-14b:semantic`（正交门）在 8 处不一致
（template source、system 文本、num_ctx、num_gpu、presence_penalty、min_p、repeat_last_n、stop 列表），
所以任何能力差都无法归因给路由——这正是「语义门控重构」跑了一天却拿不出一条能力腿的原因。

做法：从参照标签 /api/show 取回它实际生效的 template 文本 + system 文本 + parameters，
原样写进两个新 Modelfile，只把 FROM 换成各自的 GGUF、num_ctx/num_gpu 换成网格实测最优值，
标签名按 GGUF 内容哈希（宪法第 2 条：内容寻址，不用 latest）。

产物闸（任一不过即拒绝出数并返回非零）：
  G-1 两臂 template 逐字节相同
  G-2 两臂 system 逐字节相同
  G-3 两臂 parameters 字典相同（含 num_ctx/num_gpu）
  G-4 两臂 general.parameter_count 相同且 = 13,626,848,256
  G-5 两臂 GGUF sha256 不同（否则是同一份权重，比较无意义）

用法：
  python scripts/moe14b_matched_tags.py --reference virtu-moe-14b:fast \
      --num-ctx 4096 --num-gpu 22
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
EXPECT_PARAMS = 13626848256


def _no_proxy():
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(k, None)


def show(model):
    _no_proxy()
    req = urllib.request.Request(f"{BASE}/api/show", data=json.dumps({"model": model}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_parameters(text):
    """/api/show parameters is a fixed-column text block; multiple identical keys become lists."""
    d = {}
    for line in (text or "").splitlines():
        m = re.match(r"^(\S+)\s{2,}(.*)$", line.rstrip())
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif re.fullmatch(r"-?\d+", v):
            v = int(v)
        elif re.fullmatch(r"-?\d*\.\d+", v):
            v = float(v)
        if k in d:
            d[k] = d[k] if isinstance(d[k], list) else [d[k], v]
        else:
            d[k] = v
    return d


def sha8(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def build_modelfile(path, gguf, system, params):
    """No TEMPLATE line: re-supplying Ollama's *converted* Go template double-converts it
    (observed: `template error: malformed character constant`). Each arm instead resolves the
    chat template embedded in its own GGUF, which gate G-0 proves byte-identical up front."""
    lines = [f"FROM {gguf}"]
    for k, v in params.items():
        vals = v if isinstance(v, list) else [v]
        for x in vals:
            xs = f'"{x}"' if isinstance(x, str) else str(x)
            lines.append(f"PARAMETER {k} {xs}")
    lines.append('SYSTEM """' + system + '"""')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def evaluate_gates(arms, expect_params=EXPECT_PARAMS):
    """Return (gates, failures). Kept pure so the falsification tests can feed it bad samples
    without touching Ollama. An empty/absent difference is NEVER treated as passing."""
    tags = sorted(arms)
    if len(tags) < 2:
        return {"G0_two_arms": False}, ["G-0 fewer than two arms — nothing is being compared"]
    tpl = {t: hashlib.sha256(arms[t]["template"].encode()).hexdigest()[:16] for t in tags}
    sys_ = {t: hashlib.sha256(arms[t]["system"].encode()).hexdigest()[:16] for t in tags}
    ref_p = arms[tags[0]]["parameters"]
    kvs = [arms[t].get("kv_section_sha256") for t in tags]
    gates = {
        "G0_kv_sections_identical": bool(all(kvs)) and len(set(kvs)) == 1,
        "G1_template_equal": len(set(tpl.values())) == 1,
        "G2_system_equal": len(set(sys_.values())) == 1,
        "G3_parameters_equal": not any(arms[t]["parameters"] != ref_p for t in tags),
        "G4_parameter_count_equal_expected": all(arms[t]["parameter_count"] == expect_params for t in tags),
        "G5_gguf_bytes_differ": len({arms[t]["gguf_sha256"] for t in tags}) == len(tags),
    }
    failures = []
    if not gates["G0_kv_sections_identical"]:
        failures.append("G-0 the two files' metadata/tokenizer sections differ — the arms are not "
                        "comparable as a weights-only experiment "
                        + json.dumps({t: (kvs[i] or "MISSING")[:16] for i, t in enumerate(tags)}))
    if not gates["G1_template_equal"]:
        failures.append(f"G-1 template differs: {tpl}")
    if not gates["G2_system_equal"]:
        failures.append(f"G-2 system differs: {sys_}")
    if not gates["G3_parameters_equal"]:
        failures.append("G-3 parameters dict differs: "
                        + json.dumps({t: arms[t]["parameters"] for t in tags}, ensure_ascii=False))
    if not gates["G4_parameter_count_equal_expected"]:
        failures.append(f"G-4 parameter_count not {expect_params}: "
                        + json.dumps({t: arms[t]["parameter_count"] for t in tags}))
    if not gates["G5_gguf_bytes_differ"]:
        failures.append("G-5 the arms are the same bytes — the comparison would be vacuous")
    return gates, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default="virtu-moe-14b:fast")
    ap.add_argument("--gguf", nargs="*", default=[
        os.path.join(ROOT, "checkpoints", "virtu-moe-14b-q4_k_m.gguf"),
        os.path.join(ROOT, "checkpoints", "virtu-moe-14b-semantic-q4_k_m.gguf")])
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-gpu", type=int, default=22)
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_matched_tags.json"))
    args = ap.parse_args()

    if len(args.gguf) < 2:
        print("[FATAL] need at least two ggufs to match")
        return 2

    # G-0: the two weight files must be identical outside the gate tensors. The cheap, decisive
    # proxy is the whole kv/metadata section (chat template, tokenizer, vocab, all geometry).
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from moe14b_gate_forensics import read_header, resolve_artifact  # noqa: E402

    def kv_sha(path):
        kv = read_header(path)[0]
        blob = json.dumps(kv, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest(), hashlib.sha256(
            (kv.get("tokenizer.chat_template") or "").encode("utf-8")).hexdigest()

    args.gguf = []
    for g in args.gguf:
        try:
            path, _ = resolve_artifact(g)
        except FileNotFoundError as exc:
            print(f"[FATAL] {exc}")
            return 2
        args.gguf.append(os.path.abspath(path))
    kv0 = {g: kv_sha(g) for g in args.gguf}
    g0 = len({v[0] for v in kv0.values()}) == 1
    print(f"[G-0] kv sections identical across the {len(args.gguf)} weight files: {g0}")
    for g, (all_sha, tpl_sha) in kv0.items():
        print(f"      {os.path.basename(g)}  kv_sha={all_sha[:16]} chat_template_sha={tpl_sha[:16]}")

    ref = show(args.reference)
    template, system = ref.get("template") or "", ref.get("system") or ""
    if not template or not system:
        print("[FATAL] reference has empty template/system; refusing to build matched arms from it")
        return 2
    ref_params = parse_parameters(ref.get("parameters"))
    print(f"[ref] {args.reference}: template {len(template)} chars, system {len(system)} chars, "
          f"parameters={ref_params}")

    arms = {}
    for g in args.gguf:
        if not os.path.exists(g):
            print(f"[FATAL] missing gguf: {g}")
            return 2
        digest = sha8(g)
        tag = f"virtu-moe-14b:{digest[:8]}"
        mf = os.path.join(ROOT, "checkpoints", f"Modelfile.matched_{digest[:8]}")
        params = dict(ref_params)
        params["num_ctx"] = args.num_ctx
        params["num_gpu"] = args.num_gpu
        build_modelfile(mf, g, system, params)
        print(f"[create] {tag} <- {os.path.basename(g)} ({digest[:16]}…)", flush=True)
        env = dict(os.environ, OLLAMA_HOST=BASE.replace("http://", ""))
        p = subprocess.run(["ollama", "create", tag, "-f", mf], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        if p.returncode != 0:
            print(f"[FATAL] ollama create failed for {tag}: {p.stderr[-800:]}")
            return 2
        s = show(tag)
        mi = s.get("model_info") or {}
        arms[tag] = {
            "gguf": g, "gguf_sha256": digest, "modelfile": mf,
            "kv_section_sha256": kv0[g][0],
            "template": s.get("template") or "", "template_source": s.get("template_source"),
            "system": s.get("system") or "", "parameters": parse_parameters(s.get("parameters")),
            "parameter_count": mi.get("general.parameter_count"),
            "quantization": (s.get("details") or {}).get("quantization_level"),
            "capabilities": sorted(s.get("capabilities") or []),
        }

    tags = sorted(arms)
    gates, failures = evaluate_gates(arms, EXPECT_PARAMS)
    tpl = {t: hashlib.sha256(arms[t]["template"].encode()).hexdigest()[:16] for t in tags}
    sys_ = {t: hashlib.sha256(arms[t]["system"].encode()).hexdigest()[:16] for t in tags}

    receipt = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured",
        "tool": "scripts/moe14b_matched_tags.py",
        "reference": args.reference,
        "arms": {t: {k: v for k, v in arms[t].items() if k not in ("template", "system")}
                 for t in tags},
        "template_sha256_16": tpl,
        "system_sha256_16": sys_,
        "gates": gates,
        "verdict": "MATCHED" if not failures else "NOT_MATCHED",
        "failures": failures,
        "note": "两臂唯一差异必须是 GGUF 里的 36 个 ffn_gate_inp 张量；"
                "张量级证明见 runs/moe14b_gate_forensics.json（36/435 差异，全部为 gate）",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)

    print(json.dumps({"gates": receipt["gates"], "verdict": receipt["verdict"],
                      "arms": tags, "failures": failures}, indent=2, ensure_ascii=False))
    print(f"[out] {args.out}")
    return 0 if not failures else 4


if __name__ == "__main__":
    sys.exit(main())
