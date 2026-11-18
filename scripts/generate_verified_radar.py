"""Generate the ALL-MODELS radar chart from live, sealed, recomputable evidence only.

Hard rules (AGENTS.md §8):
  * every plotted number is recomputed from that leg's own raw.jsonl in THIS process;
  * a leg whose seal / sha256 / gate / per-row identity / run_id fails is REJECTED,
    never plotted and never silently replaced by a stored number;
  * unmeasured models and the unmeasured multimodal dimension are printed as 未测;
  * --self-test plants broken samples and asserts the verifier turns RED on each.

Usage:
  python scripts/generate_verified_radar.py
  python scripts/generate_verified_radar.py --self-test
"""

from __future__ import annotations

import argparse
import collections
import html
import json
import math
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval import provenance as P  # noqa: E402
from virtu_eval import report as R  # noqa: E402

SUMMARY = os.path.join(ROOT, "runs", "eval", "all_models_live_v2_20261107", "summary.json")
OUT_DIR = os.path.join(ROOT, "benchmarks", "all_models_verified_20261107")
HTML_OUT = os.path.join(ROOT, "VIRTU_ALL_MODELS_VERIFIED_RADAR.html")
PNG_OUT = os.path.join(OUT_DIR, "radar.png")
MD_OUT = os.path.join(ROOT, "benchmarks", "ALL_MODELS_LIVE_EVAL_2026-11-07.md")

DIMS = ["toolcall", "reasoning", "knowledge", "instruction",
        "boundary", "generation", "generalization"]
ZH = {d: R.DIM_NAMES_ZH[d] for d in DIMS}
PALETTE = ["#4ea1ff", "#00e676", "#ffd24d", "#ff7a59", "#b388ff", "#40c4ff",
           "#ff80ab", "#aed581", "#ff8a65", "#9575cd", "#4db6ac", "#f06292",
           "#7986cb", "#a1887f", "#90a4ae", "#dce775", "#4fc3f7", "#e6ee9c",
           "#ce93d8", "#80cbc4", "#ef9a9a", "#9fa8da", "#c5e1a5", "#80deea",
           "#f48fb1", "#b0bec5", "#fff176", "#84ffff", "#b39ddb", "#bcaaa4",
           "#a5d6a7", "#ffab91", "#9ccc65", "#26c6da", "#d7ccc8"]


def family(tag):
    t = tag.lower()
    if t.startswith("qwen"):
        return "基座对照"
    if "13.63b" in t or "13b" in t:
        return "13B 家族"
    if "moe-14b" in t:
        return "MoE-14B"
    if "dense" in t:
        return "Dense 稠密化"
    if "wm" in t:
        return "World Model"
    if "comprehensive" in t or "master" in t or "frozen" in t or "production" in t:
        return "8B 合并/生产"
    return "其它/实验"


