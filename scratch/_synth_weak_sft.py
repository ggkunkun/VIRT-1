"""GPU-free weight-level lever: generate solver-verified, contamination-checked SFT
candidates for the weak numeric/physics tasks, using the same analytic oracles RSI
uses. No model calls, no training, no production change.
"""
import json, pathlib, sys
sys.path.insert(0, r"D:\Virtu模型")

from virtu_omni.rsi.contracts import Config, load_cases, read_jsonl
from virtu_omni.rsi.candidates import build_sft_candidates, SUPPORTED
from virtu_omni.rsi.storage import RunStore

ROOT = pathlib.Path(r"D:\Virtu模型")
CASE_DIR = "data/benchmark/virtu_eval_phys_v1"

# Known-weak numeric/physics task families (from board: physics 49.3 / derivation 40.4,
# and reasoning's 53 numeric_near failures). These are exactly the tasks the analytic
# solver can verify, so the synthetic rows are trustworthy training material.
feedback = {"weak_tasks": {t: 1 for t in sorted(SUPPORTED)}}
protected, _ = load_cases(str(ROOT), CASE_DIR)  # all 60 physics/derivation cases, no dim filter
hard_holdout_path = ROOT / "data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl"
hard_holdout = read_jsonl(hard_holdout_path) if hard_holdout_path.exists() else []

cfg = Config(model_id="offline-solver", case_dir=CASE_DIR, dimensions=("physics", "derivation"),
             seed=20261104, synthetic_per_task=12)
store = RunStore(str(ROOT))
rows, report = build_sft_candidates(feedback, protected, hard_holdout, cfg, store)

out = ROOT / "data/sft/rsi_synth_weak_2026-11-05.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print("run_dir:", store.path.name)
print("rows:", len(rows))
print("tasks:", report["tasks"])
print("skipped:", report["skipped"])
print("out:", out.relative_to(ROOT).as_posix(), "bytes:", out.stat().st_size)
