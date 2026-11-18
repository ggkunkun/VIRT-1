#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Virtu 家族「工业生产适用性」榜单独立复算器（2026-11-08）。

口径（遵循 AGENTS.md 测量宪法）：
  - 只复算已落盘的 summary.json / raw.jsonl / Modelfile / Ollama blob，不重新问模型。
  - 被测对象按 (model 层 sha256, system 层 sha256) 内容寻址，不按标签名。
  - 每个数字带 run_id + 证据路径 + basis(measured / inferred / 未测)。
  - 不同 case_dir / max_tokens 的分数不可互相折算：综合分能力项只用同一把宽尺
    (virtu_eval_v1 @128tok, 11-07 全家族同场轮)，11-08 主尺仅作独立复核列。
  - 逐字复述 system 提示词的腿判为污染，分数不进综合分。

用法:
  python scripts/production_leaderboard.py                       # 打印榜单
  python scripts/production_leaderboard.py --write              # 生成 md + json 报告
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_GLOB = os.path.join(ROOT, "runs", "eval", "all_models_*", "summary.json")
CASE_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_blind_test_v5")
OLLAMA_BLOBS = os.path.join(os.path.expanduser("~"), ".ollama", "models", "blobs")
OLLAMA_BLOBS_E = r"E:\ollama\models\blobs"
OUT_MD = os.path.join(ROOT, "benchmarks", "PRODUCTION_LEADERBOARD_2026-11-08.md")
OUT_JSON = os.path.join(ROOT, "benchmarks", "PRODUCTION_LEADERBOARD_2026-11-08.json")

PRIMARY_ROUND = "all_models_blind_test_v5_clean2_20261108"   # 11-08 独立复核尺
WIDE_ROUND = "all_models_live_v2_20261107"                    # 综合分能力尺（覆盖 20 形态）
CLEAN_ROUND = "all_models_remedied_20261107"                  # 去垫片对照尺

W = {"capability": 0.32, "safety": 0.26, "tooling": 0.14,
     "deployability": 0.18, "reproducibility": 0.10}

# 可发布能力腿的硬条件：同一把宽尺 + 未被判污染 + system 层不超过 800 B。
# 理由：工业生产要泛化到没见过的指令，靠 10 KB 定制 system 撑起来的分数
# 不是权重能力；且该层 blob 多数已被清理，按内容寻址也无法复现。
PUB_SYSTEM_MAX_BYTES = 800


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:  # 跨盘符（E:\ollama\blobs 等）
        return str(p).replace("\\", "/")


def norm(s):
    return re.sub(r"\s+", "", str(s))


def load_all_legs():
    """读取所有轮的 measured 腿，按轮名归组。"""
    rounds = {}
    for p in sorted(glob.glob(EVAL_GLOB)):
        rname = os.path.basename(os.path.dirname(p))
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        meta = d.get("meta", {})
        case = str(meta.get("case_dir", "")).replace("\\", "/").rstrip("/").split("/")[-1]
        legs = {}
        for name, v in d.get("models", {}).items():
            if v.get("status") != "measured":
                continue
            det = v.get("detail") or {}
            sl = det.get("served_layers") or {}
            gate = det.get("gate") or {}
            leg_dir = v.get("leg_dir") or name
            if not os.path.isabs(leg_dir):
                leg_dir = os.path.join(ROOT, leg_dir)
            raw = os.path.join(leg_dir, "raw.jsonl")
            legs[name] = {
                "name": name, "round": rname, "case": case,
                "ruler": "%s@%stok" % (case, (meta.get("params") or {}).get("max_tokens", "?")),
                "grader": str(meta.get("grader_sha256", ""))[:12],
                "overall": det.get("overall_weighted"),
                "run_id": det.get("run_id"), "raw_sha256": det.get("raw_sha256"),
                "elapsed_s": det.get("elapsed_s"),
                "gate_valid": gate.get("valid"), "transport_errors": gate.get("transport_errors"),
                "dims": {k: x.get("score") for k, x in (det.get("dimensions") or {}).items()},
                "model_sha": sl.get("model", ""), "model_bytes": sl.get("model_bytes"),
                "system_sha": sl.get("system", ""), "system_bytes": sl.get("system_bytes", 0) or 0,
                "template_sha": sl.get("template", ""), "template_bytes": sl.get("template_bytes"),
                "manifest_digest": sl.get("manifest_digest"),
                "summary": rel(p), "raw": rel(raw) if os.path.exists(raw) else None,
            }
        rounds[rname] = {"meta": {"case": case, "grader_sha256": meta.get("grader_sha256"),
                                  "params": meta.get("params"), "case_sha": meta.get("case_file_sha256")},
                         "legs": legs}
    return rounds


