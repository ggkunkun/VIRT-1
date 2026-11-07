# -*- coding: utf-8 -*-
"""SFT 复评（bridge arm）：与基线 _eval_full4 完全同口径的 before/after 对比（已修复指纹冲突版）。

修复项：
  当输出目录已存在旧 `manifest.json` 且 `harness_source_sha256` 或 `arm` 指纹发生变化时
  （参见 `_eval_full3.log` 中的 `ValueError: Refusing to resume with a different evaluation fingerprint`），
  自动将旧目录归档备份为 `<OUT>_ archive_<timestamp>`，避免中断评测。
"""
import argparse
import json
import os
import shutil
import sys
import time
import traceback

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.getcwd())

ARM = "bridge_deployed"
OUT = os.path.join(os.getcwd(), "_eval_sft_bridge")


def _archive_if_fingerprint_changed(out_dir: str, spec: dict) -> None:
    manifest_path = os.path.join(out_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        old_m = json.load(open(manifest_path, encoding="utf-8"))
        old_arm = old_m.get("arm", {})
        if old_arm.get("model_id") != spec.get("model_id") or old_arm.get("base_url") != spec.get("base_url"):
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_dir = f"{out_dir}_bak_{ts}"
            shutil.move(out_dir, backup_dir)
            print(f"[eval] Archived mismatched manifest directory -> {backup_dir}", flush=True)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="Run Virtu 240-case evaluation via bridge arm")
    ap.add_argument("--arm", default=ARM, help="Arm key in virtu_eval/arms.json")
    ap.add_argument("--out", default=OUT, help="Output directory for raw.jsonl and manifest.json")
    ap.add_argument("--fresh", action="store_true", help="Archive existing output directory before running")
    args = ap.parse_args()

    import virtu_eval.runner as R  # noqa: E402

    arms = json.load(open("virtu_eval/arms.json", encoding="utf-8"))
    spec = arms[args.arm]
    if args.fresh and os.path.exists(args.out):
        ts = time.strftime("%Y%m%d_%H%M%S")
        shutil.move(args.out, f"{args.out}_bak_{ts}")
    else:
        _archive_if_fingerprint_changed(args.out, spec)

    case_dir = os.path.join(os.getcwd(), "data/benchmark/virtu_eval_v1")
    print(f"=== SFT 复评 arm={args.arm} model_id={spec['model_id']} -> {args.out} ===", flush=True)
    try:
        R.run(case_dir, spec, args.out, temperature=0.0, seed=1234)
    except ValueError as ve:
        if "Refusing to resume with a different evaluation fingerprint" in str(ve):
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_dir = f"{args.out}_fingerprint_bak_{ts}"
            print(f"[eval] Fingerprint changed ({ve}); archiving old run to {backup_dir} and starting fresh...", flush=True)
            shutil.move(args.out, backup_dir)
            R.run(case_dir, spec, args.out, temperature=0.0, seed=1234)
        else:
            raise
    except Exception:
        traceback.print_exc()
        sys.exit(2)
    print("=== run completed cleanly ===", flush=True)


if __name__ == "__main__":
    main()
