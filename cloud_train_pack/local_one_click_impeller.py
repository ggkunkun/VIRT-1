# -*- coding: utf-8 -*-
"""cloud_train_pack/local_one_click_impeller.py — 8.2B 叶轮与全链路定向修复云端训练闭环。

功能：
1. 打包前对语料与脚本执行本地静态与闸门自检（防泄漏 + 量纲审计 + 多轮坏解 Loss 掩码自检）；
2. 打包完整 bundle（train_turnkey + train_turnkey_impeller + 闸门模块 + benchmark + 4份修复语料 + run_impeller_fix.sh）；
3. SSH 上传云端 GPU（V100/A100/4090）→ nohup 开训 → 实时流式监控 → 回收 LoRA 交付件（自动同步 fix 与 fix2 双文件名）；
4. 支持 `--pack-only` 零网络打包自检，支持 `--auto-deploy` 回收后自动触发本地合并、GGUF 量化与 Ollama 注册。
"""
import os
import sys
import json
import time
import shutil
import tarfile
import argparse
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
try:
    import paramiko
except ImportError:
    paramiko = None

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "cloud_train_pack"
ARCHIVE = PACK / "virtu_impeller_fix_bundle.tar.gz"
CREDS = PACK / ".cloud_creds.json"
REMOTE_DIR = "/root/virtu_train"
DELIVER_REL = "output/virtu_impeller_fix2_lora/virtu_lora_deliverable.tar.gz"
DELIVER_REL_FALLBACK = "output/virtu_impeller_fix_lora/virtu_lora_deliverable.tar.gz"
LOCAL_OUT = PACK / "output_impeller"

BUNDLE_FILES = [
    ("cloud_train_pack/train_turnkey.py", "train_turnkey.py"),
    ("cloud_train_pack/train_turnkey_impeller.py", "train_turnkey_impeller.py"),
    ("cloud_train_pack/run_impeller_fix.sh", "run_impeller_fix.sh"),
    ("cloud_train_pack/dataset/virtu_impeller_fix_sft.jsonl", "dataset/virtu_impeller_fix_sft.jsonl"),
    ("cloud_train_pack/dataset/virtu_impeller_repairloop_sft.jsonl", "dataset/virtu_impeller_repairloop_sft.jsonl"),
    ("cloud_train_pack/dataset/virtu_impeller_hardened_sft.jsonl", "dataset/virtu_impeller_hardened_sft.jsonl"),
    ("cloud_train_pack/dataset/virtu_impeller_retrain_sft.jsonl", "dataset/virtu_impeller_retrain_sft.jsonl"),
    ("virtu_eval/__init__.py", "virtu_eval/__init__.py"),
    ("virtu_eval/contamination_check.py", "virtu_eval/contamination_check.py"),
    ("scripts/corpus_unit_audit.py", "scripts/corpus_unit_audit.py"),
    ("requirements-v100.txt", "requirements-v100.txt"),
]
BENCHMARK_DIR = "data/benchmark/virtu_eval_v1"


def preflight_audit():
    """打包前强制校验语料防泄漏、量纲与多轮坏解 Loss 掩码标记。"""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from virtu_eval.contamination_check import assert_no_leak
    from corpus_unit_audit import assert_units_clean

    retrain_path = ROOT / "cloud_train_pack/dataset/virtu_impeller_retrain_sft.jsonl"
    assert_no_leak(str(retrain_path))
    assert_units_clean(str(retrain_path))

    # 校验多轮修复样本的首轮坏解均已标记 loss=False
    multi_turn_count = 0
    unmasked_bad_turn = 0
    with open(retrain_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            msgs = rec.get("messages", [])
            assts = [m for m in msgs if m.get("role") == "assistant"]
            if len(assts) >= 2 and rec.get("last_assistant_only"):
                multi_turn_count += 1
                if assts[0].get("loss", True) is not False:
                    unmasked_bad_turn += 1
    assert multi_turn_count > 0, "[FATAL] 重训语料中未检测到多轮修复样本"
    assert unmasked_bad_turn == 0, f"[FATAL] 发现 {unmasked_bad_turn} 条多轮修复样本首轮坏解未标记 loss=False"
    print(f"[preflight] 语料审计通过：多轮修复样本 {multi_turn_count} 条，坏解轮 loss=False 掩码率 100%")


def ensure_lf_shell_script(sh_path: Path):
    """确保上传 Linux 的 .sh 脚本严格使用 LF 换行符，防止 bash $'\\r' 报错。"""
    raw = sh_path.read_bytes()
    if b"\r\n" in raw:
        sh_path.write_bytes(raw.replace(b"\r\n", b"\n"))


def make_tarball():
    missing = [src for src, _ in BUNDLE_FILES if not (ROOT / src).exists()]
    if missing:
        raise SystemExit(f"[FATAL] bundle 缺文件: {missing}")
    ensure_lf_shell_script(ROOT / "cloud_train_pack/run_impeller_fix.sh")
    preflight_audit()
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        for src, arc in BUNDLE_FILES:
            tar.add(ROOT / src, arcname=arc)
        bdir = ROOT / BENCHMARK_DIR
        for f in sorted(bdir.glob("*.jsonl")):
            tar.add(f, arcname=f"{BENCHMARK_DIR}/{f.name}")
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        names = tar.getnames()
    need = {
        "train_turnkey.py",
        "train_turnkey_impeller.py",
        "run_impeller_fix.sh",
        "dataset/virtu_impeller_fix_sft.jsonl",
        "dataset/virtu_impeller_repairloop_sft.jsonl",
        "dataset/virtu_impeller_hardened_sft.jsonl",
        "dataset/virtu_impeller_retrain_sft.jsonl",
        "virtu_eval/contamination_check.py",
        "scripts/corpus_unit_audit.py",
    }
    assert need.issubset(set(names)), f"bundle 不完整: {need - set(names)}"
    assert any(n.startswith(BENCHMARK_DIR) for n in names), "bundle 缺 benchmark"
    print(f"[pack] {ARCHIVE.name} {os.path.getsize(ARCHIVE)/1024/1024:.2f} MB, {len(names)} 件, 完整性自检 PASS")
    return names


def connect(creds):
    if paramiko is None:
        raise SystemExit("[FATAL] 缺少 paramiko 库，无法建立 SSH 连接")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=creds["host"], port=int(creds["port"]), username=creds["user"],
                   password=creds["password"], look_for_keys=False, allow_agent=False, timeout=30)
    print(f"[ssh] 连接 {creds['user']}@{creds['host']} (port={creds['port']}) 成功")
    return client


