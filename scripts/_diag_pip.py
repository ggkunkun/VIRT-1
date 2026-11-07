import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S
cmd = (
    "echo '=== who needs tokenizers ==='; "
    "/opt/conda/bin/python3.11 -m pip show tokenizers 2>/dev/null | head -3; "
    "echo '--- reverse deps ---'; "
    "/opt/conda/bin/python3.11 -m pip install transformers==4.56.0 2>&1 | tail -25"
)
out, err, rc = S.run(cmd, timeout=180)
print(out)
if err.strip(): print("STDERR:", err[:2000])
