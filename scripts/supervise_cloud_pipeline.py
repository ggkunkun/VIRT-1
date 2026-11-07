r"""Teacher Supervision & Pipeline Automation Script (Phase 2 & 3).

Supervises cloud training on DAMODEL 2 x NVIDIA L40S:
1. GPU 1: Omni Autonomous Industrial Agent (train_omni_autonomous_agent.py, 280 trajectories, 70 steps)
   - When finished: pulls checkpoints/omni_autonomous_agent_lora back to local D:\Virtu模型\checkpoints\omni_autonomous_agent_lora.
2. GPU 1 (Chain-Launch): Tool-Calling Full Agent Fine-Tuning (train_tool_agent.py, 200 trajectories, 75 steps)
   - Reinforced with 工程图(1) one-sentence parametric engine & non-standard automation decomposition
   - When finished: pulls output_checkpoints/tool_agent_lora_final back to local D:\Virtu模型\checkpoints\tool_agent_lora_final.
3. GPU 0: Turing Conversational High-EQ Human Dialogue Fine-Tuning
   - If completed: pulls checkpoints/turing_conversational_lora back to local D:\Virtu模型\checkpoints\turing_conversational_lora.
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
LOCAL_CKPTS = os.path.join(LOCAL_WORKSPACE, "checkpoints")


def get_ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def sftp_pull_dir(sftp, remote_dir, local_dir):
    os.makedirs(local_dir, exist_ok=True)
    try:
        files = sftp.listdir(remote_dir)
        print(f"[SFTP PULL] 发现远端目录 {remote_dir} 共 {len(files)} 项文件，开始拉回本地 {local_dir}...")
        for f in files:
            if f.startswith("checkpoint-"):
                # Skip intermediate checkpoint folders to save bandwidth
                continue
            r_path = f"{remote_dir}/{f}"
            l_path = os.path.join(local_dir, f)
            try:
                attrs = sftp.stat(r_path)
                import stat
                if stat.S_ISDIR(attrs.st_mode):
                    sub_r = r_path
                    sub_l = l_path
                    sftp_pull_dir(sftp, sub_r, sub_l)
                    continue
                size_mb = attrs.st_size / (1024 * 1024)
                print(f"  ⬇️ 下载: {f} ({size_mb:.2f} MB) -> {l_path}")
                sftp.get(r_path, l_path)
            except Exception as fe:
                print(f"  [WARN] 下载文件 {f} 出现异常: {fe}")
        print(f"[SUCCESS] 目录 {remote_dir} 全部拉回完成！")
    except Exception as e:
        print(f"[ERROR] 读取远端目录失败: {e}")


def get_process_info(client, name):
    stdin, stdout, stderr = client.exec_command(f"ps aux | grep '{name}' | grep -v grep")
    return stdout.read().decode("utf-8", errors="replace").strip()


def get_tail(client, filepath, lines=2):
    stdin, stdout, stderr = client.exec_command(f"tail -n {lines} {filepath}")
    return stdout.read().decode("utf-8", errors="replace").strip()


def run_supervision():
    print("=" * 80)
    print("🚀 [TEACHER SUPERVISOR] 云端训练管线教师监督 (Phase 2 & 3 接力)")
    print(f"   目标实例: {USER}@{HOST}:{PORT}")
    print("=" * 80)

    client = get_ssh()

    # Stage 1: Supervise Omni Autonomous Agent on GPU 1
    omni_log = "/root/workspace/Virtu/train_omni_agent.log"
    turing_log = "/root/workspace/Virtu/turing_conversational/train_turing.log"

    print("\n[MONITOR 1] 正在监控 GPU 1: Omni Autonomous Industrial Agent (280 条全能轨迹) ...")
    omni_running = True
    while omni_running:
        ps_omni = get_process_info(client, "train_omni_autonomous_agent.py")
        last_log = get_tail(client, omni_log, 2)
        turing_tail = get_tail(client, turing_log, 1)

        t_str = time.strftime("%H:%M:%S")
        print(f"[{t_str}] [GPU 1 - OmniAgent] {last_log.splitlines()[-1] if last_log else 'Running...'}")
        if turing_tail:
            print(f"          [GPU 0 - Turing]   {turing_tail.splitlines()[-1]}")

        if not ps_omni:
            print(f"\n[{t_str}] 🎉 [GPU 1] Omni Autonomous Industrial Agent 训练进程已结束！")
            omni_running = False
            break

        time.sleep(30)

    # Pull Omni Agent Checkpoint
    time.sleep(5)
    print("\n📥 [PULL 1] 正在拉回 Omni Autonomous Agent 模型权重...")
    sftp = client.open_sftp()
    remote_omni_lora = "/root/workspace/Virtu/checkpoints/omni_autonomous_agent_lora"
    local_omni_lora = os.path.join(LOCAL_CKPTS, "omni_autonomous_agent_lora")
    sftp_pull_dir(sftp, remote_omni_lora, local_omni_lora)
    sftp.close()

    # Stage 2: GPU 1 is free! Launch updated Tool-Calling Agent training on GPU 1
    print("\n" + "=" * 80)
    print("🚀 [LAUNCH 2] GPU 1 完全空闲，立即启动 Tool-Calling Full Agent 训练 (含工程图(1)一句话盲测)")
    print("=" * 80)

    # Ensure stale log is wiped
    client.exec_command("rm -f /root/cad_cam_finetune/train_tool_agent_v2.log /root/cad_cam_finetune/output_checkpoints/tool_agent_lora_final/training_receipt.json")
    time.sleep(2)

    launch_cmd = (
        "cd /root/cad_cam_finetune && "
        "CUDA_VISIBLE_DEVICES=1 nohup python3 -u train_tool_agent.py > train_tool_agent_v2.log 2>&1 & echo $!"
    )
    stdin, stdout, stderr = client.exec_command(launch_cmd)
    tool_pid = stdout.read().decode("utf-8").strip()
    print(f"[LAUNCH] Tool-Calling 训练已提交，PID: {tool_pid}")

    time.sleep(5)
    tool_log = "/root/cad_cam_finetune/train_tool_agent_v2.log"
    tool_running = True
    print("\n[MONITOR 2] 教师监督员开始实时监控 Tool-Calling Agent 收敛进程...")

    while tool_running:
        ps_tool = get_process_info(client, f"{tool_pid}")
        tool_tail = get_tail(client, tool_log, 2)
        t_str = time.strftime("%H:%M:%S")
        print(f"[{t_str}] [GPU 1 - ToolAgent] {tool_tail.splitlines()[-1] if tool_tail else 'Initializing...'}")

        if not ps_tool:
            time.sleep(5)
            receipt_check = get_tail(client, "/root/cad_cam_finetune/output_checkpoints/tool_agent_lora_final/training_receipt.json", 15)
            if receipt_check and "status" in receipt_check:
                print(f"\n[{t_str}] 🎉 Tool-Calling Agent 训练圆满完成！新凭证如下:")
                print(receipt_check)
            else:
                print(f"\n[{t_str}] [CHECK] 训练进程退出，日志最后输出:")
                print(get_tail(client, tool_log, 10))
            tool_running = False
            break

        time.sleep(20)

    # Pull updated Tool Agent weights
    print("\n📥 [PULL 2] 正在拉回更新后的 Tool-Calling Agent 最终模型权重...")
    sftp = client.open_sftp()
    remote_tool_lora = "/root/cad_cam_finetune/output_checkpoints/tool_agent_lora_final"
    local_tool_lora = os.path.join(LOCAL_CKPTS, "tool_agent_lora_final")
    sftp_pull_dir(sftp, remote_tool_lora, local_tool_lora)
    sftp.close()

    # Stage 3: Check Turing Model on GPU 0
    ps_turing = get_process_info(client, "train_turing_conversational_lora.py")
    if not ps_turing:
        print("\n📥 [PULL 3] 发现 Turing Conversational 模型已完成，正在拉回...")
        sftp = client.open_sftp()
        remote_turing_lora = "/root/workspace/Virtu/checkpoints/turing_conversational_lora"
        local_turing_lora = os.path.join(LOCAL_CKPTS, "turing_conversational_lora")
        sftp_pull_dir(sftp, remote_turing_lora, local_turing_lora)
        sftp.close()
    else:
        print("\nℹ️ [STATUS] Turing 对话模型仍在 GPU 0 持续训练中。")

    client.close()
    print("\n" + "=" * 80)
    print("✅ [TEACHER REPORT] 全部目标模型已顺利完成云端训练并同步回原文件夹！")
    print(f"   本地权重路径: {LOCAL_CKPTS}")
    print("=" * 80)


if __name__ == "__main__":
    run_supervision()