def run_cmd(client, cmd):
    _, out, err = client.exec_command(cmd)
    rc = out.channel.recv_exit_status()
    return rc, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def upload_start(client):
    run_cmd(client, f"mkdir -p {REMOTE_DIR}")
    sftp = client.open_sftp()
    sftp.put(str(ARCHIVE), f"{REMOTE_DIR}/virtu_impeller_fix_bundle.tar.gz")
    sftp.close()
    rc, out, err = run_cmd(client, f"cd {REMOTE_DIR} && tar -zxf virtu_impeller_fix_bundle.tar.gz && sed -i 's/\\r$//' run_impeller_fix.sh && chmod +x run_impeller_fix.sh")
    if rc != 0:
        raise SystemExit(f"[FATAL] 解包失败 rc={rc}: {err[-500:]}")
    run_cmd(client, f"cd {REMOTE_DIR} && : > train.log && nohup bash run_impeller_fix.sh > train.log 2>&1 &")
    print("[train] 云端后台训练已启动")


def monitor_fetch(client, max_wait_s=7200):
    t0 = time.time()
    last = ""
    while time.time() - t0 < max_wait_s:
        rc, out, _ = run_cmd(client, f"tail -n 6 {REMOTE_DIR}/train.log 2>/dev/null")
        if out and out != last:
            print(out.rstrip()[-600:])
            last = out
        for rel in (DELIVER_REL, DELIVER_REL_FALLBACK):
            rc, deliv, _ = run_cmd(client, f"ls {REMOTE_DIR}/{rel} 2>/dev/null")
            if rc == 0 and deliv.strip():
                print(f"[train] 检测到交付件 ({rel})，开始回收")
                LOCAL_OUT.mkdir(parents=True, exist_ok=True)
                sftp = client.open_sftp()
                local_fix2 = LOCAL_OUT / "virtu_impeller_fix2_lora_deliverable.tar.gz"
                local_fix1 = LOCAL_OUT / "virtu_impeller_fix_lora_deliverable.tar.gz"
                sftp.get(f"{REMOTE_DIR}/{rel}", str(local_fix2))
                sftp.close()
                shutil.copy2(local_fix2, local_fix1)
                print(f"[fetch] 已回收 {local_fix2} 并同步至 {local_fix1} ({os.path.getsize(local_fix2)/1024/1024:.2f} MB)")
                return local_fix2
        rc, fatal, _ = run_cmd(client, f"grep -E '\\[FATAL\\]|Traceback' {REMOTE_DIR}/train.log 2>/dev/null | head -3")
        if fatal.strip():
            rc3, tail, _ = run_cmd(client, f"tail -n 40 {REMOTE_DIR}/train.log")
            raise SystemExit(f"[FATAL] 训练日志出现致命错误:\n{tail}")
        rc, alive, _ = run_cmd(client, "pgrep -f '[r]un_impeller_fix.sh|[t]rain_turnkey_impeller' || true")
        if not alive.strip() and time.time() - t0 > 120:
            rc3, tail, _ = run_cmd(client, f"tail -n 40 {REMOTE_DIR}/train.log")
            raise SystemExit(f"[FATAL] 训练脚本已退出且无交付件:\n{tail}")
        time.sleep(30)
    raise SystemExit("[FATAL] 监控超时")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack-only", action="store_true", help="零网络自检打包完整性")
    ap.add_argument("--creds-file", default=str(CREDS))
    ap.add_argument("--max-wait", type=int, default=7200)
    ap.add_argument("--auto-deploy", action="store_true", help="回收后自动执行本地合并、GGUF 转换与 Ollama 注册")
    args = ap.parse_args()
    make_tarball()
    if args.pack_only:
        return
    cf = Path(args.creds_file)
    if not cf.exists():
        raise SystemExit(f"[FATAL] 无凭证文件 {cf}。租用云端 GPU 后写入 {{host,port,user,password}} JSON。")
    creds = json.loads(cf.read_text(encoding="utf-8"))
    client = connect(creds)
    try:
        upload_start(client)
        local = monitor_fetch(client, args.max_wait)
        print(f"[DONE] 交付件: {local}")
    finally:
        client.close()
    if args.auto_deploy:
        py = str(ROOT / ".venv" / "Scripts" / "python.exe")
        subprocess.run([py, str(ROOT / "scripts" / "post_training_deploy_impeller.py"), "--deliverable", str(local)], check=True)


if __name__ == "__main__":
    main()
