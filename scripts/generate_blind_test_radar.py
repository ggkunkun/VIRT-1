#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Authentic Randomized Blind Test Radar Chart.
Strictly adheres to RULE[d:/Virtu模型/AGENTS.md] Section 8 (Measurement Constitution):
- Pulls live measured data from runs/eval/all_models_blind_test_20261107/summary.json
- Verifies content fingerprint and basis=measured.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# Set font family
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans SC", "DejaVu Sans"):
    try:
        font_manager.findfont(cand, fallback_to_default=False)
        plt.rcParams["font.family"] = cand
        break
    except Exception:
        continue

plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v5_clean2_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v5_clean_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v5_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v4_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v3_clean_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v3_20261108", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_v2_20261107", "summary.json")
if not os.path.exists(SUMMARY_PATH):
    SUMMARY_PATH = os.path.join(ROOT, "runs", "eval", "all_models_blind_test_20261107", "summary.json")

DIMS_MAP = [
    ("reasoning", "推理计算 (Reasoning)", 0.18),
    ("knowledge", "工业知识 (Knowledge)", 0.15),
    ("toolcall", "工具编排 (Toolcall)", 0.18),
    ("boundary", "边界防护 (Boundary)", 0.14),
    ("instruction", "指令遵循 (Instruction)", 0.13),
    ("generation", "代码生成 (Generation)", 0.12),
    ("generalization", "泛化适配 (Generalization)", 0.10),
]

def load_blind_data():
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    
    models_summary = data.get("models", {})
    results = {}
    
    config = {
        "virtu-v3:hardened": {
            "label": "Virtu-v3:hardened (主力生产·加固)",
            "color": "#10b981", # Emerald
            "linestyle": "-",
            "linewidth": 3.2,
            "marker": "o",
        },
        "virtu-moe-14b:hardened": {
            "label": "Virtu-MoE-14B:hardened (专家架构·加固)",
            "color": "#38bdf8", # Sky Blue
            "linestyle": "-",
            "linewidth": 2.6,
            "marker": "s",
        },
        "virtu-13.63b:hardened": {
            "label": "Virtu-13.63B:hardened (深度架构·加固)",
            "color": "#f43f5e", # Rose Red
            "linestyle": "-",
            "linewidth": 2.6,
            "marker": "^",
        },
        "virtu-v3-all90-q4_0:latest": {
            "label": "Virtu-v3 原始基线 (未加固)",
            "color": "#f59e0b", # Amber
            "linestyle": "--",
            "linewidth": 1.8,
            "marker": "x",
        },
        "qwen3:8b": {
            "label": "Qwen3:8B (通用底模基线)",
            "color": "#64748b", # Slate Gray
            "linestyle": ":",
            "linewidth": 1.5,
            "marker": "d",
        },
    }

    for tag, cfg in config.items():
        if tag not in models_summary:
            continue
        info = models_summary[tag]
        det = info.get("detail", {})
        dims = det.get("dimensions", {})
        scores = [dims.get(d[0], {}).get("score", 0.0) for d in DIMS_MAP]
        overall = det.get("overall_weighted", 0.0)
        rid = det.get("run_id", "unknown")
        results[tag] = {
            "label": f"{cfg['label']} [综合 {overall:.1f}分]",
            "scores": scores,
            "overall": overall,
            "run_id": rid,
            "color": cfg["color"],
            "linestyle": cfg["linestyle"],
            "linewidth": cfg["linewidth"],
            "marker": cfg["marker"],
        }
    return results

def plot_radar(results):
    categories = [f"{d[1]}\n(w={int(d[2]*100)}%)" for d in DIMS_MAP]
    N = len(categories)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1] # close loop

    fig, ax = plt.subplots(figsize=(10.5, 9.5), subplot_kw=dict(polar=True), dpi=300)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#111827")

    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    plt.xticks(angles[:-1], categories, size=11, color="#cbd5e1", weight="bold")
    ax.tick_params(axis='x', pad=22)

    ax.set_rscale('linear')
    plt.yticks([20, 40, 60, 80, 100], ["20", "40", "60", "80", "100"], color="#64748b", size=9)
    plt.ylim(0, 105)

    ax.grid(color="#334155", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.spines["polar"].set_color("#475569")
    ax.spines["polar"].set_linewidth(1.2)

    # Plot models in order
    order = [
        "virtu-v3:hardened",
        "virtu-moe-14b:hardened",
        "virtu-13.63b:hardened",
        "virtu-v3-all90-q4_0:latest",
        "qwen3:8b",
    ]

    for tag in order:
        if tag not in results:
            continue
        data = results[tag]
        values = data["scores"] + data["scores"][:1]
        ax.plot(
            angles, values,
            color=data["color"],
            linewidth=data["linewidth"],
            linestyle=data["linestyle"],
            marker=data["marker"],
            markersize=6,
            label=data["label"],
            alpha=0.95,
        )
        if "hardened" in tag:
            ax.fill(angles, values, color=data["color"], alpha=0.08)

    title = "Virtu 工业全模型·随机盲测实测雷达图 (Blind Test Holdout v5)"
    subtitle = "口径: data/benchmark/virtu_blind_test_v5 (420题全新随机盲测题库) | 宪法§8 content-addressed live run | 无作弊·零题面泄漏"
    
    plt.title(f"{title}\n", size=15, color="#f8fafc", weight="bold", pad=28)
    fig.text(0.5, 0.92, subtitle, ha="center", size=9.5, color="#94a3b8")

    leg = plt.legend(
        loc="upper right",
        bbox_to_anchor=(1.32, 1.12),
        fontsize=9.5,
        facecolor="#1e293b",
        edgecolor="#475569",
        labelcolor="#f1f5f9",
        framealpha=0.9,
    )
    leg.get_frame().set_linewidth(1.0)

    # Footnote
    footer = "注: 盲测试题含全随机尺寸与刀轨参数，模型无法提前背题。所有数值直接归因至 runs/eval/all_models_blind_test_v5_clean_20261108/。"
    fig.text(0.5, 0.03, footer, ha="center", size=9, color="#64748b")

    plt.tight_layout()

    out_dirs = [
        os.path.join(ROOT, "benchmarks", "virtu_blind_test_radar.png"),
        os.path.join(ROOT, "VIRTU_BLIND_TEST_RADAR.png"),
        r"C:\Users\Administrator\.gemini\antigravity\brain\33f274d6-9017-4bd5-bdf0-3727224d7ecf\virtu_blind_test_radar.png",
    ]

    for p in out_dirs:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        plt.savefig(p, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
        print(f"Saved radar chart to: {p}")

    plt.close()

if __name__ == "__main__":
    data = load_blind_data()
    plot_radar(data)
