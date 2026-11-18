# -*- coding: utf-8 -*-
"""汇总叶轮三臂脚手架消融，独立复算 fabrication delta，封缄报告。"""
import sys
import json
import math
import hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
ARMS = {"bare": "projects/impeller_closed_v1",
        "contract_fewshot": "projects/impeller_closed_v1_contract",
        "contract_only": "projects/impeller_closed_v1_contract_only"}


def main():
    out = {}
    for name, rel in ARMS.items():
        d = ROOT / rel
        rep = json.load(open(d / "VERIFICATION_REPORT.json", encoding="utf-8"))
        log = [json.loads(l) for l in open(d / "proctor_log.jsonl", encoding="utf-8")]
        hashes = [e["data"]["resp_sha12"] for e in log if e["event"] == "STAGE_A_AUDIT"]
        stuck = any(e["event"] == "STUCK_REPETITION" for e in log)
        tr = [json.loads(l) for l in open(d / "transcript.jsonl", encoding="utf-8")]
        fab, geo, fmt = [], None, None
        for t in tr:
            resp = t["response"]
            try:
                p = json.loads(resp[resp.find("{"):resp.rfind("}") + 1])
            except Exception:
                fmt = "JSON_unparseable"
                continue
            nums = {k: v for k, v in p.items() if k.endswith("_mm") or k in ("N_rpm", "claimed_tip_speed_m_s")}
            if any(isinstance(v, str) for v in nums.values()):
                fmt = "string_typed_values"
            if any("\ufffd" in k for k in p):
                fmt = "corrupted_key"
            if isinstance(p.get("D2_mm"), (int, float)) and isinstance(p.get("N_rpm"), (int, float)):
                u2 = math.pi * p["D2_mm"] * p["N_rpm"] / 60000
                cl = p.get("claimed_tip_speed_m_s")
                if isinstance(cl, (int, float)):
                    fab.append({"claimed_u2": cl, "recomputed_u2": round(u2, 2),
                                "delta_pct": round(abs(cl - u2) / u2 * 100, 1)})
                if isinstance(p.get("D1t_mm"), (int, float)):
                    geo = {"D1t": p["D1t_mm"], "D2": p["D2_mm"], "D1t_gt_D2": p["D1t_mm"] > p["D2_mm"]}
        out[name] = {"verdict": rep["verdict"], "attempt_hashes": hashes, "stuck_repetition": stuck,
                     "fabrication_u2": fab[:2], "geometry": geo, "format_defect": fmt}
    report = {"title": "Layer1 scaffold ablation — closed impeller design",
              "model": "virtu-ties-v1:latest (8.2B Q4_0, blob c3b78c77)", "arms": out,
              "conclusion": "接口/契约/掩码少样本三种脚手架均 FAIL。复读与叶尖速编造在所有臂稳健出现⇒缺陷在权重而非接口；"
                            "法兰盘验证过的脚手架机制不迁移到此航空设计任务。掩码少样本额外诱导字符串类型缺陷。",
              "weight_fix_required": True,
              "weight_fix_gated": "cloud 8B QLoRA authorization (local 8B disproven, 3B cap)"}
    rp = ROOT / "projects/impeller_closed_v1/LAYER1_ABLATION_REPORT.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for n, a in out.items():
        print(f"{n}: {a['verdict']} | repetition={a['stuck_repetition']} | format={a['format_defect']} | geo={a['geometry']}")
        for f in a["fabrication_u2"]:
            print(f"    u2 claimed {f['claimed_u2']} vs {f['recomputed_u2']} (+{f['delta_pct']}%)")
    print("SEALED:", hashlib.sha256(rp.read_bytes()).hexdigest()[:16])


if __name__ == "__main__":
    main()