#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloud_train_pack/local_one_click_worldmodel.py — Virtu 世界工程模型（World Engineering Model）本地一键打包、云端开训与产物回收闭环脚本

核心能力：
  1. 自包含打包（--pack-only）：
     - 自动校验（或生成）cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl 与溯源账本；
     - 强制将 run_worldmodel_fix.sh 转换为 Unix LF 换行符，杜绝 Linux 端 `\\r` 报错；
     - 将训练器、六步启动脚本、修复语料、三大评测集（供云端开训前 assert_no_leak 门禁校验）、
       以及物理定律/契约核验模块打包进独立的 `cloud_train_pack/virtu_worldmodel_fix_bundle.tar.gz`；
     - 校验归档完整性并生成 `.sha256` 指纹文件。
  2. 云端 SSH 自动化（提供 --host / --port / --password 时）：
     - SFTP 上传归档包 -> 解压 -> 后台启动 `nohup bash run_worldmodel_fix.sh`；
     - 实时流式跟踪 `train_wm.log`；
     - 训练完成后自动拉回 `virtu_wm_lora_deliverable.tar.gz`，核验 SHA256 并解压至 `checkpoints/virtu_wm_lora_fix`；
     - 支持 `--auto-deploy` 一键衔接 `scripts/_post_train_worldmodel.py` 完成合并、量化、注册与评测。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT, os.path.join(ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BUNDLE_PATH = os.path.join(HERE, "virtu_worldmodel_fix_bundle.tar.gz")
DATA_REL = "dataset/virtu_worldmodel_fix_sft.jsonl"
LEDGER_REL = "dataset/virtu_worldmodel_fix_sft_ledger.json"

REQUIRED_ARCHIVE_MEMBERS = [
    "train_turnkey_worldmodel.py",
    "run_worldmodel_fix.sh",
    DATA_REL,
    LEDGER_REL,
    "dataset/virtu_impeller_repairloop_sft.jsonl",
    "dataset/virtu_impeller_repairloop_ledger.json",
    "dataset/virtu_wm_repairloop_sft.jsonl",
    "dataset/virtu_wm_repairloop_sft_ledger.json",
    "virtu_eval/contamination_check.py",
    "scripts/corpus_unit_audit.py",
    "scripts/wm_contract.py",
    "scripts/wm_schema.py",
    "scripts/wm_verifier.py",
    "scripts/train_world_model_final.py",
    "scripts/distill_local_solver.py",
]


def safe_extract(tar: tarfile.TarFile, dest: str) -> None:
    """解包交付件：拒绝绝对路径/父目录穿越（tar.extractall 默认不设防）。"""
    dest_abs = os.path.abspath(dest)
    for member in tar.getmembers():
        target = os.path.abspath(os.path.join(dest, member.name))
        if not target.startswith(dest_abs + os.sep) and target != dest_abs:
            raise RuntimeError(f"[FATAL] 交付包含路径穿越成员: {member.name}")
        if member.issym() or member.islnk():
            raise RuntimeError(f"[FATAL] 交付包含链接成员，拒绝解包: {member.name}")
    tar.extractall(dest)


def verify_deliverable_receipt(local_dir: str) -> dict:
    """部署前硬闸：回执必须 COMPLETED（预算停机/失败不得静默部署）且指纹齐全。"""
    receipt_file = os.path.join(local_dir, "virtu_wm_lora_adapter", "training_receipt.json")
    if not os.path.exists(receipt_file):
        raise RuntimeError("[FATAL] 交付件缺少 training_receipt.json，拒绝部署。")
    with open(receipt_file, "r", encoding="utf-8") as rf:
        receipt = json.load(rf)
    status = receipt.get("status")
    if status != "COMPLETED":
        raise RuntimeError(
            f"[FATAL] 训练回执状态={status}（非 COMPLETED）。"
            "半程/预算停机权重不得部署；请检查云端日志后决定是否重训。"
        )
    if not receipt.get("adapter_sha256") or not receipt.get("dataset_sha256"):
        raise RuntimeError("[FATAL] 回执缺少权重/语料指纹，无法归因，拒绝部署。")
    return receipt


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def ensure_lf_file(path: str) -> None:
    with open(path, "rb") as f:
        raw = f.read()
    fixed = raw.replace(b"\r\n", b"\n")
    if fixed != raw:
        with open(path, "wb") as f:
            f.write(fixed)


def ensure_corpus_built() -> tuple[str, str]:
    data_path = os.path.join(HERE, DATA_REL)
    ledger_path = os.path.join(HERE, LEDGER_REL)
    if not os.path.exists(data_path) or not os.path.exists(ledger_path):
        print("[Prep] 未检测到云端修复语料，正在调用 build_wm_cloud_fix_corpus.py 构建 ...")
        from scripts.build_wm_cloud_fix_corpus import build_corpus
        build_corpus(out_path=data_path, ledger_path=ledger_path)
    return data_path, ledger_path


def make_worldmodel_bundle(bundle_path: str = BUNDLE_PATH) -> dict:
    data_path, ledger_path = ensure_corpus_built()
    sh_path = os.path.join(HERE, "run_worldmodel_fix.sh")
    ensure_lf_file(sh_path)

    with open(ledger_path, "r", encoding="utf-8") as lf:
        ledger = json.load(lf)
    actual_sha = sha256_file(data_path)
    if ledger.get("output_sha256") != actual_sha:
        raise RuntimeError(
            f"[FATAL] 语料指纹与账本不一致: ledger={ledger.get('output_sha256')} actual={actual_sha}"
        )

    print(f"\n[1/5] 正在构建自包含世界工程模型云端修复包 -> {bundle_path} ...")
    file_map = {
        os.path.join(HERE, "train_turnkey_worldmodel.py"): "train_turnkey_worldmodel.py",
        sh_path: "run_worldmodel_fix.sh",
        data_path: DATA_REL,
        ledger_path: LEDGER_REL,
        os.path.join(HERE, "dataset", "virtu_impeller_repairloop_sft.jsonl"):
            "dataset/virtu_impeller_repairloop_sft.jsonl",
        os.path.join(HERE, "dataset", "virtu_impeller_repairloop_ledger.json"):
            "dataset/virtu_impeller_repairloop_ledger.json",
        os.path.join(HERE, "dataset", "virtu_wm_repairloop_sft.jsonl"):
            "dataset/virtu_wm_repairloop_sft.jsonl",
        os.path.join(HERE, "dataset", "virtu_wm_repairloop_sft_ledger.json"):
            "dataset/virtu_wm_repairloop_sft_ledger.json",
        os.path.join(ROOT, "virtu_eval", "__init__.py"): "virtu_eval/__init__.py",
        os.path.join(ROOT, "virtu_eval", "contamination_check.py"): "virtu_eval/contamination_check.py",
        os.path.join(ROOT, "scripts", "corpus_unit_audit.py"): "scripts/corpus_unit_audit.py",
        os.path.join(ROOT, "scripts", "wm_contract.py"): "scripts/wm_contract.py",
        os.path.join(ROOT, "scripts", "wm_schema.py"): "scripts/wm_schema.py",
        os.path.join(ROOT, "scripts", "wm_verifier.py"): "scripts/wm_verifier.py",
        os.path.join(ROOT, "scripts", "train_world_model_final.py"): "scripts/train_world_model_final.py",
        os.path.join(ROOT, "scripts", "distill_local_solver.py"): "scripts/distill_local_solver.py",
    }

    for suite in ("virtu_eval_v1", "virtu_eval_phys_v1", "virtu_eval_cl_v1"):
        suite_dir = os.path.join(ROOT, "data", "benchmark", suite)
        if os.path.isdir(suite_dir):
            for jf in sorted(glob.glob(os.path.join(suite_dir, "*.jsonl"))):
                rel = f"data/benchmark/{suite}/{os.path.basename(jf)}"
                file_map[jf] = rel

    os.makedirs(os.path.dirname(os.path.abspath(bundle_path)), exist_ok=True)
    with tarfile.open(bundle_path, "w:gz") as tar:
        for src, arc in file_map.items():
            if not os.path.exists(src):
                if arc.endswith("__init__.py"):
                    info = tarfile.TarInfo(name=arc)
                    info.size = 0
                    tar.addfile(info, io.BytesIO(b""))
                    continue
                raise FileNotFoundError(f"打包缺失依赖文件: {src} -> {arc}")
            tar.add(src, arcname=arc)

    # 校验归档完整性与 LF 换行符
    with tarfile.open(bundle_path, "r:gz") as tar:
        names = set(tar.getnames())
        missing = [m for m in REQUIRED_ARCHIVE_MEMBERS if m not in names]
        if missing:
            raise RuntimeError(f"[FATAL] 归档缺失关键成员: {missing}")
        sh_bytes = tar.extractfile("run_worldmodel_fix.sh").read()
        if b"\r\n" in sh_bytes:
            raise RuntimeError("[FATAL] run_worldmodel_fix.sh 含 CRLF，拒绝打包！")

    bundle_sha = sha256_file(bundle_path)
    with open(bundle_path + ".sha256", "w", encoding="utf-8", newline="\n") as sf:
        sf.write(f"{bundle_sha}  {os.path.basename(bundle_path)}\n")

    sz_mb = os.path.getsize(bundle_path) / (1024**2)
    summary = {
        "bundle_path": bundle_path,
        "bundle_sha256": bundle_sha,
        "bundle_size_mb": round(sz_mb, 2),
        "member_count": len(file_map),
        "dataset_rows": ledger.get("kept_rows"),
        "dataset_sha256": actual_sha,
        "masked_bad_assistant_turns": ledger.get("masked_bad_assistant_turns"),
    }
    print(f"  -> 打包与校验完成！大小: {sz_mb:.2f} MB | 成员数: {len(file_map)}")
    print(f"  -> 归档 SHA256: {bundle_sha}")
    print(f"  -> 语料行数: {ledger.get('kept_rows')} (屏蔽错误草稿轮: {ledger.get('masked_bad_assistant_turns')})")
    return summary


def _load_paramiko():
    try:
        import paramiko
        return paramiko
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        import paramiko
        return paramiko


def connect_ssh(host: str, port: int, user: str, password: str):
    paramiko = _load_paramiko()
    print(f"\n[2/5] 连接云端 GPU 实例 ({user}@{host}:{port}) ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=password, timeout=30)
    print("  -> SSH 连接成功！")
    return client


def upload_and_start(client, remote_work_dir: str = "/root/virtu_wm_train", extra_args: str = ""):
    print(f"\n[3/5] 上传世界工程模型修复包至 {remote_work_dir} ...")
    stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_work_dir}")
    stdout.channel.recv_exit_status()

    sftp = client.open_sftp()
    remote_tar = f"{remote_work_dir}/virtu_worldmodel_fix_bundle.tar.gz"
    sftp.put(BUNDLE_PATH, remote_tar)
    sftp.close()

    cmd_unpack = (
        f"cd {remote_work_dir} && tar -zxvf virtu_worldmodel_fix_bundle.tar.gz "
        f"&& chmod +x run_worldmodel_fix.sh"
    )
    stdin, stdout, stderr = client.exec_command(cmd_unpack)
    if stdout.channel.recv_exit_status() != 0:
        err = stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"远端解压失败: {err}")

    print("\n[4/5] 启动云端后台修复微调进程 (nohup bash run_worldmodel_fix.sh) ...")
    cmd_start = (
        f"cd {remote_work_dir} && touch train_wm.log && "
        f"nohup bash run_worldmodel_fix.sh {extra_args} > train_wm.log 2>&1 & "
        f"echo LAUNCHED_PID=$!"
    )
    _, l_out, _ = client.exec_command(cmd_start)
    launch_out = l_out.read().decode("utf-8", errors="replace")
    print("  ->", launch_out.strip())
    time.sleep(8)
    # 启动后必须证明进程真活着（后台启动的退出码会撒谎）
    _, p_out, _ = client.exec_command(
        f"pgrep -f 'run_worldmodel_fix.sh|train_turnkey_worldmodel.py' || true; "
        f"head -n 30 {remote_work_dir}/train_wm.log"
    )
    probe = p_out.read().decode("utf-8", errors="replace")
    if "[FATAL]" in probe:
        raise RuntimeError(f"[FATAL] 云端启动即失败，日志头部:\n{probe}")
    if not any(line.strip().isdigit() for line in probe.splitlines()):
        raise RuntimeError(
            f"[FATAL] 启动 8 秒后未找到训练进程，拒绝假启动。日志头部:\n{probe}"
        )
    print("  -> 进程存活探针通过。")


