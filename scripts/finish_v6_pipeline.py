#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v6 流水线收尾驱动（2026-11-16）。

背景：v6 原编排在 STEP 2 训练的第 11 次存断点被安全删除钩子拦截
（[safe-delete] threshold=50，累计删除 50 个文件），训练已在 step 100/117
落盘断点。本驱动不重跑训练，只在训练 receipt=COMPLETED 后执行：
  3. 合并(numpy delta) + GGUF(q4_0) + ollama create + 部署身份闸
  4. 独占验收 3 轮（verify(all) -> JSON）
  5. 汇总报告 + 门禁判定（连测最差值）
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_full_repair_v6 as m  # noqa: E402  复用常量与工具函数


def step3() -> int:
    m.log("=== STEP 3 合并/量化/部署 ===")
    if not m.run([str(m.PY), "scripts/merge_numpy.py",
                  "--base", str(m.BASE), "--lora", str(m.OUT_LORA),
                  "--mode", "delta", "--out", str(m.DEPLOY_DIR / "merged_hf")],
                 "merge_v6.log", 3600):
        m.log("[FATAL] merge failed")
        return 5
    if not m.run([str(m.PY), "scripts/hf_to_gguf_numpy.py",
                  "--model", str(m.DEPLOY_DIR / "merged_hf"), "--out", str(m.GGUF), "--dtype", "q4_0"],
                 "gguf_v6.log", 3600):
        m.log("[FATAL] gguf failed")
        return 6
    modelfile = m.DEPLOY_DIR / "Modelfile"
    modelfile.write_text(m.build_modelfile(m.GGUF), encoding="utf-8")
    if not m.run(["ollama", "create", m.TAG, "-f", str(modelfile)], "ollama_create_v6.log", 1800):
        m.log("[FATAL] ollama create failed")
        return 7
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=15) as resp:
            tags = {x["name"]: x["digest"] for x in json.loads(resp.read()).get("models", [])}
        if m.TAG not in tags:
            m.log(f"[FATAL] tag {m.TAG} absent from /api/tags after create")
            return 7
        m.log(f"deployed {m.TAG} digest={tags[m.TAG][:16]}")
    except Exception as exc:  # noqa: BLE001
        m.log(f"[FATAL] cannot verify deployed tag: {exc}")
        return 7
    return 0


def step4() -> int:
    m.log("=== STEP 4 v6 验收 3 轮 ===")
    for rnd in (1, 2, 3):
        if not m.verify_capture(m.TAG, rnd):
            m.log(f"[FATAL] v6 verify failed r{rnd}")
            return 8
        time.sleep(5)
    return 0


def step5() -> int:
    m.log("=== STEP 5 汇总报告 ===")
    summary = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": m.TAG,
               "basis": "measured", "corpus_sha256": hashlib.sha256(m.DATA.read_bytes()).hexdigest(),
               "corpus_rows": sum(1 for _ in m.DATA.open(encoding="utf-8")),
               "rounds": [], "gate": {}}
    v6_rounds = []
    for p in sorted(m.LOG.glob("verify_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        summary["rounds"].append({"tag": d["tag"], "round": d["round"],
                                  "passed": d["passed"], "total": d["total"], "failed": d["failed"]})
        if d["tag"] == m.TAG:
            v6_rounds.append({"round": d["round"], "passed": d["passed"], "total": d["total"],
                              "failed": d.get("failed")})
    if v6_rounds:
        worst = min(v6_rounds, key=lambda x: x["passed"])
        summary["gate"] = {
            "rule": "连测最差值做门禁 (project §8.2)",
            "v6_rounds_passed": [x["passed"] for x in v6_rounds],
            "worst_passed": worst["passed"],
            "worst_total": worst["total"],
            "worst_round": worst["round"],
            "worst_failed": worst["failed"],
        }
    out = ROOT / "reports" / "FULL_REPAIR_V6_2026-11-16.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    m.log(f"[DONE] 报告已落盘 {out.relative_to(ROOT)}")
    m.log(f"[GATE] {json.dumps(summary['gate'], ensure_ascii=False)}")
    return 0


def main() -> int:
    receipt = m.OUT_LORA / "training_receipt.json"
    if not receipt.is_file():
        m.log("[FATAL] training_receipt.json 不存在，训练未完成")
        return 2
    st = json.loads(receipt.read_text(encoding="utf-8"))
    if st.get("status") != "COMPLETED":
        m.log(f"[FATAL] 训练 receipt 状态={st.get('status')}，非 COMPLETED")
        return 3
    m.log(f"[OK] 训练凭证 COMPLETED | dev_loss {st.get('dev_loss_start')} -> {st.get('dev_loss_end')}")

    m.wait_exclusive()
    rc = step3()
    if rc:
        return rc
    rc = step4()
    if rc:
        return rc
    return step5()


if __name__ == "__main__":
    raise SystemExit(main())
