#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 文档级 / 语义路由层 (P1-3, 零训练)
========================================
目标：在不训练任何权重的前提下，把用户查询分流到合适的后端模型，兼顾质量与速度：
      - 快路径 FAST : virtu-dense-merged:q4_0  (稠密 8B Q4_0, ~38 tok/s)  —— P1-2 推荐稠密臂(sum_norm)
      - 难路径 HARD : virtu-moe-14b:fast        (MoE 14B Q4_K_M, ~10 tok/s) —— 质量标杆, 剥离空 <think>

路由依据（零训练，可审计、可复现）：
   1) 强专业关键词白名单：命中任一 -> HARD（高精确，几乎必为 CAD-CAM 专家任务）
    2) 语义质心余弦 margin：bge-m3 将 query 嵌入（1024 维，中文判别力优于 nomic），比较到 expert/general 两类质心的余弦差；
      margin > THRESH -> HARD，否则 FAST（补关键词漏掉的自然语言专业描述，如"怎么让刀具不震"）。

宪法合规：route() 返回的 decision 带完整证据（margin / cos_expert / cos_general / kw_hits / basis），
          可复现、可审计；bench 子命令量化分类准确率。

用法：
   python virtu_router.py route  "怎么用 UG 编一个五轴刀路"
   python virtu_router.py ask    "G71 粗车余量怎么设"
   python virtu_router.py bench  --labeled bench_labeled.json
   python virtu_router.py build  (强制重建质心缓存)
环境变量：
   OLLAMA_BASE   默认 http://127.0.0.1:11434
   ROUTER_THRESH 语义 margin 阈值，默认 0.0
