"""诊断 v3 评测失败样本：定位 toolcall / reasoning 回落根因，输出失败榜。

输出：
  - 各维度 n / mean / fail 数
  - 全局失败 criteria Top 排行
  - 重点维度(toolcall, reasoning) 的失败 criteria 分布 + 样本明细
"""
import json, collections, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_eval_v3_all90", "raw.jsonl")
DIMS = ["reasoning", "instruction", "generation", "toolcall", "generalization", "boundary", "knowledge"]


def load():
    with open(RAW, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def main():
    recs = load()
    print(f"total={len(recs)}")
    print("\n== per-dimension ==")
    for d in DIMS:
        sub = [r for r in recs if r["dimension"] == d]
        sc = [r["score"] for r in sub]
        fails = [r for r in sub if r.get("verdict") != "pass"]
        print(f"{d:14s} n={len(sub):3d} mean={sum(sc)/len(sc):6.2f} fail={len(fails):3d}")

    print("\n== global failed-criteria Top ==")
    g = collections.Counter()
    for r in recs:
        if r.get("verdict") != "pass":
            for c in r.get("criteria", []):
                if not c.get("passed"):
                    g[c["key"]] += 1
    for k, v in g.most_common():
        print(f"  {k}: {v}")

    for d in ["toolcall", "reasoning"]:
        print(f"\n== {d} failures ==")
        sub = [r for r in recs if r["dimension"] == d and r.get("verdict") != "pass"]
        cnt = collections.Counter()
        for r in sub:
            for c in r.get("criteria", []):
                if not c.get("passed"):
                    cnt[c["key"]] += 1
        print("  failed criteria:", dict(cnt.most_common()))
        print("  sample fails:")
        for r in sub[:8]:
            failed = [c["key"] for c in r.get("criteria", []) if not c.get("passed")]
            tc = r.get("tool_calls")
            print(f"  - {r['case_id']} score={r['score']:.1f} failed={failed}")
            print(f"      resp={str(r['response'])[:130]}")
            if tc is not None:
                print(f"      tool_calls(raw)={str(tc)[:130]}")


if __name__ == "__main__":
    main()