def stream_logs(client, remote_work_dir: str = "/root/virtu_wm_train"):
    print("\n[5/5] 实时流式监控云端训练日志 (Ctrl+C 可安全断开本地监控) ...")
    print("=" * 70)
    stdin, stdout, stderr = client.exec_command(f"tail -F -n 40 {remote_work_dir}/train_wm.log")
    try:
        idle_ticks = 0
        while not stdout.channel.closed:
            line = stdout.readline()
            if line:
                idle_ticks = 0
                print(line, end="", flush=True)
                if "世界工程模型云端修复训练完成" in line or "世界工程模型修复训练完成" in line:
                    print("\n[SUCCESS] 检测到云端训练完成信号！")
                    break
                if "[FATAL]" in line:
                    print("\n[ALERT] 云端门禁或训练报出 FATAL 错误，请检查日志！")
                    break
            else:
                time.sleep(1)
                idle_ticks += 1
                if idle_ticks % 10 == 0:
                    _, p_out, _ = client.exec_command("pgrep -f train_turnkey_worldmodel.py || true")
                    if not p_out.read().decode().strip() and idle_ticks > 20:
                        break
    except KeyboardInterrupt:
        print("\n[INFO] 已断开本地日志流，云端训练仍在后台继续。")


def fetch_deliverable(
    client,
    remote_work_dir: str = "/root/virtu_wm_train",
    auto_deploy: bool = False,
):
    remote_tar = f"{remote_work_dir}/output/virtu_wm_lora_fix/virtu_wm_lora_deliverable.tar.gz"
    remote_sha = remote_tar + ".sha256"
    local_dir = os.path.join(ROOT, "checkpoints", "virtu_wm_lora_fix")
    os.makedirs(local_dir, exist_ok=True)
    local_tar = os.path.join(local_dir, "virtu_wm_lora_deliverable.tar.gz")

    print(f"\n[Fetch] 正在拉取世界工程模型 LoRA 交付包 -> {local_tar} ...")
    # 预检远端回执：非 COMPLETED 不拉半成品（预算停机/失败先暴露）
    _, r_out, _ = client.exec_command(
        f"cat {remote_work_dir}/output/virtu_wm_lora_fix/final_adapter/training_receipt.json 2>/dev/null"
    )
    try:
        remote_receipt = json.loads(r_out.read().decode("utf-8", errors="replace"))
    except Exception:
        raise RuntimeError(
            "[FATAL] 远端无有效 training_receipt.json —— 训练未完成或已失败，拒绝拉取。"
        )
    if remote_receipt.get("status") != "COMPLETED":
        raise RuntimeError(
            f"[FATAL] 远端回执状态={remote_receipt.get('status')}（非 COMPLETED），拒绝拉取部署。"
        )

    sftp = client.open_sftp()
    try:
        sftp.stat(remote_tar)
        sftp.get(remote_tar, local_tar)
        try:
            sftp.get(remote_sha, local_tar + ".sha256")
        except Exception:
            raise RuntimeError("[FATAL] 远端缺少交付件 .sha256，无法校验完整性，拒绝部署。")
    finally:
        sftp.close()

    # 硬校验：sha256 必须逐字节一致（旧版从不校验，等于闸门空转）
    expected = open(local_tar + ".sha256", "r", encoding="utf-8").read().split()[0]
    actual = sha256_file(local_tar)
    if expected != actual:
        raise RuntimeError(
            f"[FATAL] 交付件 sha256 不一致: expected={expected[:16]} actual={actual[:16]}，传输损坏。"
        )
    print(f"[Fetch] SHA256 校验通过: {actual[:16]}...")

    with tarfile.open(local_tar, "r:gz") as tar:
        safe_extract(tar, local_dir)

    receipt = verify_deliverable_receipt(local_dir)
    print("\n" + "=" * 70)
    print("世界工程模型训练收据 (Training Receipt):")
    print(f"  * 基座模型   : {receipt.get('base_model')}")
    print(f"  * 训练样本数 : {receipt.get('train_rows')} (评估集: {receipt.get('eval_rows')})")
    print(f"  * 最终 Loss  : train={receipt.get('train_loss')} | eval={receipt.get('eval_loss')}")
    print(f"  * 语料 SHA256: {str(receipt.get('dataset_sha256'))[:16]}...")
    print(f"  * 权重 SHA256: {str(receipt.get('adapter_sha256'))[:16]}...")
    print("=" * 70)

    if auto_deploy:
        post_script = os.path.join(ROOT, "scripts", "_post_train_worldmodel.py")
        print(f"\n[Deploy] 触发训后合并、GGUF 量化与评测流水线: {post_script}")
        subprocess.check_call([sys.executable, post_script])


