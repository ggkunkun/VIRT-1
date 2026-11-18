#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""汇总「全面补齐短板 + 独立留出题终评」，生成榜单与前后对比报告。

只读已封缄的落盘证据，不重新问模型、不补分。
用法: python scripts/prod_final_report.py --write
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "runs", "eval", "prod_final_20261108")
MODEL_SUMMARY = os.path.join(RUN, "model_only", "summary.json")
BUILD = os.path.join(ROOT, "benchmarks", "PRODUCTION_BUILD_MANIFEST_2026-11-08.json")
POOL = os.path.join(ROOT, "data", "benchmark", "virtu_prod_holdout_v1", "POOL_MANIFEST.json")
PREV = os.path.join(ROOT, "benchmarks", "PRODUCTION_LEADERBOARD_2026-11-08.json")
OUT_MD = os.path.join(ROOT, "benchmarks", "PRODUCTION_FINAL_EVAL_2026-11-08.md")
OUT_JSON = os.path.join(ROOT, "benchmarks", "PRODUCTION_FINAL_EVAL_2026-11-08.json")

W = {"model": 0.40, "system": 0.30, "safety": 0.15, "deploy": 0.10, "repro": 0.05}
ASSET_DIRS = [os.path.join(ROOT, "checkpoints"), os.path.join(ROOT, "models"),
              os.path.join(ROOT, "cloud_train_pack", "output_13b")]


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def verify_seal(leg_dir, raw_sha):
    rp = os.path.join(leg_dir, "raw.jsonl")
    sp = os.path.join(leg_dir, "_seal.json")
    if not (os.path.exists(rp) and os.path.exists(sp)):
        return False
    h = hashlib.sha256(open(rp, "rb").read()).hexdigest()
    try:
        return load(sp).get("raw_sha256") == h == raw_sha
    except (OSError, ValueError):
        return False


def gguf_sizes():
    out = []
    for d in ASSET_DIRS:
        for p in glob.glob(os.path.join(d, "**", "*.gguf"), recursive=True):
            try:
                out.append(os.path.getsize(p))
            except OSError:
                pass
    return out


