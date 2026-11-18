#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu P1-3 路由 HTTP 服务 —— 并发压测 (零依赖)
============================================
模拟真实混合流量 (30% 专业 -> MoE 慢路径 / 70% 通用 -> 稠密快路径),
在多个并发级别下测量:
  - 端到端吞吐 (requests/sec)
  - 延迟 p50 / p95 / max
  - 各路径真实 tok/s
  - 并发下的路由准确率 (专业题是否仍被正确送往 HARD)

用法:
  python bench_concurrent.py --base http://127.0.0.1:8800 --levels 1,4,8 --per 20 --max-tokens 48
"""
import os
import sys
import json
import time
import argparse
import random
import threading
import statistics
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bridges.bridge_security import ensure_service_token

ROUTER_TOKEN = ensure_service_token("router", "ROUTER_AUTH_TOKEN")

# ---- 混合题库 (已知标签, 用于校验路由准确率) ----
EXPERT = [
    "用 UG 怎么把一个曲面拆成两块好分开加工？",
    "淬火后零件怎么消除内应力？",
    "不锈钢切削面总是起毛刺，怎么改善？",
    "G71 粗车循环的余量参数怎么设？",
    "数控加工中心怎么对刀设定 G54 坐标系？",
    "五轴机床的后处理怎么配刀轴矢量？",
    "铝合金薄壁件加工怎么防变形？",
    "VERICUT 里 Auto-Diff 红色过切怎么定位？",
    "SolidWorks 拉伸特征和旋转特征体积怎么守恒校验？",
    "FANUC 宏程序 WHILE 循环怎么写深孔钻？",
]
GENERAL = [
    "帮我写一段周末爬山的朋友圈文案。",
    "通货膨胀用简单例子说明。",
    "怎么用 Python 读 csv 并打印前五行？",
    "一份周工作计划通常要列哪些板块？",
    "健身减脂期间晚饭吃什么比较合适？",
    "如何向五岁小孩解释为什么天是蓝的？",
    "帮我起三个科技自媒体的账号名。",
    "Excel 怎么快速去重并统计重复次数？",
    "请假邮件怎么写比较得体？",
    "简述一下 TCP 三次握手。",
]

EXPERT_SET = set(EXPERT)
_pct = 30  # 专业题占比 (贴近 P1-3 实测流量结构)


def post(url, payload, timeout=300):
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {ROUTER_TOKEN}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def build_mix(per, pattern="mix"):
    """按 _pct 比例构造 per 个 (prompt, gt) 元组。
    pattern:
      mix       : 随机混流 (固定 seed, 贴近真实流量)
      interleave: 单点专业穿插 E G E G... (测主动预热消专业->通用 reload 的收益)
      bursty    : 专业成簇于后段 (测 run-length 保持热窗口收益)
    """
    n_exp = max(1, round(per * _pct / 100))
    if pattern == "interleave":
        prompts, ei, gi = [], 0, 0
        for i in range(per):
            if (i % 2 == 0) and ei < n_exp:
                prompts.append((EXPERT[ei % len(EXPERT)], "expert")); ei += 1
            elif gi < (per - n_exp):
                prompts.append((GENERAL[gi % len(GENERAL)], "general")); gi += 1
            else:
                prompts.append((EXPERT[ei % len(EXPERT)], "expert")); ei += 1
        return prompts
    if pattern == "bursty":
        gens = [(GENERAL[i % len(GENERAL)], "general") for i in range(per - n_exp)]
        exps = [(EXPERT[i % len(EXPERT)], "expert") for i in range(n_exp)]
        return gens + exps
    # mix (默认): 随机混流 (固定 seed 可复现)
    rng = random.Random(20261106)
    pool = [(EXPERT[i % len(EXPERT)], "expert") for i in range(n_exp)] + \
           [(GENERAL[i % len(GENERAL)], "general") for i in range(per - n_exp)]
    rng.shuffle(pool)
    return pool


def run_level(base, conc, per, max_tokens, pattern="mix"):
    mix = build_mix(per, pattern)
    results = [None] * per
    gate = threading.BoundedSemaphore(conc)  # 实际并发上限 = conc

    def worker(idx, prompt):
        gate.acquire()
        t0 = time.perf_counter()
        try:
            r = post(base + "/ask", {"prompt": prompt, "max_tokens": max_tokens})
            lat = time.perf_counter() - t0
            results[idx] = {
                "ok": True, "lat": lat, "kind": r.get("kind"),
                "tps": r.get("tok_s", 0), "tok": r.get("eval_count", 0),
                "empty": not (r.get("response") or "").strip(),
            }
        except Exception as e:
            results[idx] = {"ok": False, "lat": time.perf_counter() - t0,
                            "err": str(e)[:120]}
        finally:
            gate.release()

    threads = [threading.Thread(target=worker, args=(i, p)) for i, (p, _) in enumerate(mix)]
    wall0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.perf_counter() - wall0

    lats = [r["lat"] for r in results if r and r["ok"]]
    ok = [r for r in results if r and r["ok"]]
    fails = [r for r in results if r and not r["ok"]]
    empties = [r for r in ok if r["empty"]]

    # 路由准确率 (基于已知标签)
    route_ok = route_tot = 0
    for r, (prompt, gt) in zip(results, mix):
        if not r or not r["ok"]:
            continue
        route_tot += 1
        pred = "expert" if r["kind"] == "HARD(moe)" else "general"
        if pred == gt:
            route_ok += 1

    # 分路径 tok/s
    fast = [r["tps"] for r in ok if r["kind"] == "FAST(dense)"]
    hard = [r["tps"] for r in ok if r["kind"] == "HARD(moe)"]
    avg_tps_all = (sum(r["tok"] for r in ok) / sum(r["lat"] for r in ok)) if ok else 0

    return {
        "conc": conc, "per": per, "wall_s": round(wall, 2),
        "throughput_rps": round(len(ok) / wall, 2) if wall else 0,
        "ok": len(ok), "fail": len(fails), "empty": len(empties),
        "lat_p50": round(statistics.median(lats), 3) if lats else 0,
        "lat_p95": round(sorted(lats)[max(0, int(len(lats) * 0.95) - 1)] if lats else 0, 3),
        "lat_max": round(max(lats), 3) if lats else 0,
        "route_acc": round(route_ok / route_tot, 3) if route_tot else 0,
        "fast_tps_avg": round(statistics.mean(fast), 1) if fast else 0,
        "fast_n": len(fast),
        "hard_tps_avg": round(statistics.mean(hard), 1) if hard else 0,
        "hard_n": len(hard),
        "avg_tps_all": round(avg_tps_all, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8800")
    ap.add_argument("--levels", default="1,4,8")
    ap.add_argument("--per", type=int, default=20)
    ap.add_argument("--max-tokens", type=int, default=48)
    ap.add_argument("--pattern", default="mix", choices=["mix", "interleave", "bursty"])
    args = ap.parse_args()
    levels = [int(x) for x in args.levels.split(",") if x.strip()]

    # 健康预检
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    try:
        req = urllib.request.Request(
            args.base + "/health",
            headers={"Authorization": f"Bearer {ROUTER_TOKEN}"})
        h = json.load(urllib.request.urlopen(req, timeout=8))
        print(f"[bench] health ok={h.get('ok')} fast={h.get('fast_ready')} hard={h.get('hard_ready')} embed={h.get('embed_ready')}")
        if not h.get("ok"):
            print("[bench] ABORT: 后端模型未就绪"); sys.exit(2)
    except Exception as e:
        print(f"[bench] ABORT: 无法连服务 {args.base}: {e}"); sys.exit(2)

    # 串行预热 1 发 (避免首次编译/加载抖动影响并发测量)
    try:
        post(args.base + "/ask", {"prompt": GENERAL[0], "max_tokens": 16})
        print("[bench] warmup ok")
    except Exception as e:
        print(f"[bench] warmup warn: {e}")

    print(f"\n=== 并发压测: levels={levels} per_level={args.per} max_tokens={args.max_tokens} 专业占比={_pct}% pattern={args.pattern} ===")
    print(f"{'conc':>4s} {'per':>4s} {'wall':>6s} {'rps':>6s} {'ok':>3s} {'fail':>4s} {'p50':>6s} {'p95':>6s} {'max':>6s} {'routeAcc':>8s} {'fastT':>6s} {'hardT':>6s} {'allT':>6s}")
    all_rows = []
    for c in levels:
        row = run_level(args.base, c, args.per, args.max_tokens, args.pattern)
        all_rows.append(row)
        print(f"{row['conc']:>4d} {row['per']:>4d} {row['wall_s']:>6.2f} {row['throughput_rps']:>6.2f} "
              f"{row['ok']:>3d} {row['fail']:>4d} {row['lat_p50']:>6.3f} {row['lat_p95']:>6.3f} {row['lat_max']:>6.3f} "
              f"{row['route_acc']:>8.3f} {row['fast_tps_avg']:>6.1f} {row['hard_tps_avg']:>6.1f} {row['avg_tps_all']:>6.1f}")
        if row["fail"]:
            print(f"      [warn] {row['fail']} 请求失败 (可能显存/队列压力)")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench_concurrent_report.json")
    json.dump({"levels": levels, "per": args.per, "max_tokens": args.max_tokens,
               "expert_ratio": _pct, "pattern": args.pattern, "rows": all_rows,
               "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(out_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n[bench] report saved -> {out_path}")


if __name__ == "__main__":
    main()