def main() -> int:
    parser = argparse.ArgumentParser(description="Virtu 世界工程模型本地一键打包与云端训练编排器")
    parser.add_argument("--host", default=os.environ.get("DAMODEL_HOST", ""))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DAMODEL_PORT", "22")))
    parser.add_argument("--user", default=os.environ.get("DAMODEL_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("DAMODEL_PASS", ""))
    parser.add_argument("--remote-dir", default="/root/virtu_wm_train")
    parser.add_argument("--pack-only", action="store_true", help="仅构建并核验自包含云端修复归档包，不连接 SSH")
    parser.add_argument("--fetch-only", action="store_true", help="跳过上传开训，直接拉取云端产物")
    parser.add_argument("--auto-deploy", action="store_true", help="拉回产物后自动执行 _post_train_worldmodel.py")
    args = parser.parse_args()

    make_worldmodel_bundle(BUNDLE_PATH)
    if args.pack_only:
        print("\n[OK] --pack-only 自包含云端修复归档包构建并核验通过。")
        return 0

    if not args.host or not args.password:
        raise SystemExit(
            "[FATAL] 未提供 SSH 连接参数 (--host / --password)。若仅需本地打包验证请加 `--pack-only`。"
        )

    client = connect_ssh(args.host, args.port, args.user, args.password)
    try:
        if not args.fetch_only:
            upload_and_start(client, args.remote_dir)
            stream_logs(client, args.remote_dir)
        fetch_deliverable(client, args.remote_dir, auto_deploy=args.auto_deploy)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
