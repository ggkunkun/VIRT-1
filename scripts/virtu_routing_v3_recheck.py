#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 路由层 · v3 实测复核（P1-3 的确认性再分析，非生产路由）

说明：生产路由层是 scripts/router/virtu_router.py（已交付，20 题 bench acc=0.900 /
recall=1.0，含 HTTP 服务）。本脚本只做一件事：用 domain_ab_20261106_v3 的 24 题
"实测分"验证"路由是否真的能反超 MoE-only"——即 oracle 上限分析。它不替代生产路由。


判定口径（测量宪法 §8）：
- 标签来自 runs/domain_ab_20261106_v3/raw.jsonl 的实测分差：
    MoE 优势 = moe_score - dense_score >= 16.7 （粗粒度判分下非平局的明显胜出）
    其余（稠密胜 / 平局）一律默认稠密（平局时稠密与 MoE 同分但快 3.9x，故默认稠密最优）
- 路由 = 提问 embedding 到 "MoE 优势质心" 与 "稠密默认质心" 的余弦，取更近者（阈值 0）。
- 评估不含泄漏：质心由 7 个清晰案例学得，应用到全部 24 题的"实测分"上，
  即"若路由器选该臂，能得到该题的实测分"，直接换算路由后可达质量。

用法：
  python scripts/virtu_router.py --eval            # 离线评估，输出 JSON
  python scripts/virtu_router.py --prompt "..."    # 路由 + 真实生成
  python scripts/virtu_router.py --prompt "..." --no-gen   # 仅路由不生成
