import json
import time

PROV_PATH = r"D:\Virtu模型\checkpoints\PROVENANCE.json"

with open(PROV_PATH, "r", encoding="utf-8") as f:
    prov = json.load(f)

prov["virtu_moe_14b_benchmark_seal"] = {
    "status": "GATE_PASSED",
    "basis": "measured",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "arm": "virtu_moe_14b",
    "model_id": "virtu-moe-14b:latest",
    "num_ctx": 8192,
    "num_gpu": 22,
    "run_dir": "runs/eval/virtu_moe_smoke",
    "recorded_cases": 7,
    "transport_errors": 0,
    "native_tool_call_verified": True,
    "overall_weighted_score": 48.76,
    "radar_png": "runs/eval/virtu_moe_smoke/virtu_capability_radar.png",
    "results_json": "runs/eval/virtu_moe_smoke/results.json"
}

with open(PROV_PATH, "w", encoding="utf-8") as f:
    json.dump(prov, f, indent=2, ensure_ascii=False)

print("PROVENANCE.json updated with virtu_moe_14b_benchmark_seal")
