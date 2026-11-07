import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scratch.auto_monitor_and_deploy import get_ssh_client

client = get_ssh_client()

# 查看进程运行堆栈和状态
cmd = """
python3 -c "
import json, os, glob

cases_file = '/root/data/benchmark/comprehensive_240.jsonl'
if not os.path.exists(cases_file):
    fl = glob.glob('/root/**/comprehensive_*.jsonl', recursive=True)
    cases_file = fl[0] if fl else ''

if cases_file:
    cases = [json.loads(l) for l in open(cases_file)]
    print(f'Cases loaded: {len(cases)}')
    dims = {}
    for i, c in enumerate(cases):
        d = c.get('dimension', c.get('dim', 'unknown'))
        dims[d] = dims.get(d, 0) + 1
    print('Dimensions:', dims)
"
"""
stdin, stdout, stderr = client.exec_command(cmd)
print("Dataset info:")
print(stdout.read().decode())

# 查看当前显卡功耗与活跃线程
stdin, stdout, stderr = client.exec_command("cat /proc/19174/status | grep -E 'State|Threads|voluntary_ctxt_switches'")
print("Process 19174 status:")
print(stdout.read().decode())

# 查看 train_live.log 最新末尾
stdin, stdout, stderr = client.exec_command("tail -n 25 /root/cloud_train_pack/output_13b/train_live.log")
print("=== Latest train_live.log ===")
for l in stdout.read().decode('utf-8', errors='replace').splitlines():
    if not ('Loading weights' in l and '|' in l):
        print(l)

client.close()
