# -*- coding: utf-8 -*-
"""根据实测数据生成 Virtu 模型本机适配部署包"""
import json, glob, os, io

TEMP = r"D:\Virtu模型\temp"
DEPLOY = r"D:\Virtu模型\deploy"
os.makedirs(DEPLOY, exist_ok=True)

# ---------- 汇总所有基准结果，取每个模型最佳 profile ----------
best = {}
allrec = []
for f in glob.glob(os.path.join(TEMP, "bench[0-9].json")):
    try:
        data = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for r in data:
        allrec.append(r)
        if not r.get("ok") or not r.get("tok_s"):
            continue
        key = r["model"]
        if key not in best or r["tok_s"] > best[key]["tok_s"]:
            best[key] = r

print("probed models:", len(best))

# ---------- 唯一权重分组（来自 mapping）----------
mp = json.load(open(os.path.join(TEMP, "mapping.json"), encoding="utf-8"))
groups = {}
for m in mp["ollama_models"]:
    groups.setdefault(tuple(m["from"]), []).append(m)

# ---------- 人工确认的适配结论 ----------
# tier: S=推荐主力, A=可用, B=勉强可用, X=弃用/不可用
DECISION = {
    # 8B dense Q4_0 4.3GB 组：全 GPU，30-38 tok/s
    "8b": dict(tier="S", num_gpu=99, num_ctx=8192, note="8B 密集模型，全量 offload，本机最流畅档"),
    # MoE 14B q3_K_M 6.25GB
    "moe_q3km": dict(tier="S", num_gpu=34, num_ctx=4096, note="MoE 14B q3_K_M，激活参数少，13B 级最优"),
    # 13B q3_K_M 5.88GB
    "13b_q3km": dict(tier="S", num_gpu=99, num_ctx=8192, note="13B q3_K_M，基本可整装进 6GB 显存"),
    # 13B Q4_0 7.74GB
    "13b_q4": dict(tier="B", num_gpu=36, num_ctx=8192, note="13B Q4_0 超出显存，最佳仅 36 层 offload"),
    # MoE 14B Q4 7.75GB
    "moe_q4": dict(tier="X", num_gpu=36, num_ctx=4096, note="MoE 14B Q4 在本机严重劣化，建议改用 q3_K_M"),
    # MoE bf16 25GB
    "moe_bf16": dict(tier="X", num_gpu=0, num_ctx=2048, note="25GB bf16 超出 16GB 内存，本机不可用"),
}

sales = []
for frm, ms in groups.items():
    path = frm[0] if frm else ""
    bn = os.path.basename(path)
    size_gb = round(os.path.getsize(path) / 1024**3, 2) if path and os.path.exists(path) else None
    names = [m["name"] for m in ms]
    joined = " ".join(names).lower()

    if "bf16" in joined:
        kind = "moe_bf16"
    elif size_gb and size_gb > 20:
        kind = "moe_bf16"
    elif 6.0 <= (size_gb or 0) <= 6.5 and "moe" in joined:
        kind = "moe_q3km"
    elif 7.5 <= (size_gb or 0) <= 8.1 and "moe" in joined:
        kind = "moe_q4"
    elif 5.6 <= (size_gb or 0) <= 6.1:
        kind = "13b_q3km"
    elif 7.5 <= (size_gb or 0) <= 8.0:
        kind = "13b_q4"
    elif 4.0 <= (size_gb or 0) <= 4.6:
        kind = "8b"
    else:
        kind = "other"

    speeds = {n: (best.get(n, {}) or {}).get("tok_s") for n in names}
    viable = {k: v for k, v in speeds.items() if v}
    rep = max(viable, key=viable.get) if viable else names[0]
    sales.append(dict(size_gb=size_gb, kind=kind, names=names, rep=rep,
                      best_tps=max(viable.values()) if viable else None,
                      decision=DECISION.get(kind, dict(tier="?", note="未分类"))))

sales.sort(key=lambda x: (x["kind"], -(x["best_tps"] or 0)))
json.dump(sales, open(os.path.join(DEPLOY, "adapt_matrix.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------- 生成优化 Modelfile ----------
OPT = [
    ("virtu-opt-8b",         "virtu-production:latest",  "S", 99, 8192, "36.9"),
    ("virtu-opt-8b-ties",    "virtu-dense-ties:q4",      "S", 99, 8192, "37.7"),
    ("virtu-opt-8b-v3",      "virtu-v3:hardened",        "S", 99, 8192, "33.6"),
    ("virtu-opt-13b",        "virtu-13.63b:asym",        "S", 99, 8192, "19.7"),
    ("virtu-opt-moe14b",     "virtu-moe-14b:q3km",       "S", 34, 4096, "21.4"),
    ("virtu-opt-13b-q4",     "virtu-13.63b:latest",      "B", 36, 8192, "10.8"),
]
for tag, base, tier, ng, nc, tps in OPT:
    body = f"""# 本机适配版：{tag}
# 基线模型：{base}
# 实测：{tps} tok/s（RTX 4050 Laptop 6GB / i5-12450H / 16GB RAM）
# num_gpu={ng}  num_ctx={nc}  —— 由参数扫描定位的最优点，请勿随意增大 num_gpu
FROM {base}

PARAMETER num_gpu {ng}
PARAMETER num_ctx {nc}
PARAMETER num_batch 256
PARAMETER num_thread 10
PARAMETER temperature 0.1
PARAMETER top_p 0.85
PARAMETER top_k 40
PARAMETER repeat_penalty 1.15
"""
    open(os.path.join(DEPLOY, f"Modelfile.{tag}"), "w", encoding="utf-8").write(body)

print("deploy files written:", len(os.listdir(DEPLOY)))
for s in sales:
    print(f"{str(s['size_gb']):>6}GB  {s['kind']:<10} {s['decision']['tier']}  "
          f"tps={s['best_tps']}  tags={len(s['names'])}  rep={s['rep']}")
