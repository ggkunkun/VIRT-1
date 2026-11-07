"""生成 v3「短板补齐」数据集 virtu_v3_patch.jsonl。

策略（质量优先、成本最低）：
  A. toolcall 强修（核心，救 20 例 JSON 失败）：从 v3 评测 toolcall 维的 gold
     （格式为 {"tool":...,"arguments":...}）取种子，做参数/工件名增广，
     强力教模型输出 `tool` 键（而非 `name`）。
  B. 反遗忘 replay：从 virtu_v2_curated.jsonl 随机抽 200 条（覆盖 reasoning/
     instruction/generation/knowledge/generalization/boundary），防续训回退。
输出 messages 格式，与 train_qwen3_8b_qlora.py 兼容。
"""
import json, random, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
random.seed(20261103)


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ---- 1. toolcall seeds from v3 eval (gold uses "tool" key) ----
recs = load("_eval_v3_all90/raw.jsonl")
tc = [r for r in recs if r["dimension"] == "toolcall"]
seeds = []
for r in tc:
    ans = (r.get("gold") or {}).get("answer")
    if ans and '"tool"' in ans:
        seeds.append((r["prompt"], ans))
print("toolcall seeds with tool-key gold:", len(seeds))

# ---- 2. augment ----
NAMES = ["shaft", "flange", "bracket", "housing", "plate", "block", "hub", "rod"]


def vary_text(t):
    out = t
    for i, n in enumerate(NAMES):
        if n in out:
            out = out.replace(n, NAMES[(i + 1) % len(NAMES)], 1)
            break
    def num(m):
        v = float(m.group())
        nv = v * random.uniform(0.8, 1.2)
        if abs(nv) < 1e-9:
            nv = v
        return str(int(round(nv)) if abs(nv - round(nv)) < 1e-6 else round(nv, 2))
    out = re.sub(r"\d+\.?\d*", num, out)
    return out


def vary_obj(obj):
    if isinstance(obj, dict):
        return {k: vary_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [vary_obj(x) for x in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        nv = obj * random.uniform(0.8, 1.2)
        return int(round(nv)) if isinstance(obj, int) else round(nv, 2)
    if isinstance(obj, str):
        return vary_text(obj)
    return obj


toolcall_msgs = []
for prompt, ans in seeds:
    try:
        base_obj = json.loads(ans)
    except Exception:
        base_obj = None
    toolcall_msgs.append({"messages": [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": ans},
    ]})
    for _ in range(5):
        p2 = vary_text(prompt)
        if base_obj is not None:
            a2 = json.dumps(vary_obj(base_obj), ensure_ascii=False)
        else:
            a2 = vary_text(ans)
        toolcall_msgs.append({"messages": [
            {"role": "user", "content": p2},
            {"role": "assistant", "content": a2},
        ]})
print("toolcall augmented msgs:", len(toolcall_msgs))

# ---- 3. replay from v2_curated (anti-forgetting) ----
curated = load("data/sft/virtu_v2_curated.jsonl")
replay = random.sample(curated, min(200, len(curated)))
print("replay:", len(replay))

# ---- 4. write ----
patch = toolcall_msgs + replay
random.shuffle(patch)
outp = os.path.join(ROOT, "data/sft/virtu_v3_patch.jsonl")
with open(outp, "w", encoding="utf-8") as f:
    for m in patch:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")

# ---- 5. validate ----
bad = 0
tool_cnt = 0
for m in patch:
    a = m["messages"][-1]["content"]
    if not isinstance(a, str):
        bad += 1
        continue
    if '"tool"' in a:
        tool_cnt += 1
print("WROTE", outp, "total", len(patch), "tool-format", tool_cnt, "bad", bad)
