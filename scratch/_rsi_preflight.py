"""Read-only RSI preflight: verify case loading + model availability. No engine run, no validation consumption."""
import sys, collections, pathlib
ROOT = r"D:\Virtu模型"
sys.path.insert(0, ROOT)

from virtu_omni.rsi.contracts import Config, Budget, load_cases
from virtu_omni.rsi.evaluation import LocalModel

CASE_DIR = "data/benchmark/virtu_eval_v1"
DIMS = ("generalization", "boundary", "reasoning", "knowledge", "instruction", "generation", "toolcall")

cases, protected = load_cases(ROOT, CASE_DIR, DIMS)
cnt = collections.Counter(c["dimension"] for c in cases)
print("selected_total:", len(cases))
print("per_dim:", dict(sorted(cnt.items())))
print("protected_total:", len(protected))

# fresh-value check against validation_seen for this model digest (informational)
seen = pathlib.Path(ROOT, "runs/rsi/validation_seen.jsonl")
print("validation_seen_lines:", len(seen.read_text(encoding="utf-8").splitlines()) if seen.exists() else 0)

cfg = Config(model_id="virtu-disciplined:v1", case_dir=CASE_DIR, dimensions=DIMS,
             max_seconds=300, max_calls=8, timeout=120)
b = Budget(cfg)
m = LocalModel(cfg, b)
print("identity:", m.identity)
g = m.generate([{"role": "user", "content": "用一句话写出主轴转速公式 n=1000Vc/(pi*D)，并说明单位。"}], max_tokens=96)
print("gen_error:", g.get("error"))
print("gen_finish:", g.get("finish_reason"))
print("gen_text:", (g.get("text") or "")[:200].replace("\n", "\\n"))
print("PREFLIGHT_OK" if not g.get("error") else "PREFLIGHT_FAIL")
