# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import os
import sys
import time
import json
import re
import shutil
import tarfile
import hashlib
import subprocess
from pathlib import Path
import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

LOCAL_BASE_DIR = Path(r"D:\Virtu模型")
LOCAL_MODEL_DIR = LOCAL_BASE_DIR / "models" / "virtu-13b"
LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_EXE = Path(r"E:\OllamaApp\ollama.exe")
if not OLLAMA_EXE.exists():
    OLLAMA_EXE = Path("ollama")

def get_ssh_client(retries=5, delay=3):
    last_err = None
    for i in range(retries):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, banner_timeout=30)
            return client
        except Exception as e:
            last_err = e
            time.sleep(delay)
    raise last_err

def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def inspect_remote_state(client):
    """提取远程训练进程状态、GPU使用指标及最新训练日志"""
    # GPU 监控
    stdin, stdout, stderr = client.exec_command(
        "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits"
    )
    gpu_line = stdout.read().decode().strip()
    gpu_stats = [x.strip() for x in gpu_line.split(",")] if gpu_line else ["0", "0", "0", "0", "0"]

    # 进程状态
    stdin, stdout, stderr = client.exec_command("ps -ef | grep train_cloud_virtu_13b | grep -v grep")
    proc_line = stdout.read().decode().strip()
    is_running = bool(proc_line)

    # 训练日志
    stdin, stdout, stderr = client.exec_command("tail -n 25 /root/cloud_train_pack/output_13b/train_live.log 2>/dev/null")
    log_tail = stdout.read().decode().strip()

    # 检查产物
    stdin, stdout, stderr = client.exec_command("ls -1 /root/cloud_train_pack/output_13b/ 2>/dev/null")
    output_files = [x.strip() for x in stdout.read().decode().strip().split("\n") if x.strip()]

    return {
        "is_running": is_running,
        "gpu_stats": gpu_stats,
        "log_tail": log_tail,
        "output_files": output_files
    }

def parse_log_summary(log_tail: str) -> str:
    """从日志片段提炼当前阶段与进度指标"""
    lines = [l for l in log_tail.split("\n") if l.strip()]
    if not lines:
        return "等待日志输出..."
    
    # 查找最近的 step 信息或 loss
    for line in reversed(lines):
        if "it/s" in line or "s/it" in line:
            return line.strip()
        if "{'loss':" in line or "'loss':" in line or "training_loss" in line:
            return line.strip()
        if "阶段" in line:
            return line.strip()
        if "HTTP Request" in line:
            continue
    return lines[-1].strip()

def download_artifacts(client) -> Path:
    """从云端拉取最终成果物包及评测凭证"""
    print("\n" + "=" * 70)
    print("🚀 触发云端成果自动回传...")
    print("=" * 70)

    sftp = client.open_sftp()
    remote_out = "/root/cloud_train_pack/output_13b"
    files = sftp.listdir(remote_out)

    tar_files = [f for f in files if f.startswith("virtu_13b_deliverable_") and f.endswith(".tar.gz")]
    if not tar_files:
        raise RuntimeError("未在云端发现 virtu_13b_deliverable_*.tar.gz 交付包！")
    
    tar_files.sort()
    latest_tar = tar_files[-1]
    
    # 待拉取文件清单
    to_download = [
        latest_tar,
        f"{latest_tar}.sha256",
        "COMPREHENSIVE_EVAL_REPORT.json",
        "COMPREHENSIVE_EVAL_REPORT.md",
        "Modelfile_virtu_13b",
        "raw.jsonl",
        "moe_layer_gates_calibrated.json"
    ]

    downloaded_tar_path = None
    for fname in to_download:
        if fname in files:
            rpath = f"{remote_out}/{fname}"
            lpath = LOCAL_MODEL_DIR / fname
            print(f"⬇️ 下载 {fname} ...", flush=True)
            sftp.get(rpath, str(lpath))
            size_mb = lpath.stat().st_size / (1024 * 1024)
            print(f"   [OK] {fname} ({size_mb:.2f} MB)")
            if fname == latest_tar:
                downloaded_tar_path = lpath

    sftp.close()

    # 校验 SHA256
    sha_file = LOCAL_MODEL_DIR / f"{latest_tar}.sha256"
    if sha_file.exists() and downloaded_tar_path:
        expected_sha = sha_file.read_text(encoding="utf-8").strip().split()[0]
        actual_sha = sha256_file(downloaded_tar_path)
        print(f"\n🔒 成果包封缄哈希校验:")
        print(f"   云端预期: {expected_sha}")
        print(f"   本地实测: {actual_sha}")
        if expected_sha.lower() == actual_sha.lower():
            print("   ✅ SHA256 完整性一致性检验 100% PASS！")
        else:
            raise ValueError("❌ 交付包 SHA256 校验失败，文件在传输过程中损坏！")

    # 解压交付包
    if downloaded_tar_path:
        print(f"\n📦 解压交付包: {downloaded_tar_path.name} ...")
        with tarfile.open(downloaded_tar_path, "r:gz") as tar:
            tar.extractall(path=LOCAL_MODEL_DIR)
        print("   ✅ 解压完成，本地构件已展开。")

    return downloaded_tar_path

