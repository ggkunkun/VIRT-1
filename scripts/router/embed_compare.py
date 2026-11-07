#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入模型对比 (nomic-embed-text vs bge-m3) —— 仅测"语义层"本身
==============================================================
路由器是 关键词白名单 OR 语义质心margin 的混合路由。关键词命中率已很高，
真正薄弱的是语义层（nomic 中文 margin 仅 ±0.13）。本脚本隔离掉关键词，
纯粹比较两种嵌入在 Virtu 工业域上的判别力：

  1) 质心分离度：expert 质心 与 general 质心的余弦距离（越大越可分）
  2) 类内/类间：锚点集类内平均余弦 vs 类间平均余弦（discriminability = 类间 - 类内）
  3) 泛化 kNN（无关键词）：用 anchors 建质心，对独立 bench_labeled(20题) 做最近质心分类，
     报告 accuracy / precision / recall / F1 —— 这才是"换嵌入能不能少靠关键词"的硬指标

用法：
  python embed_compare.py --models nomic-embed-text bge-m3
"""
import os
import sys
import json
import time
import argparse
import numpy as np

OLLAMA = "http://127.0.0.1:11434"
HERE = os.path.dirname(os.path.abspath(__file__))
ANCHORS_PATH = os.path.join(HERE, "anchors.json")
BENCH_PATH = os.path.join(HERE, "bench_labeled.json")


def _post(url, payload, timeout=180):
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(k, None)
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def embed(model, texts):
    out = _post(f"{OLLAMA}/api/embed",
                {"model": model, "input": list(texts), "keep_alive": "10m"})
    return np.asarray(out["embeddings"], dtype=np.float32)


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def cos(a, b):
    return float(np.dot(unit(a), unit(b)))


def analyze(model):
    A = json.load(open(ANCHORS_PATH, encoding="utf-8"))
    B = json.load(open(BENCH_PATH, encoding="utf-8"))
    exp_a = embed(model, A["expert"])
    gen_a = embed(model, A["general"])
    cexp = unit(exp_a.mean(0)); cgen = unit(gen_a.mean(0))
    # 1) 质心分离度
    sep = cos(cexp, cgen)
    # 2) 类内/类间
    exp_intra = np.mean([cos(exp_a[i], exp_a[j]) for i in range(len(exp_a)) for j in range(i + 1, len(exp_a))])
    gen_intra = np.mean([cos(gen_a[i], gen_a[j]) for i in range(len(gen_a)) for j in range(i + 1, len(gen_a))])
    inter = cos(cexp, cgen)
    intra = (exp_intra + gen_intra) / 2
    disc = intra - inter  # 越大越好（类内近、类间远）
    # 3) 泛化 kNN（无关键词）：anchors 建质心，bench 最近质心
    rows = [(q, "expert") for q in B["expert"]] + [(q, "general") for q in B["general"]]
    eb = embed(model, [q for q, _ in rows])
    tp = fp = fn = tn = 0
    per = []
    for (q, gt), e in zip(rows, eb):
        ce = cos(e, cexp); cg = cos(e, cgen)
        pred = "expert" if ce > cg else "general"
        ok = pred == gt
        per.append((q, gt, pred, round(ce - cg, 3), ok))
        if pred == "expert" and gt == "expert": tp += 1
        elif pred == "expert" and gt == "general": fp += 1
        elif pred == "general" and gt == "expert": fn += 1
        else: tn += 1
    tot = tp + fp + fn + tn
    acc = (tp + tn) / tot
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "model": model, "dim": exp_a.shape[1],
        "centroid_cos": round(sep, 4),
        "intra_mean_cos": round(float(intra), 4),
        "inter_cos": round(float(inter), 4),
        "discriminability": round(float(disc), 4),
        "knn_acc": round(acc, 3), "knn_prec": round(prec, 3),
        "knn_rec": round(rec, 3), "knn_f1": round(f1, 3),
        "rows": per,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["nomic-embed-text", "bge-m3"])
    args = ap.parse_args()
    results = []
    for m in args.models:
        t0 = time.perf_counter()
        try:
            r = analyze(m)
            r["elapsed_s"] = round(time.perf_counter() - t0, 1)
            results.append(r)
            print(f"\n===== {m} (dim={r['dim']}, {r['elapsed_s']}s) =====")
            print(f"  质心余弦(越近0越可分):      {r['centroid_cos']:+.4f}")
            print(f"  类内平均余弦:               {r['intra_mean_cos']:+.4f}")
            print(f"  类间余弦(=质心余弦):        {r['inter_cos']:+.4f}")
            print(f"  判别力 intra-inter:         {r['discriminability']:+.4f}  (越大越好)")
            print(f"  独立集 kNN(无关键词):        acc={r['knn_acc']:.3f} prec={r['knn_prec']:.3f} "
                  f"rec={r['knn_rec']:.3f} f1={r['knn_f1']:.3f}")
            for q, gt, pred, marg, ok in r["rows"]:
                print(f"    [{'OK ' if ok else 'ERR'}] gt={gt:7s} pred={pred:7s} m={marg:+.3f}  {q[:34]}")
        except Exception as e:
            print(f"\n===== {m} FAILED: {repr(e)} =====")
    if len(results) == 2:
        a, b = results
        print("\n===== 对比结论 =====")
        print(f"  判别力(intra-inter): {a['model']}={a['discriminability']:+.4f}  vs  {b['model']}={b['discriminability']:+.4f}")
        print(f"  独立集 kNN acc      : {a['model']}={a['knn_acc']:.3f}  vs  {b['model']}={b['knn_acc']:.3f}")
        better = b["discriminability"] > a["discriminability"] and b["knn_acc"] >= a["knn_acc"]
        print("  =>", "建议采用", b["model"] if better else "保持", a["model"] if better else b["model"])


if __name__ == "__main__":
    main()