"""
import os
import sys
import json
import time
import argparse
import re
import numpy as np

OLLAMA = os.environ.get("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
EMBED_MODEL = "bge-m3"   # 2026-11-06 升级：中文判别力显著优于 nomic-embed-text（独立集 kNN 0.900->1.000）
HERE = os.path.dirname(os.path.abspath(__file__))
ANCHORS_PATH = os.path.join(HERE, "anchors.json")
CENTROID_PATH = os.path.join(HERE, "anchors_centroids.json")

FAST_MODEL = "virtu-dense-merged:q4_0"   # 快路径：稠密 8B Q4_0, 全 GPU ~38 tok/s
HARD_MODEL = "virtu-moe-14b:fast"        # 难路径：MoE 14B Q4_K_M, 部分 GPU ~10 tok/s
THRESH = float(os.environ.get("ROUTER_THRESH", "0.0"))
# 钉热时长: 让模型在请求间隔保持加载, 避免 Ollama 默认 keep_alive=0 每次卸载。
# 注意: 仅当显存足以同时容纳两模型(>=~13GB)时双模型才能都热; 6GB 开发机仍会跨模型互斥重载。
KEEP_ALIVE = os.environ.get("ROUTER_KEEP_ALIVE", "10m")
# 难路径(MoE)用完即卸载: 让稠密在非常专业时段回归 GPU 热, 压低 6GB 机常态延迟。
# 依据: 6GB 显卡装不下双模型同驻, Ollama 跨模型请求必互斥重载; 故 MoE 不钉热,
#       避免持续挤占稠密 -> 通用为主流量(常态)保持 dense 零抖动。
MOE_KEEP_ALIVE = os.environ.get("ROUTER_MOE_KEEP_ALIVE", "0")
# 难路径(MoE)用完即卸载(默认 0): 让稠密在非常专业时段回归 GPU 热, 压低 6GB 机常态延迟。
# 说明: 设为 >0 可让 MoE 保持热窗口(连续专业零重载), 但 6GB 单 GPU 上会与稠密互斥,
#        且快速 ka 切换易触发 Ollama 500; 故默认 0, 采用 P1-3.1 的"惰性卸载"稳态策略。

# 生成参数（按模型分别最优，来自 P1-实验实测）
# 稠密 8B 全上 GPU 最快。MoE 14B 在 6GB 上装不下，卸载层数必须按"当时空闲显存"推导：
# 显式 pin num_gpu 会关掉 llama.cpp 的 auto-fit，超配不是降级而是直接打崩服务
# （2026-11-07 实测：ctx4096 pin 30 需 6580 MiB 对 5080 MiB 空闲 -> 服务崩；22 也超安全位）。
# 故 GEN_OPTS_HARD 不再钉 num_gpu，由 _hard_num_gpu() 运行时推导。
GEN_OPTS_FAST = {"temperature": 0.1, "num_ctx": 8192, "num_gpu": 99,
                 "repeat_penalty": 1.15, "presence_penalty": 0.3, "min_p": 0.05}
GEN_OPTS_HARD = {"temperature": 0.1, "num_ctx": 4096}


def _hard_num_gpu(ctx):
    """Derive the MoE offload split from currently free VRAM (never the crash-prone 22)."""
    try:
        import sys
        root = os.path.dirname(os.path.dirname(HERE))
        if root not in sys.path:
            sys.path.insert(0, root)
        from virtu_eval import mem_budget as mb
        env = mb.sample()
        if env["gpu_free_mib"] < mb.VRAM_RESERVE_MIB:
            return 0                      # no headroom -> CPU-only, slow but won't crash
        facts = mb.facts_for_tag(HARD_MODEL)
        return mb.max_offload_layers(facts, ctx, env=env)
    except Exception:
        return 20                         # cannot derive -> conservative ctx4096 ceiling

THINK_RE = re.compile(r"<think[^>]*>.*?</think\s*>", re.DOTALL)


def _post(url, payload, timeout=180):
    # 规避本机透明代理，强制直连 Ollama 环回地址
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(k, None)
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def embed(texts):
    """texts: list[str] -> np.float32 array (n, 768)"""
    if isinstance(texts, str):
        texts = [texts]
    out = _post(f"{OLLAMA}/api/embed", {"model": EMBED_MODEL, "input": texts, "keep_alive": KEEP_ALIVE})
    return np.asarray(out["embeddings"], dtype=np.float32)


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def load_centroids(force=False):
    anchors = json.load(open(ANCHORS_PATH, encoding="utf-8"))
    if not force and os.path.exists(CENTROID_PATH):
        c = json.load(open(CENTROID_PATH, encoding="utf-8"))
        cc = c.get("centroids", {})
        # 防护：缓存的质心必须与当前 EMBED_MODEL 同源，否则静默用过时的 nomic 质心
        same_model = c.get("meta", {}).get("embed_model") == EMBED_MODEL
        if same_model and \
           len(cc.get("expert", [])) == len(anchors["expert"]) and \
           len(cc.get("general", [])) == len(anchors["general"]):
            return anchors, {k: np.asarray(v, dtype=np.float32) for k, v in cc.items()}, c.get("meta", {})
    exp_e = embed(anchors["expert"])
    gen_e = embed(anchors["general"])
    cexp = unit(exp_e.mean(axis=0))
    cgen = unit(gen_e.mean(axis=0))
    meta = {"embed_model": EMBED_MODEL, "n_expert": len(anchors["expert"]),
            "n_general": len(anchors["general"]), "built_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    cache = {"centroids": {"expert": cexp.tolist(), "general": cgen.tolist()}, "meta": meta}
    json.dump(cache, open(CENTROID_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return anchors, {"expert": cexp, "general": cgen}, meta


def match_keywords(prompt, keywords):
    p = prompt.lower()
    return [kw for kw in keywords if kw.lower() in p]


def route(prompt, anchors=None, centroids=None, explain=False):
    if anchors is None or centroids is None:
        anchors, centroids, _ = load_centroids()
    q = unit(embed(prompt)[0])
    ce = float(np.dot(q, centroids["expert"]))
    cg = float(np.dot(q, centroids["general"]))
    margin = ce - cg
    kw = match_keywords(prompt, anchors.get("strong_keywords", []))
    if kw:
        target, basis = HARD_MODEL, "keyword"
        reason = f"命中强专业关键词 {kw}"
    elif margin > THRESH:
        target, basis = HARD_MODEL, "semantic"
        reason = f"语义贴近专业域 (margin={margin:+.3f} > {THRESH})"
    else:
        target, basis = FAST_MODEL, "semantic"
        reason = f"语义偏通用 (margin={margin:+.3f} <= {THRESH})"
    kind = "HARD(moe)" if target == HARD_MODEL else "FAST(dense)"
    return {"target": target, "kind": kind, "basis": basis,
            "margin": round(margin, 4), "cos_expert": round(ce, 4), "cos_general": round(cg, 4),
            "kw_hits": kw, "reason": reason, "prompt": prompt}


def strip_think(text):
    return THINK_RE.sub("", text).strip()


def ask(prompt, max_tokens=512, verbose=False):
    d = route(prompt)
    model = d["target"]
    opts = dict(GEN_OPTS_HARD if model == HARD_MODEL else GEN_OPTS_FAST)
    if model == HARD_MODEL:
        opts["num_gpu"] = _hard_num_gpu(opts["num_ctx"])
    opts["num_predict"] = max_tokens
    ka = MOE_KEEP_ALIVE if model == HARD_MODEL else KEEP_ALIVE
    t0 = time.perf_counter()
    r = _post(f"{OLLAMA}/api/generate",
              {"model": model, "prompt": prompt, "stream": False,
               "options": opts, "keep_alive": ka}, timeout=300)
    dt = time.perf_counter() - t0
    resp = r.get("response", "")
    try:
        from virtu_omni.serving.answer_pipeline import clean_served_answer
        resp = clean_served_answer(prompt, resp).text
    except Exception:
        if model == HARD_MODEL:
            resp = strip_think(resp)
    eval_count = r.get("eval_count", 0)
    eval_dur = r.get("eval_duration", 0)
    tps = (eval_count / eval_dur * 1e9) if eval_dur else (eval_count / dt if dt else 0)
    if verbose:
        print(f"[router] {d['kind']:<11s} basis={d['basis']:<8s} margin={d['margin']:+.3f} kw={d['kw_hits']} ka={ka}")
        print(f"[router] model={model}  {eval_count} tok / {dt:.2f}s ≈ {tps:.1f} tok/s")
    return {"decision": d, "model": model, "response": resp,
            "tok_s": round(tps, 2), "eval_count": eval_count, "elapsed_s": round(dt, 2),
            "keep_alive": ka}


def bench(labeled_path):
    anchors, centroids, _ = load_centroids()
    labeled = json.load(open(labeled_path, encoding="utf-8"))
    items = [(q, "expert") for q in labeled.get("expert", [])] + \
            [(q, "general") for q in labeled.get("general", [])]
    rows = []
    for q, gt in items:
        d = route(q, anchors, centroids)
        pred = "expert" if d["target"] == HARD_MODEL else "general"
        rows.append((q, gt, pred, d["basis"], d["margin"], d["kw_hits"], pred == gt))
    total = len(rows)
    correct = sum(1 for r in rows if r[6])
    tp = sum(1 for r in rows if r[2] == "expert" and r[1] == "expert")
    fp = sum(1 for r in rows if r[2] == "expert" and r[1] == "general")
    fn = sum(1 for r in rows if r[2] == "general" and r[1] == "expert")
    tn = sum(1 for r in rows if r[2] == "general" and r[1] == "general")
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    print(f"== bench ({total} 题, THRESH={THRESH}) ==")
    print(f"accuracy={correct/total:.3f}  precision={prec:.3f}  recall={rec:.3f}  F1={f1:.3f}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    print("-- 逐题 --")
    for q, gt, pred, basis, margin, kw, ok in rows:
        mark = "OK " if ok else "ERR"
        print(f"  [{mark}] gt={gt:7s} pred={pred:7s} {basis:8s} m={margin:+.3f} kw={kw}  {q[:38]}")
    return {"accuracy": correct / total, "precision": prec, "recall": rec, "f1": f1, "rows": rows}


def tune(labeled_path, lo=-0.25, hi=0.25, step=0.01):
    """离线扫描 THRESH: 在纯语义 margin 下 (不含关键词) 找 recall>=1.0 时 precision 最高的值。
    目的: 量化“语义层”的最优阈值, 并揭示关键词白名单兜底的必要性。"""
    anchors, centroids, _ = load_centroids()
    labeled = json.load(open(labeled_path, encoding="utf-8"))
    items = [(q, "expert") for q in labeled.get("expert", [])] + \
            [(q, "general") for q in labeled.get("general", [])]
    emb = embed([q for q, _ in items])
    margins = []
    for i, (q, gt) in enumerate(items):
        qv = unit(emb[i])
        ce = float(np.dot(qv, centroids["expert"]))
        cg = float(np.dot(qv, centroids["general"]))
        margins.append((ce - cg, gt))
    print(f"== tune THRESH 扫描 (纯语义, 不含关键词; {len(items)} 题) ==")
    print(f"{'THRESH':>8s} {'recall':>7s} {'prec':>7s} {'f1':>7s} {'TP':>3s} {'FP':>3s} {'FN':>3s}")
    best = None
    t = lo
    while t <= hi + 1e-9:
        tp = fp = fn = tn = 0
        for m, gt in margins:
            pred = "expert" if m > t else "general"
            if pred == "expert" and gt == "expert":
                tp += 1
            elif pred == "expert" and gt == "general":
                fp += 1
            elif pred == "general" and gt == "expert":
                fn += 1
            else:
                tn += 1
        rec = tp / (tp + fn) if (tp + fn) else 1.0
        prec = tp / (tp + fp) if (tp + fp) else 1.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
        print(f"{t:>8.3f} {rec:>7.3f} {prec:>7.3f} {f1:>7.3f} {tp:>3d} {fp:>3d} {fn:>3d}")
        if rec >= 1.0 and (best is None or prec > best["precision"]):
            best = {"thresh": round(t, 3), "recall": rec, "precision": prec,
                    "f1": round(f1, 3), "fp": fp, "fn": fn}
        t += step
    print("\n推荐 (recall=1.0 前提下 precision 最高):", best)
    print("提示: 若纯语义下 FN 较多, 说明关键词白名单是必要的兜底; THRESH 仅需保证边界通用不误判为专业。")
    return best


def main():
    ap = argparse.ArgumentParser(description="Virtu P1-3 语义路由层 (零训练)")
    sub = ap.add_subparsers(dest="cmd")
    pr = sub.add_parser("route"); pr.add_argument("prompt")
    pa = sub.add_parser("ask"); pa.add_argument("prompt"); pa.add_argument("--max-tokens", type=int, default=512)
    pb = sub.add_parser("bench"); pb.add_argument("--labeled", default=os.path.join(HERE, "bench_labeled.json"))
    pbu = sub.add_parser("build")
    pt = sub.add_parser("tune")
    pt.add_argument("--labeled", default=os.path.join(HERE, "bench_labeled.json"))
    pt.add_argument("--lo", type=float, default=-0.25)
    pt.add_argument("--hi", type=float, default=0.25)
    pt.add_argument("--step", type=float, default=0.01)
    args = ap.parse_args()
    if args.cmd == "route":
        d = route(args.prompt)
        print(json.dumps(d, ensure_ascii=False, indent=2))
    elif args.cmd == "ask":
        res = ask(args.prompt, max_tokens=args.max_tokens, verbose=True)
        print("\n=== 回答 ===")
        print(res["response"])
    elif args.cmd == "bench":
        bench(args.labeled)
    elif args.cmd == "build":
        _, _, meta = load_centroids(force=True)
        print("centroids rebuilt:", meta)
    elif args.cmd == "tune":
        tune(args.labeled, args.lo, args.hi, args.step)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