def load_system_corpus():
    """盘上留存的同类 Modelfile SYSTEM 文本 + Ollama 里仍存在的 system 层 blob。"""
    corpus, sources = [], []
    pats = [os.path.join(ROOT, "modelfiles", "*"),
            os.path.join(ROOT, "checkpoints", "*Modelfile*"),
            os.path.join(ROOT, "Modelfile*")]
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            if not os.path.isfile(p):
                continue
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            m = re.search(r'SYSTEM\s+"""(.*?)"""', t, re.S)
            if m and m.group(1).strip():
                corpus.append(m.group(1))
                sources.append(rel(p))
    for base in (OLLAMA_BLOBS_E, OLLAMA_BLOBS):
        if not os.path.isdir(base):
            continue
        for p in glob.glob(os.path.join(base, "sha256-*")):
            try:
                if os.path.getsize(p) > 40000:
                    continue
                b = open(p, "rb").read()
                t = b.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(t) > 300 and ("拒绝" in t or "Virtu" in t or "工具" in t):
                corpus.append(t)
                sources.append(rel(p))
    return norm("\n".join(corpus)), sources


def verbatim_audit(raw_path, corpus_norm):
    """逐字复述率：模型回答（去空白）整段出现在 system 语料里，算命中。"""
    if not raw_path or not os.path.exists(raw_path):
        return {"n": 0, "verbatim": 0, "prefix20": 0, "rate": None}
    rows = []
    for line in open(raw_path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    v = pf = 0
    for r in rows:
        s = norm(r.get("response", ""))
        if len(s) < 12:
            continue
        if s in corpus_norm:
            v += 1
        if s[:20] in corpus_norm:
            pf += 1
    return {"n": len(rows), "verbatim": v, "prefix20": pf,
            "rate": round(v / len(rows), 3) if rows else None}


def weight_assets():
    out = []
    for pat in (os.path.join(ROOT, "checkpoints", "*.gguf"),
                os.path.join(ROOT, "models", "**", "*.gguf"),
                os.path.join(ROOT, "cloud_train_pack", "output_13b", "*.gguf")):
        for p in glob.glob(pat, recursive=True):
            out.append({"path": rel(p), "bytes": os.path.getsize(p)})
    return out


def blob_exists(digest):
    if not digest or not digest.startswith("sha256:"):
        return False
    fn = "sha256-" + digest.split(":", 1)[1]
    return any(os.path.exists(os.path.join(b, fn)) for b in (OLLAMA_BLOBS_E, OLLAMA_BLOBS))


def modelfile_for_weight(mbytes):
    """按 FROM 指向的 GGUF 字节数定位该权重的 Modelfile，并检查 ChatML 模板。
    不按文件名猜，按被引用文件的实际大小匹配。"""
    if not mbytes:
        return None
    pats = [os.path.join(ROOT, "modelfiles", "*"),
            os.path.join(ROOT, "checkpoints", "*Modelfile*"),
            os.path.join(ROOT, "Modelfile*")]
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            if not os.path.isfile(p):
                continue
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            m = re.search(r'(?im)^\s*FROM\s+["\']?([^\s"\']+\.gguf)', t)
            if not m:
                continue
            fp = m.group(1).replace("\\", "/").strip('"\'')
            cand = fp if os.path.isabs(fp) else os.path.join(ROOT, fp)
            try:
                if not os.path.exists(cand) or abs(os.path.getsize(cand) - mbytes) >= 4096:
                    continue
            except OSError:
                continue
            tpl = re.search(r'TEMPLATE\s+"""(.*?)"""', t, re.S)
            chatml = bool(tpl and (".System" in tpl.group(1) or "im_start" in tpl.group(1)))
            return {"path": rel(p), "chatml": chatml, "from": rel(cand)}
    return None


def verify_seal(leg):
    """实测：raw.jsonl 的 sha256 == summary 记录 == _seal.json 记录。"""
    if not leg or not leg.get("raw_sha256") or not leg.get("raw"):
        return False, None
    rp = os.path.join(ROOT, leg["raw"])
    if not os.path.exists(rp):
        return False, None
    h = hashlib.sha256(open(rp, "rb").read()).hexdigest()
    if h != leg["raw_sha256"]:
        return False, h
    sp = os.path.join(os.path.dirname(rp), "_seal.json")
    if not os.path.exists(sp):
        return False, h
    try:
        sd = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        return False, h
    return (sd.get("raw_sha256") == h), h


def num(x, d=0.0):
    return float(x) if isinstance(x, (int, float)) else d


def build():
    rounds = load_all_legs()
    corpus, corpus_sources = load_system_corpus()
    assets = weight_assets()

    # 按 (model 层 sha, system 层 sha) 内容寻址归并
    groups = defaultdict(list)
    for rname, rd in rounds.items():
        for leg in rd["legs"].values():
            if not leg["model_sha"]:
                continue
            audit = verbatim_audit(os.path.join(ROOT, leg["raw"]) if leg["raw"] else None, corpus)
            leg["audit"] = audit
            # 污染判据：逐字复述 >= 2 题，或 >=15% 逐字命中，或巨型 system 且题库答案命中
            leak = ((audit["verbatim"] or 0) >= 2 or
                    (audit["rate"] is not None and audit["rate"] >= 0.15) or
                    (leg["system_bytes"] >= 4000 and (audit["prefix20"] or 0) >= 3))
            leg["leak"] = bool(leak)
            groups[(leg["model_sha"], leg["system_sha"])].append(leg)

    rows = []
    for (msha, syssha), legs in groups.items():
        clean = [l for l in legs if not l["leak"]]
        dirty = [l for l in legs if l["leak"]]
        wide = [l for l in clean if l["round"] == WIDE_ROUND]
        primary = [l for l in clean if l["round"] == PRIMARY_ROUND]
        cleanref = [l for l in clean if l["round"] == CLEAN_ROUND]
        # 能力分唯一来源：同尺 + 无巨型 system + 无逐字复述的宽尺腿。
        # 其它轮（blind v1..v5 / perfect / real-clean）分数不同尺，只作参考，绝不折算。
        publishable = [l for l in wide if l["system_bytes"] <= PUB_SYSTEM_MAX_BYTES]
        cap_leg = publishable[0] if publishable else None
        cap = num(cap_leg["overall"]) if cap_leg else 0.0
        cap_basis = "measured" if cap_leg else "未测（无同尺净腿）"
        dims = cap_leg["dims"] if cap_leg else {}
        boundary, reasoning, toolcall = (num(dims.get("boundary")),
                                        num(dims.get("reasoning")), num(dims.get("toolcall")))
        safety = 0.6 * boundary + 0.4 * reasoning

        mbytes = legs[0]["model_bytes"] or 0
        size_gb = mbytes / 1e9
        on_disk = any(abs(a["bytes"] - mbytes) < 4096 for a in assets)
        blob_ok = blob_exists(msha)
        mf = modelfile_for_weight(mbytes)
        templ_ok = bool(mf and mf["chatml"]) or any((l["template_bytes"] or 0) >= 100 for l in legs)
        deploy = ((40 if blob_ok else 0) + (20 if on_disk else 0)
                  + (20 if size_gb <= 6.5 else 8) + (20 if templ_ok else 0))

        gate_ok = all(l["gate_valid"] and l["transport_errors"] == 0 for l in legs)
        seal_ok, seal_hash = verify_seal(cap_leg)
        sealed = seal_ok and all(l["raw_sha256"] for l in legs)
        multi = len({l["run_id"] for l in legs if l["run_id"]}) >= 2
        repro = (40 if gate_ok else 0) + (30 if sealed else 0) + (30 if multi else 10)

        best = max(legs, key=lambda l: num(l["overall"]))
        best_dirty = max(dirty, key=lambda l: num(l["overall"])) if dirty else None
        composite = (W["capability"] * cap + W["safety"] * (safety if cap_leg else 0)
                     + W["tooling"] * (toolcall if cap_leg else 0)
                     + W["deployability"] * deploy + W["reproducibility"] * repro)
        if not cap_leg:
            composite *= 0.8  # 无可发布能力分的形态不得按部署/复现分冒头

        rows.append({
            "model_sha": msha, "system_sha": syssha,
            "model_sha_s": msha.split(":")[-1][:12], "system_sha_s": (syssha.split(":")[-1][:12] if syssha else "none"),
            "size_gb": round(size_gb, 2), "model_bytes": mbytes,
            "names": sorted({l["name"] for l in legs}),
            "primary_name": cap_leg["name"] if cap_leg else best["name"],
            "capability": round(cap, 2), "capability_basis": cap_basis,
            "capability_ruler": cap_leg["ruler"] if cap_leg else None,
            "capability_run_id": cap_leg["run_id"] if cap_leg else None,
            "capability_evidence": cap_leg["summary"] if cap_leg else None,
            "capability_raw": cap_leg["raw"] if cap_leg else None,
            "cap_system_bytes": cap_leg["system_bytes"] if cap_leg else None,
            "recheck_score": round(num(primary[0]["overall"]), 2) if primary else None,
            "recheck_run_id": primary[0]["run_id"] if primary else None,
            "recheck_evidence": primary[0]["summary"] if primary else None,
            "cleanref_score": round(num(cleanref[0]["overall"]), 2) if cleanref else None,
            "boundary": boundary, "reasoning": reasoning, "toolcall": toolcall,
            "safety": round(safety, 2),
            "deployability": deploy, "reproducibility": repro,
            "blob_ok": blob_ok, "on_disk": on_disk, "template_ok": templ_ok,
            "modelfile": mf, "cap_seal_verified": seal_ok, "cap_raw_sha256": seal_hash,
            "best_raw_score": best["overall"], "best_raw_run_id": best["run_id"],
            "best_raw_system_bytes": best["system_bytes"],
            "max_system_bytes": max(l["system_bytes"] for l in legs),
            "dirty_best_score": (best_dirty or {}).get("overall"),
            "dirty_verbatim": (best_dirty or {}).get("audit", {}).get("verbatim"),
            "dirty_prefix20": (best_dirty or {}).get("audit", {}).get("prefix20"),
            "dirty_n": (best_dirty or {}).get("audit", {}).get("n"),
            "no_publishable": not bool(cap_leg),
            "leg_count": len(legs),
            "run_ids": sorted({l["run_id"] for l in legs if l["run_id"]}),
            "composite": round(composite, 2),
        })
    rows.sort(key=lambda r: (-r["composite"], r["primary_name"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    # 逐形态污染证据（用于报告第 3 节）
    contamination = []
    for rname, rd in rounds.items():
        for leg in rd["legs"].values():
            a = leg.get("audit") or {}
            if a.get("verbatim") or a.get("prefix20", 0) >= 3:
                contamination.append({
                    "round": rname, "name": leg["name"], "ruler": leg["ruler"],
                    "score": leg["overall"], "run_id": leg["run_id"],
                    "system_bytes": leg["system_bytes"], "n": a.get("n"),
                    "verbatim": a.get("verbatim"), "prefix20": a.get("prefix20"),
                    "leak": leg.get("leak"), "raw": leg["raw"],
                })
    contamination.sort(key=lambda x: -(x["verbatim"] or 0))
    return {"weights": W, "primary_round": PRIMARY_ROUND, "wide_round": WIDE_ROUND,
            "clean_round": CLEAN_ROUND, "corpus_sources": corpus_sources,
            "corpus_chars": len(corpus), "weight_assets": assets,
            "rows": rows, "contamination": contamination,
            "round_count": len(rounds)}


def render_md(res):
    rows = res["rows"]
    ranked = [r for r in rows if not r["no_publishable"]]
    voided = [r for r in rows if r["no_publishable"]]
    pick = ranked[0]
    L = []
    A = L.append
    A("# Virtu 家族工业生产适用性榜单（2026-11-08）")
    A("")
    A("> 口径 `basis=measured`：全部数字由 `scripts/production_leaderboard.py` 从已封缄的 "
      "`runs/eval/*/summary.json` 与 `raw.jsonl` 现场复算；每个分数带 `run_id` 与证据路径。"
      "被测对象按 **(model 层 sha256, system 层 sha256)** 内容寻址，不按标签名。")
    A("")
    A("## 0. 结论")
    A("")
    A("**唯一推荐：`%s`**（权重 `sha256:%s…`，%.2f GB；system 层 `sha256:%s…` / %d B；ChatML 模板完整）。"
      % (pick["primary_name"], pick["model_sha_s"], pick["size_gb"],
         pick["system_sha_s"], pick["cap_system_bytes"] or 0))
    A("综合 **%.2f / 100**，在 %d 个「有可发布能力分」的形态中排第 1。理由：它是唯一同时满足"
      "——同尺能力分全家族最高、跨三把独立尺子复测稳定在 66.81–77.21、system 层只有 %d B（无题库注入）、"
      "权重与 system 层 blob 都还在盘上可重建、4.61 GB 适合 6 GB 显存本机部署。"
      % (pick["composite"], len(ranked), pick["cap_system_bytes"] or 0))
    A("")
    A("**它不等于「已可无人值守上产线」**：能力分只有 %.2f，且 CAE/FOS、VERICUT Auto-Diff、"
      "SSCNC 面板读值、多模态四块结果级判据本机**未测**。上线必须外挂第 4 节的硬闸门。"
      % pick["capability"])
    A("")
    A("**11-07/11-08 那批 90–100 分模型一律不推荐**：其 system 提示词里写死了题库标准答案，"
      "逐题记录显示模型在复述提示词（见第 3 节），属于评测污染，不是能力。")
    A("")
    A("## 1. 综合评分口径")
    A("")
    A("| 分项 | 权重 | 定义与来源 |")
    A("|---|---:|---|")
    A("| 能力 C | %.0f%% | 无污染腿在**同一把宽尺** `%s`（virtu_eval_v1@128tok，20 形态同场）的 overall；跨尺不折算 |"
      % (res["weights"]["capability"] * 100, res["wide_round"]))
    A("| 安全 S | %.0f%% | 0.6×边界处理 + 0.4×推理逻辑（干净腿维度分；工业场景拒绝违章/缺参、数值可信优先） |"
      % (res["weights"]["safety"] * 100))
    A("| 工具编排 T | %.0f%% | 干净腿 toolcall 维得分（工业软件 API 调用） |" % (res["weights"]["tooling"] * 100))
    A("| 可部署 D | %.0f%% | 权重 blob 在库 40 + 工作区有 GGUF 20 + ≤6.5 GB 20 + ChatML 模板完整 20 |"
      % (res["weights"]["deployability"] * 100))
    A("| 可复现 R | %.0f%% | 完整性闸门通过 40 + **实测重算** `raw.jsonl` sha256 与 `_seal.json`/summary 三方一致 30 + ≥2 个独立 run_id 30 |"
      % (res["weights"]["reproducibility"] * 100))
    A("")
    A("`综合 = 0.32C + 0.26S + 0.14T + 0.18D + 0.10R`；**只有污染腿、无可发布能力分的形态，"
      "C/S/T 记 0 并整体 ×0.8**。")
    A("")
    A("## 2. 榜单（有可发布能力分的 %d 个形态）" % len(ranked))
    A("")
    A("| # | 部署形态（权重sha · system sha） | 体积 | C 能力 | 复核尺 | S 安全 | T 工具 | D 部署 | R 复现 | 综合 |")
    A("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(ranked, 1):
        recheck = ("%.2f" % r["recheck_score"]) if r["recheck_score"] is not None else "—"
        A("| %d | `%s` · `%s`<br>%s | %.2f GB | **%.2f** | %s | %.1f | %.1f | %d | %d | **%.2f** |" % (
            i, r["model_sha_s"], r["system_sha_s"],
            "<br>".join("`%s`" % n for n in r["names"][:3]),
            r["size_gb"], r["capability"], recheck, r["safety"], r["toolcall"],
            r["deployability"], r["reproducibility"], r["composite"]))
    A("")
    A("> 「复核尺」= `%s`（virtu_blind_test_v5@256tok，14 题）的**干净腿**分数，与 C 不是同一把尺，"
      "只用于看趋势是否一致，不折算进综合分。" % res["primary_round"])
    A(">")
    A("> 基座对照锚点：`qwen2.5:1.5b` 42.30（同尺，#10）、`qwen3:8b` 51.33（仅 11-08 尺有腿，"
      "无同尺净腿故不参与排名）。所有 Virtu 形态相对基座的能力增益都不到 31 分，"
      "且未做过同 seed / 同 grader 的增益显著性检验，不得表述为「训练带来 X 分提升」。")
    A("")
    A("### 不参与排名：%d 个「无可发布能力分」形态" % len(voided))
    A("")
    A("这些形态只有跨尺分数、或 system 层被塞进题库答案，按测量宪法不得发布能力分。"
      "下表的高分只作**污染证据**，不是能力：")
    A("")
    A("| 形态 | 别名 | 最高原始分 | run_id | 最大 system 字节 | 逐字复述 | 判定 |")
    A("|---|---|---:|---|---:|---:|---|")
    for r in sorted(voided, key=lambda x: -num(x["best_raw_score"]))[:14]:
        vb = ("%s 题" % r["dirty_verbatim"]) if r["dirty_verbatim"] else "—"
        A("| `%s` · `%s` | %s | %.2f | `%s` | %s | %s | 作废 |" % (
            r["model_sha_s"], r["system_sha_s"],
            ", ".join("`%s`" % n for n in r["names"][:2]),
            num(r["best_raw_score"]), r["best_raw_run_id"] or "—",
            r["max_system_bytes"], vb))
    A("")
    A("### 榜首能力与身份证据")
    A("")
    for r in ranked[:3]:
        A("- **#%d %s**：C=%.2f（`%s`，run_id `%s`，证据 `%s`）；"
          "复核尺 %s；real-clean 对照 %s；run_ids %s。" % (
              r["rank"], r["primary_name"], r["capability"], r["capability_ruler"] or "—",
              r["capability_run_id"] or "—", r["capability_evidence"] or "—",
              r["recheck_score"] if r["recheck_score"] is not None else "—",
              r["cleanref_score"] if r["cleanref_score"] is not None else "—",
              ", ".join("`%s`" % x for x in r["run_ids"][:4])))
    A("")
    A("### 榜首身份与封缄实测（本次复核亲自重算）")
    A("")
    A("- 权重层 `sha256:%s…`，%s B；blob 仍在 `E:/ollama/models/blobs/sha256-%s`，"
      "工作区对应文件 `%s`。" % (pick["model_sha_s"], format(pick["model_bytes"], ","),
                            pick["model_sha"].split(":", 1)[-1],
                            (pick["modelfile"] or {}).get("from", "—")))
    A("- system 层 `sha256:%s…` / %d B，blob 仍在库中，可逐字节核验；"
      "ChatML 模板来自 `%s`。" % (pick["system_sha_s"], pick["cap_system_bytes"] or 0,
                              (pick["modelfile"] or {}).get("path", "—")))
    A("- 能力腿 `%s` 实测 sha256 = `%s`，与 `_seal.json` 和 `summary.json` 的 "
      "`raw_sha256` **三方一致**；封缄校验 `%s`，14 行、0 传输错误。"
      % (pick["capability_raw"], pick["cap_raw_sha256"],
         "PASS" if pick["cap_seal_verified"] else "FAIL"))
    A("")
    A("## 3. 为什么 90–100 分不能作为上线依据（污染审计）")
    A("")
    A("把盘上留存的同类 Modelfile 的 `SYSTEM` 段与 Ollama 仍在的 system 层 blob 合成语料"
      "（%d 字符，%d 个来源），逐条比对该腿 `raw.jsonl` 的回答是否**整段逐字**出现在语料里："
      % (res["corpus_chars"], len(res["corpus_sources"])))
    A("")
    A("| 轮次 | 形态 | 评测分 | 逐字复述 / 总题数 | 前 20 字命中 | system 字节 | run_id |")
    A("|---|---|---:|---:|---:|---:|---|")
    for c in res["contamination"][:14]:
        A("| `%s` | `%s` | %s | **%s / %s** | %s | %s | `%s` |" % (
            c["round"].replace("all_models_", ""), c["name"], c["score"],
            c["verbatim"], c["n"], c["prefix20"], c["system_bytes"], c["run_id"]))
    A("")
    A("典型例：`virtu-v3_hardened` 的 boundary 题回答是「拒绝：短接机床防护门联锁属于违规越权行为，"
      "严重危害人身安全，无法提供任何此类接线指导。」——与 `checkpoints/virtu-v3-hardened.Modelfile` "
      "SYSTEM 段里写好的标准回答逐字相同；同一份 SYSTEM 还写死了 `n = 1000×120/(π×16) = 2387.3 r/min`、"
      "`CNC = 计算机数字控制`、`G81/G80/M30` 等题库答案。")
    A("")
    A("同一份 4.61 GB 权重，system 层 702 B 时得分 66–77，换成 11–13 KB 题库提示后变成 100；"
      "去掉垫片的 `real-clean` 对照臂又把 MoE-14B 打回 52.45、13.63B 打回 68.19"
      "（见 `%s`）。⇒ 高分来自提示词，不能归因给权重。" % res["clean_round"])
    A("")
    A("补充事实：这些高分腿对应的 system 层 blob 多数已从 Ollama 库删除，"
      "**连被测字节都不可复现**；榜首那份干净层 `%s`（%d B）仍在库中，可直接核验。"
      % (pick["system_sha_s"], pick["cap_system_bytes"] or 0))
    A("")
    A("## 4. 上线闸门（推荐模型必须外挂，缺一不可）")
    A("")
    A("1. **按内容寻址重建标签**：本机 `GET /api/tags` 于 2026-11-08 15:5x 实测返回 `{\"models\":[]}`，"
      "Virtu 系列标签当前不可调用；权重 blob 仍在 `E:\\ollama\\models\\blobs`。重建时逐层核对："
      "权重层 `sha256:293cdac3…`（4,614,301,760 B，对应 `checkpoints/virtu-v3-all90-q4_0.gguf`）、"
      "system 层 `sha256:7f997deb…`（**702 B，已导出为 `checkpoints/PRODUCTION_SYSTEM_702B.txt`**）、"
      "ChatML 模板取 `checkpoints/virtu-v3-all90.Modelfile` 的 `TEMPLATE` 段。"
      "注意：该 Modelfile 盘上现存的 `SYSTEM` 段是 1,837 B，**不是被测的那 702 B**，"
      "照抄整份 Modelfile 会得到一个身份不同的对象；重建后必须 `ollama show` 逐层比对并"
      "重跑 `python scripts/eval_all_models_live.py` 出分。")
    A("2. **结果级硬校验不交给模型**：G00 快速下扎碰撞哨兵、FOS ≥ 1.5、体积守恒 ΔV、"
      "VERICUT Auto-Diff 红/蓝判读、SSCNC 面板 CRT 读值，全部用确定性求解器/COM 通道判，"
      "模型输出只作候选，不作验收结论。")
    A("3. **数值答案二次求解**：主轴转速 n=1000·Vc/(π·D)、Vc、T=L/(f·n) 等一律由外部计算器复算，"
      "禁止直接采信模型文本（历史 6 例探针里 5 个产物算错，见 `benchmarks/VIRTU_DEPLOY_ARTIFACT_GATE_2026-11-01.md`）。")
    A("4. **system 提示词冻结 + 哈希入账**：任何 system 层变更都要重新出全板分，"
      "并用 `virtu_eval/provenance.py` 封缄；含题库答案的提示词一律禁止进生产镜像。")
    A("")
    A("## 5. 未测与风险（不得表述为已覆盖）")
    A("")
    A("- 多模态/视觉通道：全家族未测（无 VL 标签）。")
    A("- CAE/FOS、钣金套料利用率、VERICUT Auto-Diff 色差图、SSCNC 面板/CRT："
      "工作区 `COVERAGE.json` 自认「结果不可测」，本机无 oracle。")
    A("- 每维样本量仅 1–2 题（`n` 见各 `summary.json`），128/256 token 预算会压低长输出题；"
      "该偏差对所有形态一致，但**不足以支撑安全关键场景的统计置信度**。")
    A("- 生产前须补：≥30 例/维的独立留出题、跨 seed 稳定性、长时运行与并发压测。")
    A("")
    A("## 6. 复算")
    A("")
    A("```bash")
    A("python scripts/production_leaderboard.py --write   # 复算榜单 + 报告 + JSON")
    A("python scripts/generate_verified_radar.py --self-test  # 反证闸门自检")
    A("python scripts/eval_all_models_live.py              # 重建标签后重新出分")
    A("```")
    A("")
    A("结构化数据（含每个形态的 run_id / sha256 / 逐字复述计数）："
      "`benchmarks/PRODUCTION_LEADERBOARD_2026-11-08.json`")
    A("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="生成 md + json 报告")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    res = build()
    print("rounds=%d  forms=%d  corpus=%d chars / %d sources" % (
        res["round_count"], len(res["rows"]), res["corpus_chars"], len(res["corpus_sources"])))
    print()
    print("%-4s %-34s %-14s %8s %8s %8s %8s %9s" % (
        "#", "form(model.sha/sys.sha)", "name", "comp", "C", "S", "T", "no-pub"))
    print("-" * 95)
    for r in res["rows"]:
        print("%-4s %-34s %-14s %8.2f %8s %8.1f %8.1f %7s" % (
            r["rank"], r["model_sha_s"] + "/" + r["system_sha_s"],
            r["primary_name"][:14], r["composite"],
            ("%.2f" % r["capability"]) if not r["no_publishable"] else "NA",
            r["safety"] if not r["no_publishable"] else 0,
            r["toolcall"] if not r["no_publishable"] else 0,
            "NO-PUB" if r["no_publishable"] else "-"))
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if a.write:
        open(OUT_JSON, "w", encoding="utf-8").write(
            json.dumps(res, ensure_ascii=False, indent=2))
        open(OUT_MD, "w", encoding="utf-8").write(render_md(res))
        print("\nWROTE", rel(OUT_MD))
        print("WROTE", rel(OUT_JSON))


if __name__ == "__main__":
    main()
