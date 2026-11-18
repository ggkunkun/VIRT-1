"""Full-eval launcher: wraps virtu_eval.runner.run in a top-level try/except so
any crash (including outside the per-case try) prints a full traceback instead of
a silent exit 1. Resumes from _eval_full3/raw.jsonl (append-only, by case id).
"""
import sys, os, json, traceback

sys.path.insert(0, os.getcwd())
import virtu_eval.runner as R

def main():
    arms = json.load(open("virtu_eval/arms.json", encoding="utf-8"))
    spec = arms["bridge_deployed"]
    root = os.getcwd()
    out = os.path.join(root, "_eval_full4")
    print("=== FULL eval resume into _eval_full3 ===", flush=True)
    try:
        R.run(os.path.join(root, "data/benchmark/virtu_eval_v1"), spec, out,
              temperature=0.0, seed=1234)
    except Exception:
        traceback.print_exc()
        sys.exit(2)
    print("=== run completed cleanly ===", flush=True)

if __name__ == "__main__":
    main()
