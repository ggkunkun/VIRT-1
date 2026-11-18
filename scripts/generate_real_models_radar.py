"""Generate provenance-attributable radar charts (AGENTS.md §8 测量宪法).

口径见下方要点；所有能力分数均动态读取，源码内不保留任何硬编码分数。
Strictly follows RULE[d:\\Virtu模型\\AGENTS.md] Section 8 (Measurement Constitution):
1. 能力分数一律从"带 16 位 hex run_id 的 results.json"动态读取；读不到 / run_id
   非 16 位 hex / 记录不匹配 / 解析失败 => 输出「未测」，绝不保留硬编码分数。
2. 架构规格 7 维是源码断言值，明确标 basis=asserted /「未测（源码常量，非实测）」，
   不是 benchmark 能力实测分数。
3. 遵循 AGENTS.md §8 测量宪法：禁止把源码字面量当 measured，禁止无归因数值。
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Configure high-quality Chinese font
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans SC", "DejaVu Sans"):
    try:
        font_manager.findfont(cand, fallback_to_default=False)
        plt.rcParams["font.family"] = cand
        break
    except Exception:
        continue

plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------------------
# 1. 真实 8 维度工业能力测评数据 (Authentic Measured Capability Data)
# ---------------------------------------------------------------------------
CAP_DIMS = [
    ("toolcall", "工具编排", 0.18),
    ("reasoning", "推理逻辑", 0.17),
    ("knowledge", "知识覆盖", 0.15),
    ("instruction", "指令遵循", 0.14),
    ("boundary", "边界处理", 0.12),
    ("generation", "内容生成", 0.10),
    ("generalization", "泛化适配", 0.08),
    ("multimodal", "多模态理解", 0.06),
]

# 能力分数：一律从"带 run_id 的 results.json"动态读取，读不到就输出「未测」。
# 旧版把 8 维分数硬编码在源码里，手写 "basis":"measured"，还把标签名
# （"virtu-v2-all90"）和 12 位前缀（"3546c40f3ce8"）当 run_id —— 按测量宪法
# 这些都是不可归因的数值，必须全部删除。
ROOT = Path(__file__).resolve().parent.parent
RUN_ID_RE = re.compile(r"^[0-9a-f]{16}$")
UNMEASURED = "未测"

# 展示配置只保留"去哪找证据 + 期望 run_id + 绘图样式"，不含任何分数。
CAP_SOURCES = {
    "Qwen3-8B 基座": {
        "source": "benchmarks/radar_20261106/results.json",
        "expected_run_id": "46864ace19b19c3a",
        "color": "#8b9bb4", "linestyle": "--", "linewidth": 2.2, "marker": "o",
    },
    "Virtu-8.2B Comprehensive": {
        "source": "benchmarks/radar_20261106/results.json",
        "expected_run_id": "646f990b9c098ddd",
        "color": "#38bdf8", "linestyle": "-", "linewidth": 2.2, "marker": "s",
    },
    "Virtu-v2-all90 (中间优化版)": {
        "source": "benchmarks/virtu_v3/results.json",
        "expected_run_id": "virtu-v2-all90",      # 标签名 -> 格式校验直接判「未测」
        "color": "#34d399", "linestyle": "-", "linewidth": 2.2, "marker": "^",
    },
    "Virtu-v3-all90 (8.2B 巅峰版)": {
        "source": "benchmarks/virtu_v3/results.json",
        "expected_run_id": "virtu-v3-all90",
        "color": "#fbbf24", "linestyle": "-", "linewidth": 2.6, "marker": "D",
    },
    "Virtu-13B / 13.63B DPO": {
        "source": "models/virtu-13b/COMPREHENSIVE_EVAL_REPORT.json",
        "expected_run_id": "3546c40f3ce8",        # 12 位前缀 -> 判「未测」
        "color": "#f87171", "linestyle": "-", "linewidth": 2.8, "marker": "P",
    },
}


def _valid_run_id(value) -> bool:
    return isinstance(value, str) and bool(RUN_ID_RE.fullmatch(value))


def _load_result_doc(rel_path):
    """读取 results.json；不存在 / 解析失败一律抛异常（不吞、不静默降级）。"""
    p = Path(rel_path)
    if not p.is_absolute():
        p = ROOT / p
    return json.loads(p.read_text(encoding="utf-8"))


def _iter_result_records(doc):
    """从常见 results.json 结构里找出带身份的模型记录。"""
    if isinstance(doc, list):
        for rec in doc:
            if isinstance(rec, dict):
                yield rec
        return
    if not isinstance(doc, dict):
        return
    for key in ("accepted", "arms", "results", "models"):
        block = doc.get(key)
        if isinstance(block, dict):
            for rec in block.values():
                if isinstance(rec, dict):
                    yield rec
        elif isinstance(block, list):
            for rec in block:
                if isinstance(rec, dict):
                    yield rec
    for rec in doc.values():
        if isinstance(rec, dict) and ("run_id" in rec or "dimensions" in rec):
            yield rec


def _scores_from_record(rec):
    """把记录里的 dimensions.*.score 抽成 8 维；任一维缺失即 None（未测）。"""
    dims = rec.get("dimensions") or {}
    out = {}
    for dim, _, _ in CAP_DIMS:
        node = dims.get(dim) if isinstance(dims, dict) else None
        val = node.get("score") if isinstance(node, dict) else node
        out[dim] = (float(val) if isinstance(val, (int, float))
                    and not isinstance(val, bool) else None)
    return out


def load_cap_models():
    """动态构建能力数据：只有 results.json 里确实存在 16 位 hex run_id 记录才采信分数。

    读不到 / run_id 非法 / 记录不匹配 / 解析失败 => basis=「未测」、scores 全 None，
    绝不回落到任何硬编码数值。
    """
    models = {}
    for name, cfg in CAP_SOURCES.items():
        meta = {k: cfg[k] for k in ("color", "linestyle", "linewidth", "marker")}
        record = {
            **meta, "scores": {d: None for d, _, _ in CAP_DIMS},
            "basis": UNMEASURED, "run_id": cfg.get("expected_run_id"), "n": 0,
            "provenance": cfg["source"], "note": "",
        }
        expected = cfg.get("expected_run_id")
        # 1) run_id 必须是 16 位 hex 内容指纹，标签名/短前缀一律不读、判未测。
        if not _valid_run_id(expected):
            record["note"] = "run_id 非 16 位 hex 内容指纹，禁止当作实测"
            models[name] = record
            continue
        # 2) 读证据文件；解析失败/不存在 => 未测（显式标注原因，不当 success）。
        try:
            doc = _load_result_doc(cfg["source"])
        except (OSError, ValueError) as exc:
            record["note"] = f"证据读取失败：{type(exc).__name__}:{exc}，判「未测」"
            models[name] = record
            continue
        # 3) results.json 里必须存在 run_id 与该指纹一致的记录。
        match = next((r for r in _iter_result_records(doc)
                      if _valid_run_id(r.get("run_id")) and r["run_id"] == expected), None)
        if match is None:
            record["note"] = "results.json 中无该 run_id 的记录，判「未测」"
            models[name] = record
            continue
        scores = _scores_from_record(match)
        if any(v is None for v in scores.values()):
            record["scores"] = scores
            record["note"] = "部分维度无分数，判「未测」"
            models[name] = record
            continue
        # 4) 8 维齐全且身份可归因，才标 measured。
        n, dims = 0, match.get("dimensions") or {}
        for d, _, _ in CAP_DIMS:
            node = dims.get(d) if isinstance(dims, dict) else None
            if isinstance(node, dict) and isinstance(node.get("n"), int):
                n += node["n"]
        record.update({"scores": scores, "basis": "measured", "run_id": expected,
                       "n": n, "note": "来自带 16 位 hex run_id 的 results.json"})
        models[name] = record
    return models


REAL_CAP_MODELS = load_cap_models()

# ---------------------------------------------------------------------------
# 2. 真实模型实体规格雷达数据 (Physical Architecture & Maturity Radar)
# ---------------------------------------------------------------------------
ARCH_DIMS = [
    ("params", "物理参数量\n(log10 归一化)"),
    ("layers", "网络深度\n(层数/50)"),
    ("context", "上下文窗口\n(Token/40K)"),
    ("bitwidth", "计算精度\n(位宽比例)"),
    ("pipeline", "工业全模态\n(CAD/CAM闭环)"),
    ("serving", "服务就绪度\n(Ollama 注册)"),
    ("provenance", "证据链封缄\n(溯源闭环)"),
]

REAL_ARCH_MODELS = {
    "Virtu-13.63B Asym (最新旗舰)": {
        "scores": [100.0, 72.0, 100.0, 30.3, 90.0, 100.0, 100.0],
        "color": "#f87171",
        "marker": "P",
        "specs": "13.63B, 36L, 40960ctx, Q3_K_M (6.32GB), 闭环 90%, 已注册, 2026-11-07 封缄",
    },
    "Virtu-MoE-14B BF16 (全精度未量化)": {
        "scores": [100.0, 72.0, 100.0, 100.0, 85.0, 100.0, 100.0],
        "color": "#c084fc",
        "marker": "s",
        "specs": "13.63B, 36L, 40960ctx, BF16 (27GB), 闭环 85%, 已注册, 已封缄",
    },
    "Virtu-v3-all90 (8.2B 生产版)": {
        "scores": [76.6, 72.0, 100.0, 28.1, 95.0, 100.0, 100.0],
        "color": "#fbbf24",
        "marker": "D",
        "specs": "8.19B, 36L, 40960ctx, Q4_0 (4.61GB), 闭环 95%, 已注册, 已封缄",
    },
    "Virtu-8.2B Comprehensive": {
        "scores": [76.6, 72.0, 100.0, 28.1, 80.0, 100.0, 100.0],
        "color": "#38bdf8",
        "marker": "o",
        "specs": "8.19B, 36L, 40960ctx, Q4_0 (4.61GB), 闭环 80%, 已注册, 已封缄",
    },
    "Virtu-longctx (3.1B 端侧长文本)": {
        "scores": [31.8, 72.0, 80.0, 30.3, 60.0, 100.0, 70.0],
        "color": "#f472b6",
        "marker": "v",
        "specs": "3.09B, 36L, 32768ctx, Q4_K_M (1.9GB), 闭环 60%, 已注册, 基础 receipt",
    },
    "Virtu-extreme-256k (1.5B 极速核)": {
        "scores": [15.0, 56.0, 80.0, 30.3, 50.0, 100.0, 70.0],
        "color": "#34d399",
        "marker": "^",
        "specs": "1.54B, 28L, 32768ctx, Q4_K_M (986MB), 闭环 50%, 已注册, 基础 receipt",
    },
    "Qwen3-8B (官方标准基座)": {
        "scores": [76.6, 72.0, 100.0, 30.3, 65.0, 100.0, 100.0],
        "color": "#8b9bb4",
        "marker": "x",
        "specs": "8.19B, 36L, 40960ctx, Q4_K_M (5.2GB), 闭环 65%, 官方基座, 官方指纹",
    },
}

# 架构规格 7 维是源码断言值（物理事实描述），不是 benchmark 能力实测分数：
# 明确标 basis=asserted /「未测（源码常量，非实测）」，禁止被当成 measured 引用。
for _m in REAL_ARCH_MODELS.values():
    _m["basis"] = "asserted"
    _m["basis_label"] = "未测（源码常量，非实测）"


def draw_radar_polar(ax, labels, models_dict, title, subtitle="", is_dark=True):
    num_vars = len(labels)
    angles = [n / float(num_vars) * 2 * math.pi for n in range(num_vars)]
    angles += angles[:1]

    bg_color = "#0b0f19" if is_dark else "#ffffff"
    grid_color = "#20293a" if is_dark else "#e2e8f0"
    text_color = "#f1f5f9" if is_dark else "#0f172a"
    sub_color = "#94a3b8" if is_dark else "#64748b"

    ax.set_facecolor(bg_color)
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    # X-ticks (dimension labels)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, color=text_color, fontweight="bold")

    # Y-ticks (levels)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=9, color=sub_color)
    ax.grid(color=grid_color, linestyle="-", linewidth=1.2, alpha=0.9)

    # Concentric rings
    for y in [20, 40, 60, 80, 100]:
        ax.plot(angles, [y] * len(angles), color=grid_color, linewidth=0.9, linestyle=":")

    # Highlight 80 & 90 standard lines
    ax.plot(angles, [80] * len(angles), color="#38bdf8", linewidth=1.0, linestyle="--", alpha=0.35)
    ax.plot(angles, [90] * len(angles), color="#34d399", linewidth=1.0, linestyle="--", alpha=0.35)

    # Draw model polygons
    for name, mdata in models_dict.items():
        if isinstance(mdata.get("scores"), dict):
            vals = [mdata["scores"].get(k) for k, _, _ in CAP_DIMS]
        else:
            vals = list(mdata.get("scores") or [])
        # 未测（任一维为 None）不画多边形：用 0 冒充分数正是测量宪法禁止的。
        if not vals or any(v is None for v in vals):
            continue
        vals = [float(v) for v in vals]
        vals += vals[:1]

        c = mdata.get("color", "#38bdf8")
        ls = mdata.get("linestyle", "-")
        lw = mdata.get("linewidth", 2.2)
        marker = mdata.get("marker", "o")

        ax.plot(angles, vals, color=c, linestyle=ls, linewidth=lw, marker=marker,
                markersize=6, label=name, zorder=3)
        ax.fill(angles, vals, color=c, alpha=0.12, zorder=2)

    ax.set_title(title, fontsize=15, color=text_color, pad=32, fontweight="bold")
    ax.legend(loc="upper right", bbox_to_anchor=(1.36, 1.16), fontsize=9,
              facecolor="#131b2e" if is_dark else "#f8fafc",
              edgecolor=grid_color, labelcolor=text_color)


def generate_capability_radar_chart(out_path):
    fig, ax = plt.subplots(figsize=(10.5, 9.0), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#0b0f19")
    labels = [f"{zh}\n(权重 {w:.2f})" for _, zh, w in CAP_DIMS]
    draw_radar_polar(ax, labels, REAL_CAP_MODELS, "Virtu 工业模型 8 维度能力雷达图\n(仅动态读取带 run_id 的实测 · 未测一律标注)", is_dark=True)
    plt.tight_layout()
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved Capability Radar: {out_path}")


def generate_architecture_radar_chart(out_path):
    fig, ax = plt.subplots(figsize=(10.5, 9.0), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#0b0f19")
    labels = [name for _, name in ARCH_DIMS]
    draw_radar_polar(ax, labels, REAL_ARCH_MODELS, "Virtu 物理模型规格与工程成熟度雷达 (7 维 · 源码断言值，非实测)", is_dark=True)
    plt.tight_layout()
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved Architecture Radar: {out_path}")


def generate_unified_panorama_radar(out_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, 10.2), subplot_kw={"polar": True})
    fig.patch.set_facecolor("#0b0f19")

    cap_labels = [f"{zh}\n(权重 {w:.2f})" for _, zh, w in CAP_DIMS]
    draw_radar_polar(ax1, cap_labels, REAL_CAP_MODELS, "【图 A】核心工业能力雷达 (8 维度 · 未测标注未测)", is_dark=True)

    arch_labels = [name for _, name in ARCH_DIMS]
    draw_radar_polar(ax2, arch_labels, REAL_ARCH_MODELS, "【图 B】物理模型规格与工程成熟度雷达 (7 维度 · 断言值)", is_dark=True)

    fig.suptitle("Virtu 文件夹全模型雷达全景图谱 (严守测量宪法 · 未测标注未测)",
                 fontsize=19, color="#f1f5f9", fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved Unified Panorama Radar: {out_path}")


def generate_interactive_html(html_path):
    center = 360
    radius = 230

    def _fmt(v):
        return UNMEASURED if v is None else f"{v:.1f}"

    def _weighted(mdata):
        vals = [mdata["scores"].get(k) for k, _, _ in CAP_DIMS]
        if any(v is None for v in vals):
            return UNMEASURED
        return f"{sum(v * w for (_, _, w), v in zip(CAP_DIMS, vals)):.2f}"

    def get_poly_points(scores):
        n = len(scores)
        pts = []
        for i, val in enumerate(scores):
            angle = i * (2 * math.pi / n) - (math.pi / 2)
            r = (val / 100.0) * radius
            x = center + r * math.cos(angle)
            y = center + r * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    cap_polys = []
    for name, mdata in REAL_CAP_MODELS.items():
        vals = [mdata["scores"].get(k) for k, _, _ in CAP_DIMS]
        if any(v is None for v in vals):
            continue  # 未测：不画多边形，禁止用 0 冒充
        poly = get_poly_points([float(v) for v in vals])
        cap_polys.append((name, poly, mdata["color"], mdata.get("linestyle", "-")))

    arch_polys = []
    for name, mdata in REAL_ARCH_MODELS.items():
        poly = get_poly_points(mdata["scores"])
        arch_polys.append((name, poly, mdata["color"]))

    # 溯源段落按动态数据生成，不再写死任何分数 / run_id / 样本量。
    prov_rows = "".join(
        f"<div>· <b>{name}</b>：证据 <code>{m['provenance']}</code>；"
        f"run_id <code>{m['run_id'] or '—'}</code>；口径 <b>{m['basis']}</b>；n={m['n']}。"
        f"{m['note'] or ('8 维分数均来自带 16 位 hex run_id 的 results.json' if m['basis'] == 'measured' else '无可归因实测证据，输出「未测」')}</div>"
        for name, m in REAL_CAP_MODELS.items())

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Virtu 文件夹模型雷达图谱 (Attributable Radar)</title>
<style>
  body {{
    background: #0b0f19;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
    margin: 0;
    padding: 28px;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 18px;
    margin-bottom: 24px;
  }}
  h1 {{
    font-size: 26px;
    margin: 0 0 8px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
  }}
  .sub {{
    color: #94a3b8;
    font-size: 13.5px;
    line-height: 1.6;
  }}
  .badge-constitution {{
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid #38bdf8;
    color: #38bdf8;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
  }}
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
  }}
  @media (max-width: 1250px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}
  .card {{
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }}
  .card-title {{
    font-size: 18px;
    font-weight: 600;
    color: #f9fafb;
  }}
  .badge {{
    font-size: 11.5px;
    padding: 4px 10px;
    border-radius: 6px;
    background: #1f2937;
    border: 1px solid #374151;
    color: #9ca3af;
  }}
  .radar-box {{
    text-align: center;
    position: relative;
    padding: 10px 0;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    margin-top: 18px;
  }}
  th, td {{
    border: 1px solid #1f2937;
    padding: 9px 10px;
    text-align: center;
  }}
  th {{
    background: #192237;
    color: #cbd5e1;
    font-weight: 600;
  }}
  td.l {{
    text-align: left;
    font-weight: 500;
  }}
  tr:nth-child(even) td {{
    background: #0f1626;
  }}
  .tag {{
    display: inline-block;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 600;
  }}
  .tag-pass {{ background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid #34d399; }}
  .tag-warn {{ background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid #fbbf24; }}
  .tag-fail {{ background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid #f87171; }}
  .provenance-card {{
    margin-top: 28px;
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 16px;
    padding: 22px;
  }}
  .provenance-title {{
    font-size: 16px;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 12px;
  }}
  .provenance-list {{
    font-size: 13px;
    line-height: 1.8;
    color: #94a3b8;
  }}
  .provenance-list b {{
    color: #f1f5f9;
  }}
  .provenance-list code {{
    background: #1f2937;
    padding: 2px 6px;
    border-radius: 4px;
    color: #e2e8f0;
    font-family: Consolas, monospace;
    font-size: 12px;
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>📊 Virtu 文件夹全模型雷达图谱 (Attributable Radar)</h1>
    <div class="sub">
      口径遵照 <code>RULE[d:\\Virtu模型\\AGENTS.md]</code> 第 8 条测量宪法 · 能力分数仅从带 16 位 hex run_id 的 results.json 动态读取 · 读不到一律输出「未测」· 架构规格为源码断言值
    </div>
  </div>
  <div class="badge-constitution">🛡️ 归因校验 · 未测标注「未测」· 断言值标 asserted</div>
</div>

<div class="grid">
  <!-- 核心工业能力实测雷达 -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">🎯 核心工业能力雷达 (8 维度)</span>
      <span class="badge">未测标注未测 · 实测需 16 位 hex run_id</span>
    </div>
    
    <div class="radar-box">
      <svg viewBox="0 0 720 720" style="max-width: 100%; height: auto;">
        <!-- Background Grid Rings -->
        <circle cx="360" cy="360" r="230" fill="#0f1626" stroke="#1f2937" stroke-width="1.2"/>
        <circle cx="360" cy="360" r="184" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="138" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="92" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="46" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        
        <!-- Standard Reference Lines (80分/90分) -->
        <circle cx="360" cy="360" r="207" fill="none" stroke="#34d399" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.4"/>
        <text x="365" y="157" fill="#34d399" font-size="10" opacity="0.7">90分基准</text>
        <circle cx="360" cy="360" r="184" fill="none" stroke="#38bdf8" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.4"/>
        <text x="365" y="180" fill="#38bdf8" font-size="10" opacity="0.7">80分基准</text>

        <!-- Dimension Axes -->
        {"".join([f'''<line x1="360" y1="360" x2="{360 + 230 * math.cos(i*2*math.pi/8 - math.pi/2):.1f}" y2="{360 + 230 * math.sin(i*2*math.pi/8 - math.pi/2):.1f}" stroke="#223048" stroke-width="1.2"/>
        <text x="{360 + 260 * math.cos(i*2*math.pi/8 - math.pi/2):.1f}" y="{360 + 260 * math.sin(i*2*math.pi/8 - math.pi/2):.1f}" fill="#cbd5e1" font-size="12" font-weight="600" text-anchor="middle" dominant-baseline="middle">{zh} ({w:.2f})</text>''' for i, (_, zh, w) in enumerate(CAP_DIMS)])}

        <!-- Polygons -->
        {"".join([f'''<polygon points="{poly}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2.4" stroke-dasharray="{"6,3" if ls == "--" else "none"}"/>''' for name, poly, color, ls in cap_polys])}
      </svg>
    </div>

    <table>
      <thead>
        <tr>
          <th>模型名称</th>
          <th>工具编排</th>
          <th>推理逻辑</th>
          <th>知识覆盖</th>
          <th>指令遵循</th>
          <th>边界处理</th>
          <th>内容生成</th>
          <th>泛化适配</th>
          <th>多模态</th>
          <th>加权实得分</th>
        </tr>
      </thead>
      <tbody>
        {"".join([f'''<tr>
          <td class="l"><span style="display:inline-block;width:10px;height:10px;background:{mdata['color']};border-radius:2px;margin-right:6px;"></span><b>{name}</b></td>
          <td>{_fmt(mdata['scores'].get('toolcall'))}</td>
          <td>{_fmt(mdata['scores'].get('reasoning'))}</td>
          <td>{_fmt(mdata['scores'].get('knowledge'))}</td>
          <td>{_fmt(mdata['scores'].get('instruction'))}</td>
          <td>{_fmt(mdata['scores'].get('boundary'))}</td>
          <td>{_fmt(mdata['scores'].get('generation'))}</td>
          <td>{_fmt(mdata['scores'].get('generalization'))}</td>
          <td>{_fmt(mdata['scores'].get('multimodal'))}</td>
          <td><b style="color:{mdata['color']};">{_weighted(mdata)}</b></td>
        </tr>''' for name, mdata in REAL_CAP_MODELS.items()])}
      </tbody>
    </table>
  </div>

  <!-- 模型架构规格与工程成熟度雷达 -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">📐 物理模型规格与工程成熟度雷达 (7 维 · 断言值)</span>
      <span class="badge">源码断言值（非实测）</span>
    </div>

    <div class="radar-box">
      <svg viewBox="0 0 720 720" style="max-width: 100%; height: auto;">
        <!-- Background Grid Rings -->
        <circle cx="360" cy="360" r="230" fill="#0f1626" stroke="#1f2937" stroke-width="1.2"/>
        <circle cx="360" cy="360" r="184" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="138" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="92" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>
        <circle cx="360" cy="360" r="46" fill="none" stroke="#1f2937" stroke-width="1" stroke-dasharray="3,3"/>

        <!-- Dimension Axes -->
        {"".join([f'''<line x1="360" y1="360" x2="{360 + 230 * math.cos(i*2*math.pi/7 - math.pi/2):.1f}" y2="{360 + 230 * math.sin(i*2*math.pi/7 - math.pi/2):.1f}" stroke="#223048" stroke-width="1.2"/>
        <text x="{360 + 260 * math.cos(i*2*math.pi/7 - math.pi/2):.1f}" y="{360 + 260 * math.sin(i*2*math.pi/7 - math.pi/2):.1f}" fill="#cbd5e1" font-size="12" font-weight="600" text-anchor="middle" dominant-baseline="middle">{name.replace(chr(10), " ")}</text>''' for i, (_, name) in enumerate(ARCH_DIMS)])}

        <!-- Polygons -->
        {"".join([f'''<polygon points="{poly}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2.4"/>''' for name, poly, color in arch_polys])}
      </svg>
    </div>

    <table>
      <thead>
        <tr>
          <th>模型名称</th>
          <th>物理参数量</th>
          <th>网络层数</th>
          <th>上下文窗口</th>
          <th>计算位宽</th>
          <th>工业全模态</th>
          <th>服务注册</th>
          <th>封缄状态</th>
        </tr>
      </thead>
      <tbody>
        {"".join([f'''<tr>
          <td class="l"><span style="display:inline-block;width:10px;height:10px;background:{mdata['color']};border-radius:2px;margin-right:6px;"></span><b>{name}</b></td>
          <td>{mdata['specs'].split(',')[0]}</td>
          <td>{mdata['specs'].split(',')[1]}</td>
          <td>{mdata['specs'].split(',')[2]}</td>
          <td>{mdata['specs'].split(',')[3]}</td>
          <td>{mdata['specs'].split(',')[4]}</td>
          <td><span class="tag tag-pass">已注册</span></td>
          <td><span class="tag tag-pass">已封缄</span></td>
        </tr>''' for name, mdata in REAL_ARCH_MODELS.items()])}
      </tbody>
    </table>
  </div>
</div>

<div class="provenance-card">
  <div class="provenance-title">📜 测量宪法溯源归因报告 (Provenance & Integrity Audit)</div>
  <div class="provenance-list">
    {prov_rows}
    <div>· 架构规格 7 维为 <b>asserted（源码断言值，未测/非实测）</b>，不是 benchmark 实测分数，不得当作能力结论引用。</div>
  </div>
</div>

</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Saved Interactive HTML: {html_path}")


def main():
    bench_dir = r"D:\Virtu模型\benchmarks"
    # Current active artifact dir
    artifact_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\33f274d6-9017-4bd5-bdf0-3727224d7ecf"
    os.makedirs(artifact_dir, exist_ok=True)

    cap_png = os.path.join(bench_dir, "virtu_real_capability_radar.png")
    arch_png = os.path.join(bench_dir, "virtu_real_architecture_radar.png")
    unified_png = os.path.join(bench_dir, "virtu_real_models_radar_unified.png")
    root_png = r"D:\Virtu模型\VIRTU_REAL_MODELS_RADAR.png"
    html_out = r"D:\Virtu模型\VIRTU_REAL_MODELS_RADAR.html"

    # Generate images
    generate_capability_radar_chart(cap_png)
    generate_architecture_radar_chart(arch_png)
    generate_unified_panorama_radar(unified_png)
    generate_unified_panorama_radar(root_png)
    generate_interactive_html(html_out)

    # Copy to artifact directory for markdown embedding
    shutil.copy(cap_png, os.path.join(artifact_dir, "virtu_real_capability_radar.png"))
    shutil.copy(arch_png, os.path.join(artifact_dir, "virtu_real_architecture_radar.png"))
    shutil.copy(unified_png, os.path.join(artifact_dir, "virtu_real_models_radar_unified.png"))
    shutil.copy(html_out, os.path.join(artifact_dir, "VIRTU_REAL_MODELS_RADAR.html"))

    print("\n[DONE] 雷达图已生成：能力分数按 16 位 hex run_id 动态读取，未测一律标注「未测」，架构规格为断言值。")


if __name__ == "__main__":
    main()
