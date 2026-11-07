import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scratch.auto_monitor_and_deploy import get_ssh_client
import json

client = get_ssh_client()

# 1. 查看 log 末尾
stdin, stdout, stderr = client.exec_command('tail -n 35 /root/cloud_train_pack/output_13b/train_live.log')
text = stdout.read().decode('utf-8', errors='replace')
print("=== Latest train_live.log ===")
for l in text.splitlines():
    if not ('Loading weights' in l and '|' in l):
        print(l)

# 2. 查看评测报告
stdin, stdout, stderr = client.exec_command('cat /root/cloud_train_pack/output_13b/COMPREHENSIVE_EVAL_REPORT.json 2>/dev/null')
report_content = stdout.read().decode('utf-8', errors='replace')
if report_content.strip():
    print("\n=== COMPREHENSIVE_EVAL_REPORT.json ===")
    try:
        data = json.loads(report_content)
        print("Model:", data.get("model", data.get("run_id")))
        print("Overall Weighted Score:", data.get("overall_weighted_score", data.get("overall_score")))
        print("Physics Compliance:", data.get("physics_compliance", data.get("physics_gate")))
        print("Dimensions Summary:")
        dims = data.get("dimension_summary", data.get("dimensions", {}))
        for k, v in dims.items():
            print(f"  - {k}: {v.get('score', v.get('mean_score'))} (n={v.get('n', v.get('count'))})")
    except Exception as e:
        print("JSON parse error:", e)
        print(report_content[:500])
else:
    print("\nCOMPREHENSIVE_EVAL_REPORT.json not found yet.")

# 3. 输出文件列表
stdin, stdout, stderr = client.exec_command('ls -lh /root/cloud_train_pack/output_13b')
print("\n=== Output files in output_13b ===")
print(stdout.read().decode())

client.close()