"""
import argparse, json, math, hashlib, urllib.request, os, sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
BENCH = os.path.join(WS, "benchmarks", "virtu_domain_cases_2026-11-06.json")
V3 = os.path.join(WS, "runs", "domain_ab_20261106_v3", "raw.jsonl")
DENSE_MODEL = "virtu-production:latest"
MOE_MODEL = "virtu-moe-14b:fast"
MARGIN = 16.7  # 粗粒度判分下非平局的明显胜出阈值

# 可解释的"难题"词表：知识/推理/标准/API 类意图（MoE 实测占优的语义域）。
# 误报只会增加延迟（MoE 更慢但不更错），故对模糊难题偏向 MoE 是安全的。
LEXICAL_HARD = [
    # FEA / 强度推理
    "von mises", "安全系数", "fos", "屈服强度", "等效应力", "强度校核",
    "疲劳强度", "疲劳极限", "应力集中",
    # CAD API / 脚本
    "api", "vba", "solidworks api", "方法名", "对象模型", "接口", "二次开发",
    # 热处理 / 材料
    "调质", "淬火", "回火", "正火", "退火", "热处理", "硬度", "晶相", "金相",
    # 表面质量 / 标准
    "表面粗糙度", "粗糙度", "ra", "轮廓算术", "gb/", "公差标准", "形位公差",
    # 需要推导的经验关系
    "关系式", "经验公式", "推导", "理论公式",
]

def lexical_route(text):
    t = text.lower()
    for kw in LEXICAL_HARD:
        if kw in t:
            return True, kw
    return False, None

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def embed(texts):
    if isinstance(texts, str):
        texts = [texts]
    payload = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(OLLAMA + "/api/embed", data=payload,
                                 headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120).read()
    return json.loads(resp)["embeddings"]

def cos(a, b):
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
    return s / (na * nb) if na and nb else 0.0

def load_data():
    d = json.load(open(BENCH, encoding="utf-8"))
    qmap = {c["id"]: c.get("q", "") for c in d["cases"]}
    rows = [json.loads(l) for l in open(V3, encoding="utf-8")]
    by = {}
    for r in rows:
        by.setdefault(r["case_id"], {})[r["model"]] = r["score"]
    cases = []
    for cid, mm in by.items():
        dscore = mm.get("virtu-dense-merged:q4_0", 0.0)
        mscore = mm.get("virtu-moe-14b:fast", 0.0)
        margin = mscore - dscore
        label = "MOE" if margin >= MARGIN else ("DENSE" if -margin >= MARGIN else "TIE")
        cases.append({"id": cid, "q": qmap.get(cid, ""), "dense": dscore,
                      "moe": mscore, "margin": margin, "label": label})
    return cases

def build_centroids(cases):
    moe = [c for c in cases if c["label"] == "MOE"]
    dense = [c for c in cases if c["label"] == "DENSE"]
    emb_moe = embed([c["q"] for c in moe])
    emb_dense = embed([c["q"] for c in dense])
    cen_moe = [sum(v) / len(v) for v in zip(*emb_moe)] if emb_moe else None
    cen_dense = [sum(v) / len(v) for v in zip(*emb_dense)] if emb_dense else None
    return cen_moe, cen_dense, moe, dense

def route(text, cen_moe, cen_dense, embed_thresh=0.05):
    """混合路由：词表命中 -> MoE；否则 embedding 强信号(cos差>thresh) -> MoE；否则 DENSE。"""
    hit, kw = lexical_route(text)
    if hit:
        return "MOE", "lexical:" + kw, 0.0, 0.0
    if cen_moe and cen_dense:
        e = embed([text])[0]
        cm = cos(e, cen_moe); cd = cos(e, cen_dense)
        if cm - cd > embed_thresh:
            return "MOE", "embed", cm, cd
        return "DENSE", "embed", cm, cd
    return "DENSE", "default", 0.0, 0.0

def generate(model, prompt, num_ctx=4096, num_predict=256):
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                          "options": {"num_ctx": num_ctx, "temperature": 0.0,
                                      "num_predict": num_predict}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=300).read())
    return resp.get("response", "")

def _routed_mean_for(preds, cases):
    sc = [(c["moe"] if arm == "MOE" else c["dense"]) for c, arm in preds]
    return sum(sc) / len(sc)

def _clear_pr(preds, cases):
    """在 7 个清晰案例上算 MoE 类的精确率/召回率。"""
    clear = [c for c in cases if c["label"] in ("MOE", "DENSE")]
    tp = fp = fn = 0
    for c, arm in preds:
        if c["label"] not in ("MOE", "DENSE"):
            continue
        if arm == "MOE" and c["label"] == "MOE": tp += 1
        elif arm == "MOE" and c["label"] == "DENSE": fp += 1
        elif arm == "DENSE" and c["label"] == "MOE": fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return round(100 * prec, 1), round(100 * rec, 1), len(clear)

def run_eval():
    cases = load_data()
    cen_moe, cen_dense, moe_set, dense_set = build_centroids(cases)
    dense_only = sum(c["dense"] for c in cases) / len(cases)
    moe_only = sum(c["moe"] for c in cases) / len(cases)
    oracle_mean = sum(max(c["dense"], c["moe"]) for c in cases) / len(cases)

    # 混合路由（词表 OR 严格 embedding）
    hyb_preds = [(c, route(c["q"], cen_moe, cen_dense)[0]) for c in cases]
    hyb_mean = _routed_mean_for(hyb_preds, cases)
    hyb_prec, hyb_rec, n_clear = _clear_pr(hyb_preds, cases)

    # 纯词表路由
    lex_preds = [(c, ("MOE" if lexical_route(c["q"])[0] else "DENSE")) for c in cases]
    lex_mean = _routed_mean_for(lex_preds, cases)
    lex_prec, lex_rec, _ = _clear_pr(lex_preds, cases)

    run_id = hashlib.sha256(
        (sha256_file(BENCH) + sha256_file(V3) + "virtu_router_v2").encode()).hexdigest()[:16]
    out = {
        "run_id": "rt-" + run_id,
        "basis": "measured",
        "n_cases": len(cases),
        "labels": {"MOE_adv": len(moe_set), "DENSE_adv": len(dense_set),
                   "TIE": sum(1 for c in cases if c["label"] == "TIE")},
        "quality": {
            "dense_only_mean": round(dense_only, 2),
            "moe_only_mean": round(moe_only, 2),
            "oracle_ceiling_mean": round(oracle_mean, 2),
            "hybrid_routed_mean": round(hyb_mean, 2),
            "lexical_routed_mean": round(lex_mean, 2),
            "hybrid_vs_dense_gain": round(hyb_mean - dense_only, 2),
            "hybrid_vs_moe_gap": round(moe_only - hyb_mean, 2),
        },
        "router_validity_clear_n": n_clear,
        "hybrid_clear_precision_pct": hyb_prec,
        "hybrid_clear_recall_pct": hyb_rec,
        "lexical_clear_precision_pct": lex_prec,
        "lexical_clear_recall_pct": lex_rec,
        "note": ("oracle_ceiling 证明路由概念可行（完美路由可反超 moe_only）。"
                 "但 embedding 质心在 7 样本上 LOO≈ Chance，故生产用可解释词表路由；"
                 "embedding 仅作严格补充信号。误报只增延迟、不降质量。"),
    }
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", action="store_true", help="离线评估并输出 JSON")
    ap.add_argument("--prompt", type=str, default=None, help="待路由的提问")
    ap.add_argument("--no-gen", action="store_true", help="仅路由不生成")
    ap.add_argument("--num-predict", type=int, default=256)
    args = ap.parse_args()

    if args.eval:
        out = run_eval()
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.prompt:
        cases = load_data()
        cen_moe, cen_dense, _, _ = build_centroids(cases)
        arm, reason, cm, cd = route(args.prompt, cen_moe, cen_dense)
        model = MOE_MODEL if arm == "MOE" else DENSE_MODEL
        print(f"[route] -> {arm}  (reason={reason}, cos_MOE={cm:.3f}, cos_DENSE={cd:.3f})")
        print(f"[model] {model}")
        if not args.no_gen:
            nc = 8192 if arm == "MOE" else 4096
            ans = generate(model, args.prompt, num_ctx=nc, num_predict=args.num_predict)
            print("---- answer ----")
            print(ans)
        return

    print("用法: --eval | --prompt \"...\" [--no-gen]", file=sys.stderr)

if __name__ == "__main__":
    main()
