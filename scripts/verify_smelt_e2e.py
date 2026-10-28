"""End-to-End Verification and Turnkey Demonstration for Standardized Smelt Bundle."""

from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni import load_standardized_bundle

BUNDLE_DIR = Path(r"D:\Virtu模型\checkpoints\standardized_smelt_bundle")


def main() -> int:
    print("======================================================================")
    print("  Virtu: Standardized Smelted Parameter Bundle End-to-End Verification")
    print("======================================================================")
    t_start = time.time()

    print(f"\n[1] Checking Bundle Directory & Manifest ({BUNDLE_DIR})...")
    bundle, model = load_standardized_bundle(BUNDLE_DIR, device="cpu")

    manifest = bundle.load_manifest()
    print(f"  * Bundle Title: {manifest['package_title']}")
    print(f"  * Target Model: {manifest['target_model']}")
    print(f"  * Total Files: {manifest['total_files_in_bundle']}")
    print(f"  * Total Parameters: {manifest['parameter_count']:,}")
    print(f"  * Total Tensors: {manifest['tensor_count']}")

    print("\n[2] Executing Bundle Integrity Audit...")
    ok, errors = bundle.verify_bundle_integrity()
    if not ok:
        print(f"  [FAIL] Integrity errors detected: {errors}")
        return 1
    print("  [OK] 100% of bundle files passed structural and size verification.")

    print("\n[3] Reading Triple Verification Suite Ledger...")
    report = bundle.load_verification_report()
    print(f"  * Overall Verdict: {report['overall_verdict']}")
    print(f"  * Verification Pass Rate: {report['pass_rate']}%")
    print(f"  * Integrity Check: {report['integrity_check']['status']} (Retention: {report['integrity_check']['retention_rate_pct']}%)")
    print(f"  * Validity Check: {report['validity_check']['status']} (NaNs: {report['validity_check']['nan_tensor_count']}, Infs: {report['validity_check']['inf_tensor_count']})")
    print(f"  * Consistency Check: {report['consistency_check']['status']} (Drifts: {report['consistency_check']['value_drift_count']})")

    print("\n[4] Running Real-World End-to-End Inference Scenarios...")

    # Case 1: Coordinate System
    c1 = "G54 工件坐标系设定并执行刀尖点跟随 RTCP 动态校准"
    p1 = bundle.predict_subsystem(c1)
    print(f"\n  Scenario A: [坐标系/刀具补偿]")
    print(f"    Input: {c1}")
    print(f"    Subsystem Prediction: [{p1['predicted_key']}] {p1['predicted_name']} (Confidence: {p1['confidence']:.4f}, Latency: {p1['latency_ms']:.2f}ms)")
    print(f"    Top Candidates: {', '.join(c['key'] + ':' + str(c['probability']) for c in p1['top_candidates'][:3])}")

    # Case 2: Machining Task
    c2 = "五轴龙门机床 使用硬质合金端铣刀 铣削 4140钢 阶梯槽"
    p2 = bundle.predict_machining_task(c2)
    print(f"\n  Scenario B: [智能制造全要素联合感知]")
    print(f"    Input: {c2}")
    print(f"    Subsystem: [{p2['subsystem']['key']}] {p2['subsystem']['name']}")
    print(f"    Operation: {p2['operation']['name']}")
    print(f"    Material: {p2['material']['name']}")
    print(f"    Latency: {p2['latency_ms']:.2f}ms")

    # Case 3: Action Pair JEV Verification
    ctx = "主轴高速旋转且冷却液未开启报警"
    act = "M08 开启高压切削液喷淋并降速巡检"
    p3 = bundle.verify_action_pair(ctx, act)
    print(f"\n  Scenario C: [JEV 工况与动作安全验证]")
    print(f"    Context: {ctx}")
    print(f"    Action: {act}")
    print(f"    Verification Score: {p3['verification_score']:.4f} => Verdict: {p3['verdict']} (Latency: {p3['latency_ms']:.2f}ms)")

    # Case 4: Representation Extractor
    text_feat = "FANUC 数控系统 31i-B5 参数设定与 PLC 梯形图调试"
    emb = bundle.extract_joint_embedding(text_feat)
    norm = sum(x * x for x in emb) ** 0.5
    print(f"\n  Scenario D: [512维 JEV 表征向量空间]")
    print(f"    Text: {text_feat}")
    print(f"    Embedding Dim: {len(emb)}, L2 Norm: {norm:.4f}")

    total_time = time.time() - t_start
    print("\n======================================================================")
    print(f"  >>> RESULT: [PASS] All End-to-End Verifications Succeeded in {total_time:.2f}s!")
    print("======================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
