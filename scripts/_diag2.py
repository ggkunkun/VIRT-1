import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
cmd = (
    "echo '=== installed versions ==='; "
    "/opt/conda/bin/python3.11 -m pip show transformers accelerate 2>/dev/null | grep -E '^(Name|Version)'; "
    "echo '=== accelerate has parallelism_config? ==='; "
    "/opt/conda/bin/python3.11 -c \"from accelerate import Accelerator; print('hasattr parallelism_config =', hasattr(Accelerator, 'parallelism_config')); import accelerate; print('acc', accelerate.__version__)\" 2>&1; "
    "echo '=== transformers references to parallelism_config ==='; "
    "grep -rn 'parallelism_config' /opt/conda/lib/python3.11/site-packages/transformers/trainer.py 2>/dev/null | head; "
    "echo '=== transformers requires accelerate? ==='; "
    "grep -rn 'accelerate' /opt/conda/lib/python3.11/site-packages/transformers/setup.py 2>/dev/null | head; "
    "grep -rn 'accelerate' /opt/conda/lib/python3.11/site-packages/transformers/pyproject.toml 2>/dev/null | head"
)
out, err, rc = S.run(cmd, timeout=90)
print(out)
if err.strip(): print("STDERR:", err[:1200])