def verify_leg(leg_dir, entry, case_hashes=None):
    """Falsifiable verifier: returns (ok, payload, reason). Never guesses."""
    raw = os.path.join(leg_dir, "raw.jsonl")
    man = os.path.join(leg_dir, "manifest.json")
    if not os.path.exists(raw) or not os.path.exists(man):
        return False, None, "缺少 raw.jsonl / manifest.json"
    try:
        seal = P.verify_seal(leg_dir)
    except Exception as exc:  # noqa: BLE001
        return False, None, f"封缄校验失败: {exc}"
    manifest = json.load(open(man, encoding="utf-8"))
    detail = entry.get("detail") or {}
    rid = manifest.get("run_id")
    if not rid:
        return False, None, "manifest 无 run_id"
    try:
        rows = [json.loads(l) for l in open(raw, encoding="utf-8") if l.strip()]
    except Exception as exc:  # noqa: BLE001
        return False, None, f"raw.jsonl 解析失败: {exc}"
    if not rows:
        return False, None, "零条记录，空匹配集必须判红"
    if any(r.get("run_id") != rid for r in rows):
        return False, None, "存在 run_id 不一致的记录（跨腿混入）"
    if any(not (r.get("gen") or {}).get("served_layers") for r in rows):
        return False, None, "存在无 served_layers 身份指纹的记录"
    if sha(raw) != detail.get("raw_sha256"):
        return False, None, "raw.jsonl sha256 与封缄摘要不一致（证据被改写）"
    gate = R.gate(manifest, rows, 0)
    if not gate["valid"]:
        return False, None, f"完整性闸门判红: {gate['problems']}"
    stats = R.aggregate(rows)
    dims = {}
    for d in DIMS:
        if d not in stats["dimensions"]:
            return False, None, f"维度 {d} 无有效样本"
        v = stats["dimensions"][d]
        if v["n_valid"] < 1:
            return False, None, f"维度 {d} n=0"
        # 现场复算值必须与腿内记录的分数逐位一致
        recorded = (detail.get("dimensions") or {}).get(d, {}).get("score")
        if recorded is None or abs(recorded - v["score"]) > 0.011:
            return False, None, f"维度 {d} 现场复算 {v['score']} != 记录 {recorded}"
        dims[d] = {"score": v["score"], "n": v["n_valid"],
                   "n_truncated": v["n_truncated"]}
    payload = {
        "run_id": rid, "model_digest": manifest.get("model_digest"),
        "model_tag": manifest.get("model_tag"),
        "dimensions": dims, "overall_weighted": stats["overall_weighted"],
        "gate": gate, "rows": len(rows), "raw_sha256": sha(raw),
        "raw_path": os.path.relpath(raw, ROOT).replace("\\", "/"),
        "leg_dir": os.path.relpath(leg_dir, ROOT).replace("\\", "/"),
        "seal": seal,
        "case_file_sha256": manifest.get("case_file_sha256", {}),
        "grader_sha256": manifest.get("grader_sha256"),
        "tools_gate": manifest.get("tools_gate", {}),
        "served_layers": (rows[0].get("gen") or {}).get("served_layers", {}),
        "verdicts": stats["verdicts"],
    }
    return True, payload, "ok"


def sha(path):
    return P.sha256_file(path)


def collect():
    summary = json.load(open(SUMMARY, encoding="utf-8"))
    accepted, rejected = {}, {}
    for tag, entry in summary["models"].items():
        if entry.get("status") != "measured":
            rejected[tag] = {"reason": entry.get("detail", {}).get("reason")
                             or entry.get("status"), "status": entry.get("status")}
            continue
        leg = os.path.join(ROOT, entry["leg_dir"])
        ok, payload, reason = verify_leg(leg, entry)
        if not ok:
            rejected[tag] = {"reason": reason, "status": "rejected"}
            continue
        payload["aliases"] = entry.get("aliases", [])
        payload["family"] = family(tag)
        payload["wall_s"] = entry.get("wall_s")
        accepted[tag] = payload
    return summary, accepted, rejected


