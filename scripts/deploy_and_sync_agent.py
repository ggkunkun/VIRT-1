r"""Teacher Supervision & Deployment Script for Industrial Tool-Calling Agent.

Handles:
1. Uploading dataset (toolcall_automation_feature_tree_sft.jsonl), tools schema, and training script to DAMODEL.
2. Launching and supervising training progress (loss, steps, GPU memory).
3. Automatically pulling down trained LoRA model back to local checkpoints folder (D:\Virtu模型\checkpoints\tool_agent_lora_final).
"""

import os
import sys
import time
import json
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
PORT = int(os.environ.get("DAMODEL_PORT", "42688"))
USER = os.environ.get("DAMODEL_USER", "root")
PASS = os.environ.get("DAMODEL_PASS", "")

LOCAL_WORKSPACE = r"D:\Virtu模型"
LOCAL_DATASET = os.path.join(LOCAL_WORKSPACE, "damodel_cad_cam_tuning", "dataset", "toolcall_full_cad_cam_agent_sft.jsonl")
LOCAL_TOOLS = os.path.join(LOCAL_WORKSPACE, "data", "tools", "industrial_agent_tools.json")
LOCAL_TRAIN_PY = os.path.join(LOCAL_WORKSPACE, "scripts", "train_tool_agent.py")
LOCAL_CHECKPOINTS = os.path.join(LOCAL_WORKSPACE, "checkpoints", "tool_agent_lora_final")

REMOTE_WORK_DIR = "/root/cad_cam_finetune"
REMOTE_OUT_DIR = f"{REMOTE_WORK_DIR}/output_checkpoints/tool_agent_lora_final"


def check_auth():
    if not PASS:
        print("[FATAL] 请在运行前通过环境变量设置 DAMODEL_PASS：")
        print('  PowerShell: $env:DAMODEL_PASS = "您的实例密码"')
        print('  如需指定端口: $env:DAMODEL_PORT = "实例端口"')
        sys.exit(1)


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def upload_training_assets():
    print(f"=== [TEACHER] 1. 连接云端实例并上传训练资产 ({USER}@{HOST}:{PORT}) ===")
    client = get_ssh_client()
    sftp = client.open_sftp()

    # Ensure remote directory exists
    stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_WORK_DIR}/output_checkpoints")
    stdout.read()

    # Upload dataset
    remote_data = f"{REMOTE_WORK_DIR}/toolcall_full_cad_cam_agent_sft.jsonl"
    print(f"[UPLOAD] 数据集 -> {remote_data} ({os.path.getsize(LOCAL_DATASET):,} bytes)")
    sftp.put(LOCAL_DATASET, remote_data)

    # Upload tools schema
    remote_tools = f"{REMOTE_WORK_DIR}/industrial_agent_tools.json"
    print(f"[UPLOAD] 工具定义 -> {remote_tools}")
    sftp.put(LOCAL_TOOLS, remote_tools)

    # Upload training script
    remote_script = f"{REMOTE_WORK_DIR}/train_tool_agent.py"
    print(f"[UPLOAD] 训练脚本 -> {remote_script}")
    sftp.put(LOCAL_TRAIN_PY, remote_script)

    sftp.close()
    client.close()
    print("[SUCCESS] 资产上传完毕！\n")


def launch_and_supervise():
    print("=== [TEACHER] 2. 启动训练并执行教师监督 (Teacher Supervision) ===")
    client = get_ssh_client()

    # Check GPU status
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader")
    gpu_info = stdout.read().decode("utf-8").strip()
    print(f"[HARDWARE] 云端 GPU 环境: {gpu_info}")

    # Launch training script with nohup
    cmd = (
        f"cd {REMOTE_WORK_DIR} && "
        f"export PYTHONPATH={REMOTE_WORK_DIR}:$PYTHONPATH && "
        f"CUDA_VISIBLE_DEVICES=0 nohup python3 -u train_tool_agent.py > train_agent.log 2>&1 & echo $!"
    )
    stdin, stdout, stderr = client.exec_command(cmd)
    pid = stdout.read().decode("utf-8").strip()
    print(f"[LAUNCH] 训练进程已启动，PID: {pid}")

    # Supervise loop
    print("[SUPERVISION] 教师监督员开始实时监控训练日志与收敛状态...\n")
    log_cmd = f"tail -n 20 {REMOTE_WORK_DIR}/train_agent.log"
    finished = False

    while not finished:
        time.sleep(15)
        stdin, stdout, stderr = client.exec_command(f"ps aux | grep {pid} | grep -v grep")
        ps_out = stdout.read().decode("utf-8").strip()

        stdin, stdout, stderr = client.exec_command(log_cmd)
        recent_log = stdout.read().decode("utf-8", errors="replace")

        # Extract latest status
        lines = [l for l in recent_log.split("\n") if l.strip()]
        last_line = lines[-1] if lines else "Waiting for training output..."
        print(f"[PROGRESS] {last_line}")

        if not ps_out:
            print("[INFO] 训练主进程已退出，检查最终状态...")
            finished = True

    # Check final receipt
    stdin, stdout, stderr = client.exec_command(f"cat {REMOTE_OUT_DIR}/training_receipt.json")
    receipt_str = stdout.read().decode("utf-8").strip()
    if receipt_str:
        print("\n=== [TEACHER REPORT] 训练完成核查凭证 ===")
        print(receipt_str)
    else:
        print("[WARNING] 未发现 training_receipt.json，请核查 train_agent.log 日志。")

    client.close()


def pull_back_model():
    print(f"\n=== [TEACHER] 3. 训练产物回流本地: {REMOTE_OUT_DIR} -> {LOCAL_CHECKPOINTS} ===")
    os.makedirs(LOCAL_CHECKPOINTS, exist_ok=True)
    client = get_ssh_client()
    sftp = client.open_sftp()

    try:
        files = sftp.listdir(REMOTE_OUT_DIR)
        print(f"[PULL] 发现云端权重产物 {len(files)} 项: {files}")
        for f in files:
            r_file = f"{REMOTE_OUT_DIR}/{f}"
            l_file = os.path.join(LOCAL_CHECKPOINTS, f)
            print(f"  正在下载: {f} ...")
            sftp.get(r_file, l_file)
        print(f"[SUCCESS] 模型权重已全部成功拉回本地文件夹: {LOCAL_CHECKPOINTS}！")
    except Exception as e:
        print(f"[ERROR] 拉回权重失败: {e}")
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    check_auth()
    upload_training_assets()
    launch_and_supervise()
    pull_back_model()
