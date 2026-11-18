# -*- coding: utf-8 -*-
"""WorkBuddy takeover: wait for an EXCLUSIVE Ollama window, then run v2/v3 A/B.

Rules enforced (FINAL_REPORT.md section 8 / AGENTS.md 8.1-8.2):
  * never start a measurement while another workspace Python measurement is alive;
  * never start while a /api/chat finished in the last 45 s;
  * require 3 consecutive idle checks (10 s apart) before starting;
  * archive any pre-existing raw rows as CONTAMINATED before the fresh run;
  * write a result markdown from comparison_report.json when done.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import psutil

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\Virtu模型"
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
OUT = os.path.join(ROOT, "runs", "eval_vericut96_v2_vs_v3")
LOG = os.path.join(OUT, "workbuddy_takeover_ab.log")
OLLAMA_LOG = os.path.join(ROOT, "runs", "ollama_11434.log")
RESULT_MD = os.path.join(ROOT, "reports", "V2_VS_V3_AB_RESULT_2026-11-15.md")
MAIN_RAW = os.path.join(OUT, "raw_baseline_holdout.jsonl")
EVAL = [
    PY, "-u", os.path.join(ROOT, "scripts", "eval_vericut_e_training.py"),
    "--baseline", "virtu-vericut96:v2",
    "--candidate", "virtu-vericut96:v3",
    "--out-dir", OUT,
]
SKIP = ("proxy_failopen_watchdog", "wait_exclusive_then_ab")


def note(msg: str) -> None:
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def other_measure_procs():
    me = os.getpid()
    found = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.pid == me:
                continue
            if not (proc.info["name"] or "").lower().startswith("python"):
                continue
            cmd = " ".join(proc.info["cmdline"] or [])
            if any(s in cmd for s in SKIP):
                continue
            if "Virtu" in cmd and ".py" in cmd:
                found.append((proc.pid, cmd[:160]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def recent_chat(max_age: float = 45.0) -> bool:
    try:
        with open(OLLAMA_LOG, "rb") as fh:
            end = fh.seek(0, 2)
            fh.seek(max(0, end - 24000))
            tail = fh.read().decode("utf-8", "ignore")
    except OSError:
        return False
    stamps = re.findall(
        r"\[GIN\] (\d{4})/(\d{2})/(\d{2}) - (\d{2}):(\d{2}):(\d{2})[^\n]*POST\s+\"/api/(?:chat|generate)\"",
        tail,
    )
    if not stamps:
        return False
    y, mo, d, h, mi, s = map(int, stamps[-1])
    return (datetime.now() - datetime(y, mo, d, h, mi, s)).total_seconds() < max_age


def wait_window(timeout_s: int = 3600, interval: int = 10, need: int = 3) -> bool:
    deadline = time.time() + timeout_s
    stable = 0
    while time.time() < deadline:
        others = other_measure_procs()
        chat = recent_chat()
        if not others and not chat:
            stable += 1
            note("idle check %d/%d (no workspace measurement, no recent chat)" % (stable, need))
        else:
            stable = 0
            note("busy: other_procs=%s recent_chat=%s" % ([p[0] for p in others], chat))
        if stable >= need:
            return True
        time.sleep(interval)
    return False


def archive_if_any() -> None:
    if os.path.isfile(MAIN_RAW) and os.path.getsize(MAIN_RAW) > 0:
        arc = MAIN_RAW + ".CONTAMINATED_" + datetime.now().strftime("%H%M")
        with open(MAIN_RAW, "rb") as src, open(arc, "wb") as dst:
            dst.write(src.read())
        open(MAIN_RAW, "wb").close()
        note("archived pre-existing rows -> " + os.path.basename(arc))


def write_result(rc: int, started: str, ended: str) -> None:
    rp = os.path.join(OUT, "comparison_report.json")
    lines = [
        "# virtu-vericut96 v2 vs v3 留出集 A/B（WorkBuddy 接手实测）", "",
        "- 独占窗口：%s ~ %s" % (started, ended),
        "- 口径：`scripts/eval_vericut_e_training.py --baseline virtu-vericut96:v2 --candidate virtu-vericut96:v3`，temperature=0 / seed=42 / num_ctx=4096 / 105 题留出集",
        "- 退出码：`%d`" % rc, "",
    ]
    if os.path.isfile(rp):
        r = json.loads(open(rp, encoding="utf-8").read())
        h = r["holdout"]
        b, c = h["baseline"], h["candidate"]
        lines += [
            "## 结论", "",
            "| 项 | v2 (baseline) | v3 (candidate) | delta |",
            "|:--|--:|--:|--:|",
            "| holdout 均分 | %.2f | %.2f | %+.2f |" % (b["overall_mean"], c["overall_mean"], h["delta_mean"]),
            "| pass@100 | %.2f%% | %.2f%% | %+.2f pp |" % (b["overall_pass_rate_pct"], c["overall_pass_rate_pct"], h["delta_pass_pct"]),
            "| 传输错误 | %d | %d | — |" % (b["transport_errors"], c["transport_errors"]),
            "",
            "- basis：`%s`；run_id：`%s`；identity_drift：`%s`" % (r["basis"], r["run_id"], r["identity_drift"]),
            "", "## 分维度", "",
            "| 维度 | n | v2 | v3 | delta |", "|:--|--:|--:|--:|--:|",
        ]
        for dim, v in sorted(h["by_dimension"].items()):
            lines.append("| %s | %s | %s | %s | %s |" % (
                dim, v["n"], v["baseline_mean"], v["candidate_mean"], v["delta_mean"]))
        s = r.get("general_sanity")
        if s:
            lines += ["", "## 通用不回归 sanity", "",
                      "- n=%s，v2 %.2f / v3 %.2f，delta %+.2f" % (
                          s["n"], s["baseline_mean"], s["candidate_mean"], s["delta_mean"])]
    else:
        lines += ["## 状态", "",
                  "`comparison_report.json` 未生成 ⇒ 测量未完成，**不得据此下结论**。"]
    lines += [
        "", "## 证据", "",
        "- `runs/eval_vericut96_v2_vs_v3/comparison_report.json`",
        "- `raw_baseline_holdout.jsonl` / `raw_candidate_holdout.jsonl`",
        "- `identity.json`（构件指纹 + drift）",
        "- `workbuddy_takeover_ab.log`（独占守候 + 每 10 题进度）",
        "", "> 诚实边界：并发窗口内产出的样本已另存 `*.CONTAMINATED_*`，不参与本结论。",
    ]
    with open(RESULT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    note("result markdown -> " + RESULT_MD)


def main() -> int:
    note("takeover watchdog started pid=%d" % os.getpid())
    if not wait_window():
        note("ABORT: no exclusive window within 60 min; A/B NOT started")
        return 2
    archive_if_any()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note("EXCLUSIVE WINDOW OPEN -> start A/B (105 x 2 + sanity)")
    with open(LOG, "a", encoding="utf-8") as lf:
        rc = subprocess.call(EVAL, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    ended = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note("A/B finished rc=%d" % rc)
    write_result(rc, started, ended)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