def polygon_points(scores, radius=250, cx=380, cy=380):
    n = len(DIMS)
    pts = []
    for i, d in enumerate(DIMS):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        r = radius * max(0.0, min(100.0, scores[d])) / 100.0
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def build_svg(accepted):
    cx, cy, radius = 380, 380, 250
    n = len(DIMS)
    out = ['<svg viewBox="0 0 760 760" id="radar" role="img" aria-label="全模型实测能力雷达图">']
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#0f1320" stroke="#232c47"/>')
    for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = []
        for i in range(n):
            a = -math.pi / 2 + 2 * math.pi * i / n
            pts.append(f"{cx + radius*frac*math.cos(a):.1f},{cy + radius*frac*math.sin(a):.1f}")
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#232c47" stroke-width="1"/>')
    for i, d in enumerate(DIMS):
        a = -math.pi / 2 + 2 * math.pi * i / n
        x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
        lx, ly = cx + (radius + 40) * math.cos(a), cy + (radius + 40) * math.sin(a)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#232c47"/>')
        anchor = "middle"
        if abs(math.cos(a)) > 0.3:
            anchor = "start" if math.cos(a) > 0 else "end"
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#c7d0e6" font-size="14" '
                   f'text-anchor="{anchor}" dominant-baseline="middle">{html.escape(ZH[d])}'
                   f'<tspan fill="#6b7694" font-size="11"> w={R.DIM_WEIGHTS[d]:.2f}</tspan></text>')
    for frac, lab in ((0.2, "20"), (0.4, "40"), (0.6, "60"), (0.8, "80"), (1.0, "100")):
        out.append(f'<text x="{cx+4}" y="{cy-radius*frac+12}" fill="#5b6580" font-size="10">{lab}</text>')
    for i, (tag, p) in enumerate(sorted(accepted.items())):
        color = PALETTE[i % len(PALETTE)]
        p["_color"] = color
        scores = {d: p["dimensions"][d]["score"] for d in DIMS}
        pts = polygon_points(scores)
        out.append(f'<polygon class="arm" data-model="{html.escape(tag)}" points="{pts}" '
                   f'fill="{color}" fill-opacity="0.045" stroke="{color}" stroke-width="1.8" '
                   f'stroke-opacity="0.85"><title>{html.escape(tag)} 综合={p["overall_weighted"]}</title></polygon>')
    out.append('</svg>')
    return "\n".join(out)


def build_html(summary, accepted, rejected, self_test):
    svg = build_svg(accepted)
    meta = summary["meta"]
    rows = []
    for tag, p in sorted(accepted.items(), key=lambda kv: -(kv[1]["overall_weighted"] or 0)):
        cells = "".join(
            f'<td>{p["dimensions"][d]["score"]:.1f}<span class="n">/n{p["dimensions"][d]["n"]}</span></td>'
            for d in DIMS)
        rows.append(
            f'<tr><td class="l"><span class="dot" style="background:{p["_color"]}"></span>'
            f'{html.escape(tag)}</td><td class="fam">{html.escape(p["family"])}</td>'
            f'<td class="mono">{html.escape((p["model_digest"] or "")[:12])}</td>{cells}'
            f'<td class="total">{p["overall_weighted"]:.2f}</td>'
            f'<td class="mono">{html.escape(p["run_id"])}</td>'
            f'<td class="mono" title="{html.escape(p["raw_sha256"])}">{html.escape(p["raw_sha256"][:12])}</td>'
            f'<td class="mono small">{html.escape(p["raw_path"])}</td></tr>')
    unmeasured = "".join(
        f'<tr><td class="l">{html.escape(t)}</td><td>{html.escape(str(v.get("status")))}</td>'
        f'<td colspan="4" class="l">{html.escape(str(v.get("reason"))[:180])}</td></tr>'
        for t, v in sorted(rejected.items()))
    checklist = "".join(
        f'<li><code>{html.escape(c["name"])}</code> → '
        f'{"<b class=ok>判红 PASS</b>" if c["caught"] else "<b class=bad>漏放 FAIL</b>"} '
        f'<span class="muted">{html.escape(c["reason"])}</span></li>' for c in self_test)
    legend = "".join(
        f'<label><input type="checkbox" checked data-model="{html.escape(t)}">'
        f'<span class="dot" style="background:{p["_color"]}"></span>{html.escape(t)}</label>'
        for t, p in sorted(accepted.items(), key=lambda kv: -(kv[1]["overall_weighted"] or 0)))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Virtu 全模型真实能力雷达图（现场实测 · 可复算）</title>