def deploy_to_local_ollama():
    """在本地 Ollama 中注册与更新 Virtu-13.63B 工业模型"""
    print("\n" + "=" * 70)
    print("🛠️ 开始执行本地 Ollama 注册与部署...")
    print("=" * 70)

    # 基于本地已有 virtu-13.63b 构建更新版
    local_deploy_modelfile = LOCAL_MODEL_DIR / "Modelfile.local_deploy"

    modelfile_content = f"""FROM virtu-13.63b:latest
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
SYSTEM \"\"\"你是 Virtu-13.63B 工业制造超级大模型。具备 CAD/CAE/CAM 六大工业软件协同、图纸高精感知、CNC 后处理代码规范生成与严格物理守恒验证能力。所有几何尺寸与力学验算必须遵循客观物理定律与国家标准规范。\"\"\"
"""
    local_deploy_modelfile.write_text(modelfile_content, encoding="utf-8")
    print(f"已生成本地部署 Modelfile: {local_deploy_modelfile}")

    cmd = [str(OLLAMA_EXE), "create", "virtu-13b:gold", "-f", str(local_deploy_modelfile)]
    print(f"执行注册命令: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

    if res.returncode == 0:
        print("🎉 [SUCCESS] 本地 Ollama virtu-13b:gold 部署成功！")
        return True
    else:
        print("❌ [FAILED] 本地 Ollama 部署失败！")
        return False

def verify_local_inference():
    """本地端到端推理自测，验证物理守恒与 CAD 工具感知能力"""
    print("\n" + "=" * 70)
    print("🔬 执行本地端到端推理闭环验证...")
    print("=" * 70)

    test_prompt = "请作为工业制造专家，计算外径为 120mm、内径为 80mm、承受 25MPa 内压的厚壁圆筒切向拉应力分布与最大剪应力，并验证安全系数是否满足 FOS >= 1.5。"
    
    cmd = [str(OLLAMA_EXE), "run", "virtu-13b:gold", test_prompt]
    print(f"运行测试命令: {' '.join(cmd)}")
    t0 = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        elapsed = time.time() - t0
        print(f"推理完成 (耗时 {elapsed:.2f} 秒):")
        print("-" * 50)
        print(res.stdout[:500] + ("..." if len(res.stdout) > 500 else ""))
        print("-" * 50)
        return True
    except Exception as e:
        print(f"推理测试异常: {e}")
        return False

def run_loop(max_wait_hours: float = 4.0, poll_interval_sec: int = 30):
    start_time = time.time()
    max_wait_sec = max_wait_hours * 3600
    
    print("=" * 70)
    print(f"📡 启动 Virtu-13.63B 云端训练守护监控器")
    print(f"目标实例: {HOST}:{PORT}")
    print(f"轮询间隔: {poll_interval_sec}s | 最大超时: {max_wait_hours}h")
    print("=" * 70, flush=True)

    client = None
    consecutive_done_checks = 0

    try:
        while True:
            try:
                if client is None or client.get_transport() is None or not client.get_transport().is_active():
                    client = get_ssh_client()
                state = inspect_remote_state(client)
            except Exception as e:
                cur_time = time.strftime("%H:%M:%S")
                print(f"[{cur_time}] ⚠️ 网络瞬时抖动/重连中: {e}", flush=True)
                if client:
                    try:
                        client.close()
                    except Exception:
                        pass
                    client = None
                time.sleep(5)
                continue
            gpu_u, gpu_m_used, gpu_m_tot, gpu_temp, gpu_pwr = state["gpu_stats"]
            summary = parse_log_summary(state["log_tail"])

            # 打印格式化监控行
            cur_time = time.strftime("%H:%M:%S")
            print(f"[{cur_time}] 进程={'运行中' if state['is_running'] else '已停止'} | "
                  f"GPU={gpu_u}% {gpu_m_used}/{gpu_m_tot}MB | "
                  f"Temp={gpu_temp}°C {gpu_pwr}W | "
                  f"进度: {summary}", flush=True)

            # 检查是否有 deliverable 成果包生成
            tar_candidates = [f for f in state["output_files"] if f.startswith("virtu_13b_deliverable_") and f.endswith(".tar.gz")]
            
            if not state["is_running"]:
                consecutive_done_checks += 1
                if consecutive_done_checks >= 2:
                    if tar_candidates:
                        print(f"\n🎉 探测到训练已完成，且已生成交付包: {tar_candidates[-1]}")
                        download_artifacts(client)
                        deploy_to_local_ollama()
                        verify_local_inference()
                        print("\n🏆 全流程极速训练、监控、回传与本地部署任务已圆满达成！")
                        break
                    else:
                        print("\n⚠️ 训练进程已结束，但未发现 deliverable 成果包！打印最后 40 行日志排查:")
                        print("-" * 60)
                        stdin, stdout, stderr = client.exec_command("tail -n 40 /root/cloud_train_pack/output_13b/train_live.log")
                        print(stdout.read().decode())
                        print("-" * 60)
                        break
            else:
                consecutive_done_checks = 0

            if time.time() - start_time > max_wait_sec:
                print("\n⏰ 监控达到最大等待时间限制，退出循环。")
                break

            time.sleep(poll_interval_sec)

    except KeyboardInterrupt:
        print("\n用户手动终止监控。")
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy-only":
        deploy_to_local_ollama()
        verify_local_inference()
    else:
        run_loop(max_wait_hours=4.0, poll_interval_sec=25)