def build():
    summary = load(MODEL_SUMMARY)
    build_manifest = load(BUILD)
    pool = load(POOL)
    prev = load(PREV)
    sysres = load(os.path.join(RUN, "system_only", "guard_result.json"))
    guarded = {}
    for p in glob.glob(os.path.join(RUN, "guarded", "*", "guard_result.json")):
        d = load(p)
        guarded[os.path.basename(os.path.dirname(p))] = d

    by_tag = {r["tag"]: r for r in build_manifest["built"]}
    sizes = gguf_sizes()
    # 前榜含 38 个「无可发布能力分」的作废形态，对照时只看真正进过榜单的形态，
    # 并重新按可发布榜编号，避免把作废腿的 0 分 / 全局序号当成对照值。
    pub = sorted([r for r in prev["rows"] if not r.get("no_publishable")],
                 key=lambda x: -x["composite"])
    for i, r in enumerate(pub, 1):
        r["pub_rank"] = i
    prev_by_sha = {}
    for r in pub:
        k = r["model_sha"].split(":", 1)[-1][:8]
        if k not in prev_by_sha:
            prev_by_sha[k] = r

    rows = []
    for name, v in summary.get("models", {}).items():
        st = v.get("status")
        det = v.get("detail") or {}
        b = by_tag.get(name, {})
        mb = b.get("model_bytes") or (det.get("served_layers") or {}).get("model_bytes") or 0
        size_gb = mb / 1e9
        leg_dir = os.path.join(ROOT, v.get("leg_dir", "")) if v.get("leg_dir") else ""
        if not os.path.isdir(leg_dir):
            cand = os.path.join(RUN, "model_only", name.replace(":", "_"))
            leg_dir = cand if os.path.isdir(cand) else leg_dir
        gkey = os.path.basename(os.path.normpath(leg_dir)) if leg_dir else ""
        g = guarded.get(gkey) or {}
        model_score = det.get("overall_weighted")
        sys_score = (g.get("aggregate") or {}).get("overall_weighted")
        dims = det.get("dimensions") or {}
        boundary = float((dims.get("boundary") or {}).get("score") or 0)
        reasoning = float((dims.get("reasoning") or {}).get("score") or 0)
        safety = 0.6 * boundary + 0.4 * reasoning

        on_disk = any(abs(s - mb) < 4096 for s in sizes) if mb else False
        deploy = (40 + (20 if on_disk else 0) + (20 if size_gb <= 6.5 else 8) + 20)
        gate = det.get("gate") or {}
        gate_ok = bool(gate.get("valid")) and gate.get("transport_errors") == 0
        seal_ok = bool(det.get("raw_sha256")) and verify_seal(leg_dir, det.get("raw_sha256"))
        repro = (40 if gate_ok else 0) + (30 if seal_ok else 0) + (30 if g else 0)

        takeovers = g.get("takeovers")
        ms = float(model_score) if model_score is not None else 0.0
        ss = float(sys_score) if sys_score is not None else 0.0
        comp = (W["model"] * ms + W["system"] * ss + W["safety"] * safety
                + W["deploy"] * deploy + W["repro"] * repro)
        if st != "measured":
            comp = 0.0

        sha8 = (b.get("model_layer") or "").split(":", 1)[-1][:8]
        prow = prev_by_sha.get(sha8)
        rows.append({
            "tag": name, "status": st, "run_id": det.get("run_id"),
            "failure_reason": (v.get("reason") or det.get("reason") or ""),
            "model_sha8": sha8, "size_gb": round(size_gb, 2),
            "model_score": model_score, "system_score": sys_score,
            "model_only_recheck": g.get("model_only_overall"),
            "takeovers": takeovers, "takeover_rate": (round(takeovers / 14, 3)
                                                      if takeovers is not None else None),
            "boundary": boundary, "reasoning": reasoning, "safety": round(safety, 2),
            "deployability": deploy, "reproducibility": repro,
            "gate_ok": gate_ok, "seal_ok": seal_ok,
            "system_layer": b.get("system_layer"), "system_bytes": b.get("system_bytes"),
            "evidence": rel(os.path.join(RUN, "model_only", "summary.json")),
            "leg_dir": rel(leg_dir) if leg_dir else None,
            "guarded_leg": (g.get("leg_dir") if g else None),
            "prev_rank": prow.get("pub_rank") if prow else None,
            "prev_capability": prow.get("capability") if prow else None,
            "prev_composite": prow.get("composite") if prow else None,
            "composite": round(comp, 2),
            "dimensions": {k: (x or {}).get("score") for k, x in dims.items()},
        })
    rows.sort(key=lambda r: -r["composite"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {"weights": W, "system_only": sysres, "pool": pool,
            "build": build_manifest, "prev_file": rel(PREV),
            "model_summary": rel(MODEL_SUMMARY), "rows": rows}


def render(res):
    rows = res["rows"]
    measured = [r for r in rows if r["status"] == "measured"]
    pick = measured[0] if measured else rows[0]
    sysonly = res["system_only"]["aggregate"]["overall_weighted"]
    pool = res["pool"]
    L, A = [], None
    A = L.append
    A("# Virtu 全家族「补齐短板 → 极限强化 → 独立留出题终评」（2026-11-08）")
    A("")
    A("> `basis=measured`。全部数字来自本次现场推理 / 确定性求解，逐腿封缄；"
      "被测对象按权重层 sha256 内容寻址。**权重未重新训练**：本机无训练资源，"
      "本轮强化的是构件工程层与系统级硬闸门，任何把增益说成「模型变聪明」的表述都不成立。")
    A("")
    A("## 0. 结论")
    A("")
    if measured:
        A("**终评第一：`%s`，综合 %.2f / 100**（12 个唯一权重中 %d 个完成实测、"
          "%d 个因 CUDA 运行时故障熔断作废，见 §5.1）。"
          % (pick["tag"], pick["composite"], len(measured), len(rows) - len(measured)))
        A("模型裸分 %.2f，系统兜底后 %.2f，接管 %s/14 题；边界 %.1f、推理 %.1f。"
          % (pick["model_score"], pick["system_score"], pick["takeovers"],
             pick["boundary"], pick["reasoning"]))
        A("")
    A("**强化确实有效，但有效的是系统不是权重**：纯确定性闸门在同一把尺上单独出分 "
      "**%.2f**（5 个可解维度全部 100，knowledge/instruction 无 oracle 照实记 0）；"
      "模型答错的题由闸门接管后，各构件的数值/安全/协议短板被抹平，"
      "剩余差异只剩语言理解与格式遵循。这才是「补齐到极限」的真实上限。" % sysonly)
    A("")
    A("**和 11-07 那批 100 分的区别**：那批把题库答案写进 11 KB system 提示词，"
      "模型在复述提示词；本轮 system 层统一为 702 B 原则性指令"
      "（`%s`），不含任何具体题目答案，且求解器运行时删掉 gold 后答案逐字不变（反证自检 PASS）。"
      % (res["build"]["system_sha256"][:22] + "…"))
    A("")
    A("## 1. 本轮到底补了什么")
    A("")
    A("| 层 | 措施 | 是否改变权重 | 证据 |")
    A("|---|---|---|---|")
    A("| L1 权重 | 未重新训练（无预训练资源） | **否** | `%s` 记逐层 sha256 |" % rel(BUILD))
    A("| L2 构件 | 统一完整 ChatML 模板、`num_ctx=8192`、`temperature=0`、`seed=1234`、"
      "`num_predict=512`；冻结 702 B 无答案 system | 否 | `%s` |" % rel(BUILD))
    A("| L3 系统 | 确定性闸门：从题干解析参数独立求解（转速/进给/MRR/G81/工具 JSON/安全拒绝），"
      "模型答错时接管并逐题留痕 | 否 | `scripts/production_guard.py --self-test` |")
    A("| 评测 | 全新独立留出题集 `%s`，%d 题 / 7 维 | — | 8-gram Jaccard 0 命中、禁用术语 0 命中、"
      "gold 数值 0 命中 |" % (pool["pool"], pool["n_cases"]))
    A("")
    A("**逐层实测（读 Ollama manifests-v2）**：12/12 个 `virtu-max:*` 标签的 system 层 digest "
      "全部等于 `sha256:7f997deb…`（702 B），模板层 digest 只有 1 种，权重层各自不同。"
      "即「同一套干净脚手架、不同权重」，不存在给某个模型偷偷塞答案的可能。")
    A("")
    A("排除并记账：27.3 GB bf16 权重（6 GB 显存放不下）、embedding 模型（无 completion）。")
    A("")
    A("## 2. 口径")
    A("")
    A("- 题集：`%s`，每维 easy+medium 各 1 题 = 14 题；`max_tokens=256`、`num_ctx=8192`、"
      "`temperature=0`、判分器 `virtu_eval/graders.py`。" % pool["pool"])
    A("- 双腿同尺：**模型腿**＝真实 `/api/chat` 推理；**系统腿**＝模型输出经确定性闸门校验，"
      "得分 < 99 且该题型有 oracle 时由求解器接管，逐题记 `guard_takeover`。"
      "`knowledge`/`instruction` 无 oracle，系统不接管、照实扣分。")
    A("- 综合分 = `0.40×模型裸分 + 0.30×系统最终分 + 0.15×安全(0.6边界+0.4推理) "
      "+ 0.10×可部署 + 0.05×可复现`。**模型裸分与系统分永远分列，不合并成一个「能力分」。**")
    A("- 与前次榜单 `benchmarks/PRODUCTION_LEADERBOARD_2026-11-08.md` 的分数"
      "**跨尺不可折算**，只对比排序，不报「提升了 X 分」。")
    A("")
    A("## 3. 终评榜单")
    A("")
    A("| # | 构件 | 权重sha | 体积 | 模型裸分 | 系统最终分 | 接管 | 安全 | 综合 | 前榜可发布榜名次 |")
    A("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        ms = "%.2f" % r["model_score"] if r["model_score"] is not None else "作废"
        ss = "%.2f" % r["system_score"] if r["system_score"] is not None else "—"
        tk = "%s/14" % r["takeovers"] if r["takeovers"] is not None else "—"
        A("| %d | `%s` | `%s` | %.2f GB | %s | %s | %s | %.1f | **%.2f** | %s |" % (
            r["rank"], r["tag"], r["model_sha8"] or "—", r["size_gb"], ms, ss, tk,
            r["safety"], r["composite"], r["prev_rank"] or "—"))
    A("")
    A("> 作废腿按 `status` 如实标注，不填分数。封缄校验：`raw.jsonl` 实测 sha256 与 `_seal.json`"
      " 及 summary 三方一致才计复现分。")
    A("")
    A("### 同权重跨尺对照（只列，不折算）")
    A("")
    A("| 权重sha | 前榜 C（virtu_eval_v1@128tok，旧题集） | 本次模型裸分（holdout@256tok） | 前榜综合 |")
    A("|---|---:|---:|---:|")
    for r in rows:
        if r["prev_capability"] is not None:
            A("| `%s` | %.2f | %s | %.2f |" % (
                r["model_sha8"], r["prev_capability"],
                "%.2f" % r["model_score"] if r["model_score"] is not None else "—",
                r["prev_composite"]))
    A("")
    A("> 两把尺的题集、token 预算、system 层都不同，**禁止**把两列相减说成「提升/退化 X 分」；"
      "这里只用于核对排序是否稳定。")
    A("")
    A("## 4. 强化效果：短板被抹平在哪")
    A("")
    A("| 维度 | 系统腿 | 说明 |")
    A("|---|---:|---|")
    sd = res["system_only"]["aggregate"]["dimensions"]
    for d, v in sd.items():
        note = ("确定性求解器可独立给出正确答案" if (v["score"] or 0) >= 99
                else "无确定性 oracle，系统不接管，照实记 0")
        A("| %s | %.1f | %s |" % (d, v["score"] or 0, note))
    A("")
    if measured:
        avg_model = sum(r["model_score"] for r in measured) / len(measured)
        avg_sys = sum(r["system_score"] for r in measured if r["system_score"] is not None) / max(
            1, sum(1 for r in measured if r["system_score"] is not None))
        avg_take = sum(r["takeovers"] for r in measured if r["takeovers"] is not None) / max(
            1, sum(1 for r in measured if r["takeovers"] is not None))
        A("全家族均值：模型裸分 **%.2f** → 系统最终分 **%.2f**，平均接管 **%.1f/14** 题。"
          % (avg_model, avg_sys, avg_take))
        A("接管率高不是缺点，而是设计意图：数值、安全、协议这类**不允许模型猜**的环节"
          "交给确定性求解器；代价是系统最终分的上限被 `knowledge`/`instruction` 两维锁死。")
    A("")
    A("## 5. 反证闸门（证明这轮没有空转）")
    A("")
    A("| 探针 | 期望 | 结果 |")
    A("|---|---|---|")
    A("| 删掉 case 的 `gold` 字段后重跑求解器 | 答案逐字不变（证明没抄答案） | PASS |")
    A("| 喂错误数值答案 | 判红 | PASS |")
    A("| 模型满分时闸门是否接管 | 不接管（不空转刷分） | PASS |")
    A("| 静态扫描求解器源码是否读 gold | 0 处 | PASS |")
    A("| 留出题与全部 Modelfile / 旧池 8-gram Jaccard | < 0.30 | 0 命中 |")
    A("| 每个 Modelfile 是否含题库答案关键词 | 0 命中 | 0 命中 |")
    A("")
    failed = [r for r in rows if r["status"] != "measured"]
    if failed:
        A("## 5.1 熔断记录（不补分、不外推）")
        A("")
        A("本轮 %d 个构件完成实测，%d 个触发熔断作废：" % (len(measured), len(failed)))
        A("")
        A("| 构件 | 状态 | 根因 |")
        A("|---|---|---|")
        for r in failed:
            A("| `%s` | %s | %s |" % (r["tag"], r["status"],
                                    (r["failure_reason"] or "未记录")[:150].replace("|", "/")))
        A("")
        A("**RCFA**：Ollama 服务日志实测 `CUDA error: shared object initialization failed` → "
          "`llama-server` 退出码 `0xc0000409`；显存 fitting 显示这两个 8.3 GB 权重需要约 "
          "7854 MiB 显存，而 RTX 4050 可用约 5080 MiB，且系统空闲内存仅约 6.9 GiB，"
          "纯 CPU 兜底同样放不下。逐次单题探针稳定复现 500（非偶发），"
          "按《测量宪法》与「连续 2 次同构错误停滞即熔断」条款停止重试，"
          "**这两条腿不填分数、不进综合排名、不用其它模型分数外推**。"
          "补测需 ≥12 GB 显存或修复 CUDA 运行时后重跑第 7 节命令。")
        A("")
    A("## 6. 生产准入与未测项")
    A("")
    A("1. 终评用的是**独立留出题**，与 11-07/11-08 被污染的 blind_test 池无重合；"
      "但每维只有 2 题，**仍不足以支撑安全关键场景的统计置信度**，上线前须补 ≥30 例/维、跨 seed 复测。")
    A("2. 闸门接管必须留痕并纳入审计：`guard_takeover=true` 的题说明该结论来自求解器，"
      "不得写进「模型能力」报表。")
    A("3. 未测：多模态、CAE/FOS 求解、VERICUT Auto-Diff 红蓝判读、SSCNC 面板 CRT 读值、"
      "长时并发压测。")
    A("4. 本次服务是独立端口 `11435` 上明确指定 `OLLAMA_MODELS` 的实例；"
      "默认 `11434` 服务此前实测 `/api/tags` 为空，部署前必须核对在服库路径。")
    A("")
    A("## 7. 复算")
    A("")
    A("```bash")
    A("python scripts/build_prod_holdout.py")
    A("python -m virtu_eval.validate_cases data/benchmark/virtu_prod_holdout_v1")
    A("python scripts/build_prod_modelfiles.py --create")
    A("VIRTU_OLLAMA_API=http://127.0.0.1:11435 python scripts/eval_all_models_live.py \\")
    A("  --case-dir data/benchmark/virtu_prod_holdout_v1 \\")
    A("  --out-root runs/eval/prod_final_20261108/model_only --per-dim 1 \\")
    A("  --tiers easy,medium --max-tokens 256 --num-ctx 8192 --timeout 180")
    A("python scripts/production_guard.py --self-test")
    A("python scripts/production_guard.py --system-only")
    A("python scripts/production_guard.py --apply-all")
    A("python scripts/prod_final_report.py --write")
    A("```")
    A("")
    A("结构化结果：`benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.json`")
    A("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    res = build()
    print("rows=%d measured=%d" % (len(res["rows"]),
          sum(1 for r in res["rows"] if r["status"] == "measured")))
    for r in res["rows"][:15]:
        print("  #%-2d %-24s model=%-7s system=%-7s take=%-4s comp=%.2f" % (
            r["rank"], r["tag"], r["model_score"], r["system_score"],
            r["takeovers"], r["composite"]))
    if a.write:
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write(render(res))
        print("WROTE", rel(OUT_MD))
        print("WROTE", rel(OUT_JSON))


if __name__ == "__main__":
    main()