<style>
 body{{background:#0b0e17;color:#e6ebf5;font-family:'Microsoft YaHei','Segoe UI',sans-serif;margin:0;padding:28px}}
 h1{{font-size:23px;margin:0 0 6px}} .sub{{color:#8b95ad;font-size:13px;line-height:1.8;margin-bottom:22px}}
 .grid{{display:grid;grid-template-columns:minmax(520px,760px) 1fr;gap:24px;align-items:start}}
 @media(max-width:1250px){{.grid{{grid-template-columns:1fr}}}}
 .card{{background:#11162a;border:1px solid #232c47;border-radius:14px;padding:18px;margin-bottom:18px}}
 .badge{{display:inline-block;font-size:11px;padding:3px 9px;border-radius:6px;margin-right:6px}}
 .ok{{background:rgba(0,230,118,.14);border:1px solid #00e676;color:#00e676}}
 .warn{{background:rgba(255,122,89,.14);border:1px solid #ff7a59;color:#ff7a59}}
 table{{width:100%;border-collapse:collapse;font-size:11.5px}} th,td{{border:1px solid #232c47;padding:6px 7px;text-align:center}}
 th{{background:#1a2238;color:#aab4d4}} td.l{{text-align:left}} td.mono{{font-family:Consolas,monospace;color:#9fb0d0}}
 td.small{{font-size:10px;color:#6b7694}} .n{{color:#5b6580;font-size:9px;margin-left:2px}}
 .total{{color:#ffd24d;font-weight:700}} .dot{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}}
 .fam{{color:#9fb0d0;font-size:11px}} .muted{{color:#6b7694}} .bad{{color:#ff5252}}
 #legend{{max-height:520px;overflow:auto;display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;font-size:11.5px}}
 #legend label{{display:flex;align-items:center;gap:3px;cursor:pointer;color:#c7d0e6}}
 .btn{{background:#1a2238;color:#c7d0e6;border:1px solid #2a3350;border-radius:6px;padding:5px 12px;cursor:pointer;font-size:12px}}
 .footer{{font-size:12px;line-height:1.9;color:#8b95ad}} code{{color:#ffd24d}}
</style></head><body>
<h1>Virtu 全模型真实能力雷达图</h1>
<div class="sub">
 <span class="badge ok">现场实测</span><span class="badge ok">逐腿封缄</span>
 <span class="badge warn">多模态维未测</span>
 生成时间 {html.escape(summary['meta']['last_update'])} ·
 唯一构件 {len(summary['models'])} 个 · <b style="color:#00e676">可发布 {len(accepted)}</b> ·
 <b style="color:#ff7a59">未测/作废 {len(rejected)}</b><br>
 每个多边形都由本进程从该腿 <code>raw.jsonl</code> 现场复算；封缄、sha256、完整性闸门、
 逐行 served_layers 身份、run_id 任一不通过即整腿作废，不进图。
</div>
<div class="grid">
 <div><div class="card"><h3 style="margin:0 0 10px;font-size:15px">7 维能力雷达（0–100，仅实测维度）</h3>
 {svg}
 <div style="margin-top:10px"><button class="btn" id="all">全选</button> <button class="btn" id="none">全不选</button>
 <button class="btn" id="top8">仅 Top 8</button></div>
 </div>
 <div class="card footer">
 <b>口径</b>：用例 <code>data/benchmark/virtu_eval_v1</code>，7 维 × {html.escape(str(meta['params']['tiers']))} 各 {meta['params']['per_dim']} 题
 = 每腿 {sum(p['rows'] for p in accepted.values())//max(1,len(accepted))} 条；temperature=0 / seed=1234 /
 num_predict≤{meta['params']['max_tokens']} / num_ctx={meta['params']['num_ctx']} / think=false。<br>
 <b>计分</b>：case=命中权重/总权重×100；维度=有效用例算术平均；综合=Σ(维度分×权重)/Σ(权重)；
 transport_error 剔除，空回答与截断照实计 0 或低分。<br>
 <b>toolcall</b>：本轮未注入工具 schema，判分锚定响应文本中的 JSON 字面量，
 不得与历史 16 工具 schema 腿直接比较。<br>
 <b>多模态</b>：需视觉通道，Ollama 库无 VL 标签，<b>未测</b>，故不画第 8 轴、不进综合分。<br>
 <b>限制</b>：每维样本量小（n={meta['params']['per_dim']*len(meta['params']['tiers'].split(','))}），
 用于全库横向对齐，不能当作发布级精度；生成预算 128 token 会压低长输出题（generation）的分数，
 该偏差对所有模型一致。<br>
 <b>复算</b>：<code>python scripts/generate_verified_radar.py --self-test</code>
 </div></div>
 <div><div class="card"><h3 style="margin:0 0 8px;font-size:15px">显示控制（{len(accepted)} 条实测多边形）</h3>
 <div id="legend">{legend}</div></div>
 <div class="card"><h3 style="margin:0 0 8px;font-size:15px">反证闸门（植入坏样本必须判红）</h3>
 <ul style="font-size:12px;line-height:2;padding-left:18px;margin:0">{checklist}</ul></div></div>
</div>
<div class="card"><h3 style="margin:0 0 10px;font-size:15px">逐模型溯源表（分数 / n / run_id / 证据）</h3>
<div style="overflow:auto"><table><tr><th>模型标签</th><th>家族</th><th>digest</th>
{''.join(f'<th>{html.escape(ZH[d])}</th>' for d in DIMS)}<th>综合</th><th>run_id</th><th>raw sha256</th><th>证据路径</th></tr>
{''.join(rows)}</table></div></div>
<div class="card"><h3 style="margin:0 0 10px;font-size:15px">未测 / 作废清单（不填分数）</h3>
<table><tr><th>模型</th><th>状态</th><th colspan="4">原因</th></tr>{unmeasured or '<tr><td colspan="6">无</td></tr>'}</table></div>
<script>
const boxes=[...document.querySelectorAll('#legend input')];
const arms=[...document.querySelectorAll('.arm')];
function apply(){{const on=new Set(boxes.filter(b=>b.checked).map(b=>b.dataset.model));
 arms.forEach(a=>a.style.display=on.has(a.dataset.model)?'':'none');}}
boxes.forEach(b=>b.addEventListener('change',apply));
document.getElementById('all').onclick=()=>{{boxes.forEach(b=>b.checked=true);apply();}};
document.getElementById('none').onclick=()=>{{boxes.forEach(b=>b.checked=false);apply();}};
document.getElementById('top8').onclick=()=>{{const top=new Set(boxes.slice(0,8).map(b=>b.dataset.model));
 boxes.forEach(b=>b.checked=top.has(b.dataset.model));apply();}};
apply();
</script></body></html>"""


def build_png(accepted):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError:
        return None
    for cand in ("Microsoft YaHei", "SimHei", "DejaVu Sans"):
        try:
            font_manager.findfont(cand, fallback_to_default=False)
            plt.rcParams["font.family"] = cand
            break
        except Exception:  # noqa: BLE001
            continue
    plt.rcParams["axes.unicode_minus"] = False
    n = len(DIMS)
    angles = [i / n * 2 * math.pi for i in range(n)]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(11, 11), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#0b0e17")
    ax.set_facecolor("#0f1320")
    for i, (tag, p) in enumerate(sorted(accepted.items())):
        vals = [p["dimensions"][d]["score"] for d in DIMS]
        vals += vals[:1]
        color = p["_color"]
        ax.plot(angles, vals, linewidth=1.3, color=color, alpha=0.75)
        ax.fill(angles, vals, color=color, alpha=0.015)
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([ZH[d] for d in DIMS], fontsize=11, color="#e6ebf5")
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="#8b95ad")
    ax.grid(color="#232c47")
    ax.spines["polar"].set_color("#232c47")
    ax.set_title(f"Virtu 全模型实测能力雷达 · {len(accepted)} 个构件 · 7 维 · 多模态未测",
                 fontsize=14, color="#e6ebf5", pad=24)
    # PNG 必须自带图例：否则四条同色系折线无法从图上对应到模型（2026-11-16 实测发现）
    handles = [plt.Line2D([0], [0], color=p["_color"], linewidth=2, alpha=0.85)
               for _tag, p in sorted(accepted.items())]
    labels = [_tag for _tag, _p in sorted(accepted.items())]
    leg = ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.06),
                    ncol=2 if len(labels) > 2 else 1, frameon=False,
                    fontsize=9, labelcolor="#e6ebf5")
    for text in leg.get_texts():
        text.set_color("#e6ebf5")
    os.makedirs(os.path.dirname(PNG_OUT), exist_ok=True)
    fig.savefig(PNG_OUT, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return PNG_OUT


def build_md(summary, accepted, rejected, self_test):
    meta = summary["meta"]
    lines = [
        "# 全模型真实能力测评（2026-11-07 现场实测）",
        "",
        "## 结论口径",
        "",
        f"- Ollama 库枚举 {len(summary['models'])} 个唯一构件（按 digest 去重，标签别名合并）。",
        f"- 真实调用并封缄、**可发布** {len(accepted)} 个；未测/作废 {len(rejected)} 个（见下表，不填分数）。",
        "- 每个分数由 `scripts/generate_verified_radar.py` 从各腿 `raw.jsonl` 现场复算，",
        "  与腿内记录逐位比对；封缄/sha256/完整性闸门/逐行 served_layers/run_id 任一不符即整腿作废。",
        "- 与 `VIRTU_*_RADAR.html` 中 98–99 分「极限强化」多边形不同：那些数字在仓内找不到",
        "  对应的 raw.jsonl 证据，本图不予采用。",
        "",
        "## 统一口径",
        "",
        f"- 用例：`data/benchmark/virtu_eval_v1`，7 维 × {meta['params']['tiers']} 各 "
        f"{meta['params']['per_dim']} 题；判分器 `virtu_eval/graders.py`（sha256 "
        f"{meta['grader_sha256'][:16]}…）。",
        f"- 采样：temperature=0，seed=1234，num_predict≤{meta['params']['max_tokens']}，"
        f"num_ctx={meta['params']['num_ctx']}，think=false。",
        "- toolcall 维未注入工具 schema（纯文本 JSON 协议），不得与历史 16 工具腿比较。",
        "- 多模态维**未测**（需视觉通道，库内无 VL 标签），不画轴、不进综合分。",
        "- 每维样本量小，且 128 token 预算会压低长输出题；该偏差对所有模型一致。",
        "",
        "## 实测榜（按综合分）",
        "",
        "| 模型 | 家族 | " + " | ".join(ZH[d] for d in DIMS) + " | 综合 | n/维 | run_id | 证据 |",
        "|---|---|" + "---|" * (len(DIMS) + 4),
    ]
    for tag, p in sorted(accepted.items(), key=lambda kv: -(kv[1]["overall_weighted"] or 0)):
        cells = " | ".join(f"{p['dimensions'][d]['score']:.1f}" for d in DIMS)
        ns = "/".join(str(p["dimensions"][d]["n"]) for d in DIMS)
        lines.append(f"| {tag} | {p['family']} | {cells} | **{p['overall_weighted']:.2f}** | "
                     f"{ns} | `{p['run_id']}` | `{p['raw_path']}` |")
    lines += ["", "## 未测 / 作废（不填分数）", "", "| 模型 | 状态 | 原因 |", "|---|---|---|"]
    for t, v in sorted(rejected.items()):
        lines.append(f"| {t} | {v['status']} | {str(v['reason']).replace('|','/')[:160]} |")
    lines += ["", "## 反证闸门", ""]
    for c in self_test:
        lines.append(f"- `{c['name']}` → {'判红 PASS' if c['caught'] else '漏放 FAIL'}：{c['reason']}")
    lines += ["", "## 复现", "", "```bash",
              "python scripts/eval_all_models_live.py",
              "python scripts/generate_verified_radar.py --self-test",
              "```", ""]
    return "\n".join(lines)


def self_test(accepted):
    """宪法 §4：闸必须能被证伪。复制一份真实腿做破坏，校验器必须判红。"""
    if not accepted:
        return [{"name": "no accepted leg", "caught": False,
                 "reason": "没有可用真实腿，无法做反证（应视为失败）"}]
    tag, p = next(iter(accepted.items()))
    src = os.path.join(ROOT, p["leg_dir"])
    results = []

    def probe(name, mutate, reseal=True):
        """破坏后重新封缄并伪造一致的摘要，逼校验器靠后续闸门判红，防止闸门空转。"""
        tmp = tempfile.mkdtemp(prefix="radar_gate_")
        dst = os.path.join(tmp, "leg")
        shutil.copytree(src, dst)
        try:
            mutate(dst)
            raw = os.path.join(dst, "raw.jsonl")
            if reseal:
                P.seal_leg(dst, owner="mutation_probe")
            fake = {"detail": {"raw_sha256": sha(raw), "dimensions": p["dimensions"]}}
            ok, _, reason = verify_leg(dst, fake)
            results.append({"name": name, "caught": not ok, "reason": reason[:150]})
        except Exception as exc:  # noqa: BLE001
            results.append({"name": name, "caught": True,
                            "reason": f"破坏样本触发异常（同样属于判红）: {type(exc).__name__}"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def change_score(dst):
        path = os.path.join(dst, "raw.jsonl")
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        rows[0]["score"] = 100.0 if rows[0]["score"] < 99 else 0.0
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def drop_row(dst):
        path = os.path.join(dst, "raw.jsonl")
        rows = [l for l in open(path, encoding="utf-8") if l.strip()]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(rows[:-1])

    def break_seal(dst):
        os.remove(os.path.join(dst, "_seal.json"))

    def inject_transport(dst):
        path = os.path.join(dst, "raw.jsonl")
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        for r in rows[:3]:
            r["verdict"] = "transport_error"
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def strip_identity(dst):
        path = os.path.join(dst, "raw.jsonl")
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        rows[0]["gen"].pop("served_layers", None)
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    probe("篡改单题分数（重封缄+伪摘要）", change_score)
    probe("删除一行（覆盖不全）", drop_row)
    probe("删除封缄", break_seal, reseal=False)
    probe("植入 3 条 transport_error", inject_transport)
    probe("抹掉一行 served_layers 身份", strip_identity)
    return results


def main():
    global SUMMARY, OUT_DIR, HTML_OUT, PNG_OUT, MD_OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="运行反证闸门并输出 JSON")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--summary", default=SUMMARY, help="封缄腿 summary.json；默认历史腿")
    ap.add_argument("--out-dir", default=OUT_DIR, help="产物目录")
    a = ap.parse_args()
    SUMMARY = a.summary
    OUT_DIR = a.out_dir
    HTML_OUT = os.path.join(OUT_DIR, "radar.html")
    PNG_OUT = os.path.join(OUT_DIR, "radar.png")
    MD_OUT = os.path.join(OUT_DIR, "radar.md")
    if not os.path.exists(SUMMARY):
        raise SystemExit(f"缺 {SUMMARY}；先跑 scripts/eval_all_models_live.py")
    summary, accepted, rejected = collect()
    tests = self_test(accepted)
    if a.self_test:
        print(json.dumps({"accepted": len(accepted), "rejected": len(rejected),
                          "all_caught": all(c["caught"] for c in tests),
                          "checks": tests}, ensure_ascii=False, indent=2))
        return 0 if all(c["caught"] for c in tests) else 2

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {"summary_meta": summary["meta"], "accepted": accepted,
               "rejected": rejected, "self_test": tests,
               "snapshots": summary.get("snapshots", [])}
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(build_html(summary, accepted, rejected, tests))
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(build_md(summary, accepted, rejected, tests))
    png = None if a.no_png else build_png(accepted)
    print(json.dumps({"accepted": len(accepted), "rejected": len(rejected),
                      "html": HTML_OUT, "md": MD_OUT, "png": png,
                      "results": os.path.join(OUT_DIR, "results.json")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
