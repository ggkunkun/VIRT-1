#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/local_one_click.py — Virtu 8.2B 主力模型本地一键打包、云端开训、流式监控与产物回收闭环脚本 (v2)

用法：
  python cloud_train_pack/local_one_click.py --host cn-north-b.ssh.damodel.com --port 40526 --user root --password <PASSWORD>
  python cloud_train_pack/local_one_click.py --pack-only
  python cloud_train_pack/local_one_click.py --selftest
"""

import io
import os
import sys
import json
import time
import glob
import shlex
import shutil
import hashlib
import tarfile
import argparse
import tempfile
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(ROOT, "cloud_train_pack")
ARCHIVE_PATH = os.path.join(ROOT, "cloud_train_pack.tar.gz")
BENCHMARK_SUBDIRS = ("virtu_eval_v1", "virtu_eval_phys_v1", "virtu_eval_cl_v1")

try:
    from cloud_train_pack.start_train_now import find_active_fatal_marker
except ImportError:
    from start_train_now import find_active_fatal_marker


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def resolve_primary_dataset(dataset_arg: str = None) -> str:
    if dataset_arg:
        cand = dataset_arg if os.path.isabs(dataset_arg) else os.path.join(ROOT, dataset_arg)
        if not os.path.exists(cand):
            cand_pack = os.path.join(PACK_DIR, dataset_arg)
            if os.path.exists(cand_pack):
                cand = cand_pack
            else:
                raise SystemExit(f"[FATAL] 指定数据集不存在，拒绝静默回退: {dataset_arg}")
        return cand

    for name in (
        "virtu_master_sft.jsonl",
        "virtu_capability_sft_v5.jsonl",
        "virtu_v100_production_sft.jsonl",
        "virtu_gold_production_sft.jsonl",
    ):
        p = os.path.join(PACK_DIR, "dataset", name)
        if os.path.exists(p):
            return p
    raise SystemExit("[FATAL] 未在 cloud_train_pack/dataset 找到可用主力 SFT 语料")


def _add_bytes_to_tar(tar: tarfile.TarFile, arcname: str, data: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = mode
    info.mtime = int(time.time())
    tar.addfile(info, io.BytesIO(data))


def make_tarball(archive_path: str = ARCHIVE_PATH, dataset_arg: str = None):
    """打包云端最小自包含训练套件，写入 .sha256 伴随校验文件。"""
    print(f"\n[1/5] 打包自包含硬门禁开训套件 -> {archive_path} ...")
    required_files = [
        (os.path.join(PACK_DIR, "train_turnkey.py"), "train_turnkey.py"),
        (os.path.join(ROOT, "virtu_eval", "__init__.py"), "virtu_eval/__init__.py"),
        (os.path.join(ROOT, "virtu_eval", "contamination_check.py"), "virtu_eval/contamination_check.py"),
        (os.path.join(ROOT, "scripts", "corpus_unit_audit.py"), "scripts/corpus_unit_audit.py"),
    ]
    for src, _ in required_files:
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] 打包缺少必需门禁依赖文件: {src}")

    run_sh_src = os.path.join(PACK_DIR, "run.sh")
    if not os.path.exists(run_sh_src):
        raise SystemExit(f"[FATAL] 缺少云端编排脚本: {run_sh_src}")
    with open(run_sh_src, "rb") as rf:
        run_sh_bytes = rf.read().replace(b"\r\n", b"\n")

    dataset_path = resolve_primary_dataset(dataset_arg)
    dataset_name = os.path.basename(dataset_path)
    dataset_sha = sha256_file(dataset_path)

    # 若仓库已带对应 ledger 则强校 SHA256；否则为包内生成一个锁定当下 SHA256 的 ledger
    disk_ledger = os.path.join(os.path.dirname(dataset_path), "dataset_ledger.json")
    bundle_ledger = {
        "output_path": f"dataset/{dataset_name}",
        "output_sha256": dataset_sha,
        "files": {dataset_name: {"sha256": dataset_sha, "size_bytes": os.path.getsize(dataset_path)}},
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if os.path.exists(disk_ledger):
        with open(disk_ledger, "r", encoding="utf-8") as lf:
            existing = json.load(lf)
        exp = None
        if isinstance(existing.get("files"), dict) and dataset_name in existing["files"]:
            entry = existing["files"][dataset_name]
            exp = entry.get("sha256") if isinstance(entry, dict) else entry
        elif os.path.basename(str(existing.get("output_path") or existing.get("dataset") or "")) == dataset_name:
            exp = existing.get("output_sha256") or existing.get("sha256")
        if exp and exp.lower() != dataset_sha.lower():
            raise SystemExit(
                f"[FATAL] 语料与本地 ledger SHA256 不一致 ({disk_ledger})! expected={exp[:16]} actual={dataset_sha[:16]}"
            )

    bench_files = []
    for sub in BENCHMARK_SUBDIRS:
        sub_dir = os.path.join(ROOT, "data", "benchmark", sub)
        if not os.path.isdir(sub_dir):
            raise SystemExit(f"[FATAL] 打包缺少防污染评测基准目录: {sub_dir}")
        for fp in sorted(glob.glob(os.path.join(sub_dir, "*.jsonl"))):
            rel = os.path.relpath(fp, ROOT).replace("\\", "/")
            bench_files.append((fp, rel))

    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for src, arcname in required_files:
            tar.add(src, arcname=arcname)
        _add_bytes_to_tar(tar, "run.sh", run_sh_bytes, mode=0o755)
        tar.add(dataset_path, arcname=f"dataset/{dataset_name}")
        _add_bytes_to_tar(
            tar,
            "dataset/dataset_ledger.json",
            json.dumps(bundle_ledger, ensure_ascii=False, indent=2).encode("utf-8"),
            mode=0o644,
        )
        for src, rel in bench_files:
            tar.add(src, arcname=rel)

    tar_sha = sha256_file(archive_path)
    with open(archive_path + ".sha256", "w", encoding="utf-8", newline="\n") as sf:
        sf.write(f"{tar_sha}  {os.path.basename(archive_path)}\n")

    sz_mb = os.path.getsize(archive_path) / (1024**2)
    print(f"  -> 打包完成: {sz_mb:.2f} MB | sha256={tar_sha[:16]}... | 语料={dataset_name} ({len(bench_files)} 个防污染基准文件)")
    return archive_path, tar_sha


make_master_bundle = make_tarball


def safe_extract(tar: tarfile.TarFile, dest_dir: str) -> list:
    """安全解包：拒绝绝对路径、.. 路径穿越、软硬链接及设备节点。"""
    dest_real = os.path.realpath(dest_dir)
    os.makedirs(dest_real, exist_ok=True)
    safe_members = []
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"[SECURITY] 拒绝解压链接条目: {member.name}")
        if member.isdev() or member.isfifo() or member.ischr() or member.isblk():
            raise ValueError(f"[SECURITY] 拒绝解压特殊设备条目: {member.name}")
        norm_name = member.name.replace("\\", "/")
        if os.path.isabs(norm_name) or norm_name.startswith("/") or (len(norm_name) > 1 and norm_name[1] == ":"):
            raise ValueError(f"[SECURITY] 拒绝绝对路径条目: {member.name}")
        target_real = os.path.realpath(os.path.join(dest_real, member.name))
        if target_real != dest_real and not target_real.startswith(dest_real + os.sep):
            raise ValueError(f"[SECURITY] 拒绝路径穿越条目: {member.name} -> {target_real}")
        safe_members.append(member)

    for member in safe_members:
        target_real = os.path.realpath(os.path.join(dest_real, member.name))
        if member.isdir():
            os.makedirs(target_real, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target_real), exist_ok=True)
            src_f = tar.extractfile(member)
            if src_f is None:
                continue
            with src_f, open(target_real, "wb") as out_f:
                shutil.copyfileobj(src_f, out_f)
    return safe_members


def verify_deliverable_receipt(unpack_dir: str) -> dict:
    """验证交付解包收据：必须 status=COMPLETED、含 adapter_sha256/dataset_sha256 且与磁盘权重一致。"""
    candidates = [
        os.path.join(unpack_dir, "virtu_lora_adapter", "training_receipt.json"),
        os.path.join(unpack_dir, "training_receipt.json"),
    ]
    receipt_path = next((p for p in candidates if os.path.exists(p)), None)
    if not receipt_path:
        raise RuntimeError(f"[FATAL] 解包目录缺少 training_receipt.json: {unpack_dir}")

    with open(receipt_path, "r", encoding="utf-8") as f:
        rdata = json.load(f)

    status = rdata.get("status")
    if status != "COMPLETED":
        raise RuntimeError(f"[FATAL] 交付状态非 COMPLETED (status={status!r})，拒绝验收与上线！")

    adapter_sha = str(rdata.get("adapter_sha256", "")).strip()
    dataset_sha = str(rdata.get("dataset_sha256", "")).strip()
    if len(adapter_sha) != 64 or len(dataset_sha) != 64:
        raise RuntimeError("[FATAL] training_receipt.json 缺少有效的 64 位 SHA256 凭证")

    if "instruct" in str(rdata.get("base_model", "")).lower():
        raise RuntimeError(f"[FATAL] 交付基座非法包含 Instruct: {rdata.get('base_model')}")

    adapter_dir = os.path.dirname(receipt_path)
    safetensor_file = os.path.join(adapter_dir, "adapter_model.safetensors")
    if not os.path.exists(safetensor_file):
        raise RuntimeError(f"[FATAL] 缺少适配器权重文件: {safetensor_file}")
    actual_adapter_sha = sha256_file(safetensor_file)
    if actual_adapter_sha.lower() != adapter_sha.lower():
        raise RuntimeError(
            f"[FATAL] adapter_model.safetensors SHA256 不匹配! receipt={adapter_sha[:16]} actual={actual_adapter_sha[:16]}"
        )
    return rdata


def _ensure_paramiko():
    try:
        import paramiko
        return paramiko
    except ImportError as e:
        raise SystemExit(f"[FATAL] 缺少 paramiko 依赖，请执行 `.venv\\Scripts\\python.exe -m pip install paramiko`: {e}")


def connect_ssh(host: str, port: int, user: str, password: str):
    paramiko = _ensure_paramiko()
    print(f"\n[2/5] 连接云端 GPU 实例 ({user}@{host}:{port}) ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=password, timeout=30)
    print("  -> SSH 连接成功！")
    return client


def _exec_checked(client, cmd: str, desc: str) -> str:
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if rc != 0:
        raise SystemExit(f"[FATAL] {desc} 失败 (rc={rc}):\n{out}\n{err}")
    return out


def upload_and_start(
    client,
    remote_work_dir: str = "/root/virtu_train",
    max_hours: float = 1.5,
    epochs: float = 2.0,
    lr: float = 1.5e-4,
    skip_smoke: bool = False,
    qlora: bool = False,
):
    print(f"\n[3/5] 上传训练套件与校验文件到 {remote_work_dir} ...")
    _exec_checked(client, f"mkdir -p {shlex.quote(remote_work_dir)}", "创建远端目录")

    sftp = client.open_sftp()
    remote_tar = f"{remote_work_dir}/cloud_train_pack.tar.gz"
    remote_sha = f"{remote_tar}.sha256"
    sftp.put(ARCHIVE_PATH, remote_tar)
    sftp.put(ARCHIVE_PATH + ".sha256", remote_sha)
    sftp.close()

    rdir_q = shlex.quote(remote_work_dir)
    _exec_checked(
        client,
        f"cd {rdir_q} && sed -i 's/\\r$//' cloud_train_pack.tar.gz.sha256 && sha256sum -c cloud_train_pack.tar.gz.sha256 && tar -zxf cloud_train_pack.tar.gz && sed -i 's/\\r$//' run.sh && chmod +x run.sh",
        "远端 SHA256 校验与解包",
    )

    run_flags = [f"--max-hours {shlex.quote(str(max_hours))}", f"--epochs {shlex.quote(str(epochs))}", f"--lr {shlex.quote(str(lr))}"]
    if skip_smoke:
        run_flags.append("--skip-smoke")
    if qlora:
        run_flags.append("--qlora")
    flags_str = " ".join(run_flags)

    print(f"\n[4/5] 启动云端 7 阶段训练 (bash run.sh {flags_str}) ...")
    start_out = _exec_checked(client, f"cd {rdir_q} && rm -f train_master.log && bash run.sh {flags_str}", "启动 run.sh")
    print(start_out.strip())

    # 8 秒看门狗存活探针 + [FATAL] 扫描
    time.sleep(8)
    _, p_out, _ = client.exec_command("pgrep -f 'run\\.sh|train_turnkey\\.py' || true")
    pids = p_out.read().decode("utf-8", errors="replace").strip()
    _, l_out, _ = client.exec_command(f"tail -n 60 {rdir_q}/train_master.log 2>/dev/null || true")
    log_tail = l_out.read().decode("utf-8", errors="replace")
    active_marker = find_active_fatal_marker(log_tail)
    if active_marker == "[FATAL]" or (active_marker and not pids):
        raise SystemExit(f"[FATAL] 启动 8s 后检测到致命异常({active_marker})！\n--- 远端日志尾部 ---\n{log_tail}")
    if not pids and "[Stage7] PASS" not in log_tail:
        raise SystemExit(f"[FATAL] 启动 8s 后训练进程未存活且未见完成信号！\n--- 远端日志尾部 ---\n{log_tail}")
    print(f"  -> 8s 存活探针通过 (PIDs: {pids.replace(chr(10), ',') or 'finished'})")


def stream_logs(client, remote_work_dir: str = "/root/virtu_train"):
    print("\n[5/5] 开始实时跟踪云端训练日志 (Ctrl+C 可安全断开，云端后台继续运行) ...")
    print("=" * 70)
    rdir_q = shlex.quote(remote_work_dir)
    _, stdout, _ = client.exec_command(f"tail -F -n 40 {rdir_q}/train_master.log")
    try:
        no_line_count = 0
        while not stdout.channel.closed:
            line = stdout.readline()
            if line:
                no_line_count = 0
                print(line, end="", flush=True)
                if "[Stage7] PASS" in line or "训练圆满完成" in line:
                    print("\n[SUCCESS] 检测到 Stage7 交付验证通过信号！")
                    break
                if "TIME_BUDGET_STOPPED" in line:
                    print("\n[ALERT] 训练触及时间预算停机 (TIME_BUDGET_STOPPED)！")
                    break
                if find_active_fatal_marker(line, markers=("[FATAL]",)):
                    print("\n[ALERT] 日志中出现 [FATAL]，请核查！")
            else:
                time.sleep(1)
                no_line_count += 1
                if no_line_count % 10 == 0:
                    _, p_out, _ = client.exec_command("pgrep -f 'run\\.sh|train_turnkey\\.py' || true")
                    pids = p_out.read().decode("utf-8", errors="replace").strip()
                    if not pids:
                        _, r_out, _ = client.exec_command(
                            f"cat {rdir_q}/output/virtu_lora_master/training_receipt.json 2>/dev/null || true"
                        )
                        rec_raw = r_out.read().decode("utf-8", errors="replace").strip()
                        if rec_raw:
                            print("\n[NOTICE] 云端进程已结束，已发现 training_receipt.json。")
                            break
                        if no_line_count > 30:
                            raise SystemExit("[FATAL] 云端进程已退出且未产出 training_receipt.json")
    except KeyboardInterrupt:
        print("\n[INFO] 本地监控已断开；云端训练仍在后台运行。")


def fetch_deliverable(
    client,
    remote_work_dir: str = "/root/virtu_train",
    auto_deploy: bool = False,
    deploy_tag: str = "virtu-master-fixed:latest",
    base_dir: str = None,
):
    rdir_q = shlex.quote(remote_work_dir)
    remote_out = f"{remote_work_dir}/output/virtu_lora_master"
    _, rec_out, _ = client.exec_command(f"cat {rdir_q}/output/virtu_lora_master/training_receipt.json 2>/dev/null || true")
    rec_text = rec_out.read().decode("utf-8", errors="replace").strip()
    if not rec_text:
        raise SystemExit(f"[FATAL] 远端缺少 training_receipt.json ({remote_out})")
    remote_rec = json.loads(rec_text)
    if remote_rec.get("status") != "COMPLETED":
        raise SystemExit(f"[FATAL] 远端训练未达到 COMPLETED (status={remote_rec.get('status')})，拒绝拉取假完成产物！")

    local_ckpt_dir = os.path.join(ROOT, "checkpoints")
    os.makedirs(local_ckpt_dir, exist_ok=True)
    local_tar = os.path.join(local_ckpt_dir, "virtu_master_lora_deliverable.tar.gz")
    local_sha = local_tar + ".sha256"

    sftp = client.open_sftp()
    try:
        sftp.get(f"{remote_out}/virtu_lora_deliverable.tar.gz", local_tar)
        sftp.get(f"{remote_out}/virtu_lora_deliverable.tar.gz.sha256", local_sha)
    finally:
        sftp.close()

    expected_tar_sha = open(local_sha, "r", encoding="utf-8").read().strip().split()[0]
    actual_tar_sha = sha256_file(local_tar)
    if expected_tar_sha.lower() != actual_tar_sha.lower():
        raise SystemExit(f"[FATAL] 交付包本地 SHA256 校验失败: expected={expected_tar_sha[:16]} actual={actual_tar_sha[:16]}")

    unpack_dir = os.path.join(local_ckpt_dir, "virtu_master_extract")
    if os.path.exists(unpack_dir):
        shutil.rmtree(unpack_dir)
    with tarfile.open(local_tar, "r:gz") as tar:
        safe_extract(tar, unpack_dir)

    rdata = verify_deliverable_receipt(unpack_dir)
    print("\n" + "=" * 70)
    print("📜 训练账本凭证 (已通过 SHA256 + 完整性校验):")
    print(f"  * 状态: {rdata.get('status')}")
    print(f"  * 基座模型: {rdata.get('base_model')}")
    print(f"  * 训练样本: {rdata.get('total_train_samples')} 条 | 最终 Loss: {rdata.get('final_train_loss')}")
    print(f"  * 语料指纹: {rdata.get('dataset_sha256', '')[:16]}...")
    print(f"  * 适配器指纹: {rdata.get('adapter_sha256', '')[:16]}...")
    print("=" * 70)

    if auto_deploy:
        deploy_script = os.path.join(PACK_DIR, "deploy_trained_adapter.py")
        cmd = [sys.executable, deploy_script, "--deliverable", local_tar, "--tag", deploy_tag]
        if base_dir:
            cmd.extend(["--base", base_dir])
        print(f"\n[AutoDeploy] 调用部署修复器: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    else:
        print(
            f"\n下一步可运行:\n  .venv\\Scripts\\python.exe cloud_train_pack/deploy_trained_adapter.py "
            f"--deliverable {local_tar} --tag {deploy_tag}"
        )


def run_selftest() -> int:
    """离线自检：make_tarball 完整性、LF/0o755 校验、safe_extract 防穿越/防链接、receipt 严格门禁。"""
    with tempfile.TemporaryDirectory(prefix="virtu_oneclick_selftest_") as td:
        # 1. make_tarball() 产物、伴随 .sha256、LF/0o755、门禁文件与基准数据
        test_tar = os.path.join(td, "test_pack.tar.gz")
        arc_path, tar_sha = make_tarball(archive_path=test_tar)
        assert os.path.exists(arc_path + ".sha256")
        recorded_sha = open(arc_path + ".sha256", "r", encoding="utf-8").read().strip().split()[0]
        assert recorded_sha == tar_sha

        with tarfile.open(arc_path, "r:gz") as tar:
            names = set(tar.getnames())
            for req in (
                "train_turnkey.py",
                "run.sh",
                "dataset/dataset_ledger.json",
                "virtu_eval/__init__.py",
                "virtu_eval/contamination_check.py",
                "scripts/corpus_unit_audit.py",
            ):
                assert req in names, f"tarball 缺少 {req}"
            assert any(n.startswith("data/benchmark/virtu_eval_v1/") for n in names)
            run_member = tar.getmember("run.sh")
            assert (run_member.mode & 0o111) != 0, f"run.sh 缺少可执行权限 mode={oct(run_member.mode)}"
            run_bytes = tar.extractfile(run_member).read()
            assert b"\r\n" not in run_bytes, "run.sh 包含 CRLF!"

        # 2. safe_extract 防路径穿越与防 symlink
        evil_tar = os.path.join(td, "evil.tar.gz")
        for label, builder in (
            ("traversal", lambda ti: setattr(ti, "name", "../escaped.txt")),
            ("symlink", lambda ti: (setattr(ti, "type", tarfile.SYMTYPE), setattr(ti, "linkname", "/etc/passwd"))),
        ):
            with tarfile.open(evil_tar, "w:gz") as tar:
                ti = tarfile.TarInfo(name="safe.txt")
                payload = b"evil"
                ti.size = len(payload)
                builder(ti)
                tar.addfile(ti, io.BytesIO(payload) if ti.isfile() else None)
            with tarfile.open(evil_tar, "r:gz") as tar:
                try:
                    safe_extract(tar, os.path.join(td, f"out_{label}"))
                    raise AssertionError(f"safe_extract 未拦截 {label}")
                except ValueError:
                    pass

        # 3. verify_deliverable_receipt 拦截 TIME_BUDGET_STOPPED / 篡改 SHA256，放行合格件
        unpack_ok = os.path.join(td, "unpack_ok")
        adapter_dir = os.path.join(unpack_ok, "virtu_lora_adapter")
        os.makedirs(adapter_dir, exist_ok=True)
        weight_path = os.path.join(adapter_dir, "adapter_model.safetensors")
        with open(weight_path, "wb") as wf:
            wf.write(b"fake-safetensors-payload")
        w_sha = sha256_file(weight_path)
        valid_rec = {
            "status": "COMPLETED",
            "base_model": "/root/models/Qwen3-8B",
            "adapter_sha256": w_sha,
            "dataset_sha256": "a" * 64,
        }
        rec_file = os.path.join(adapter_dir, "training_receipt.json")
        with open(rec_file, "w", encoding="utf-8") as rf:
            json.dump(valid_rec, rf)
        assert verify_deliverable_receipt(unpack_ok)["status"] == "COMPLETED"

        for bad_patch in ({"status": "TIME_BUDGET_STOPPED"}, {"adapter_sha256": "b" * 64}, {"base_model": "Qwen3-8B-Instruct"}):
            bad_rec = {**valid_rec, **bad_patch}
            with open(rec_file, "w", encoding="utf-8") as rf:
                json.dump(bad_rec, rf)
            try:
                verify_deliverable_receipt(unpack_ok)
                raise AssertionError(f"verify_deliverable_receipt 未拦截 {bad_patch}")
            except RuntimeError:
                pass

    print("[SELFTEST] PASS: make_tarball / LF+0755 / safe_extract / receipt_gate")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Virtu 8.2B 主力模型一键云端开训与回收")
    parser.add_argument("--host", default=os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DAMODEL_PORT", "40526")))
    parser.add_argument("--user", default=os.environ.get("DAMODEL_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("DAMODEL_PASS", ""))
    parser.add_argument("--remote-dir", default="/root/virtu_train", help="云端工作目录")
    parser.add_argument("--dataset", default=None, help="指定主训 JSONL 数据集路径")
    parser.add_argument("--max-hours", type=float, default=1.5)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=1.5e-4)
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--fetch-only", action="store_true", help="跳过开训，直接拉取远端结果")
    parser.add_argument("--pack-only", action="store_true", help="仅打包套件并验证完整性，不连接 SSH")
    parser.add_argument("--auto-deploy", action="store_true", help="拉取完成后自动运行 deploy_trained_adapter.py")
    parser.add_argument("--deploy-tag", default="virtu-master-fixed:latest", help="--auto-deploy 目标 Ollama 标签")
    parser.add_argument("--base", default=None, help="本地 GGUF 合并使用的基座路径")
    parser.add_argument("--selftest", action="store_true", help="运行零 SSH 离线自检")
    args = parser.parse_args()

    if args.selftest:
        raise SystemExit(run_selftest())

    if not args.fetch_only:
        make_tarball(ARCHIVE_PATH, dataset_arg=args.dataset)

    if args.pack_only:
        print("\n[OK] --pack-only 打包验证完成，归档文件与 .sha256 已就绪。")
        return

    if not args.password:
        print("[Notice] 未提供密码，可通过 --password 或环境变量 DAMODEL_PASS 指定。")
        try:
            import getpass
            args.password = getpass.getpass("请输入云端实例 SSH 密码: ")
        except Exception as e:
            raise SystemExit(f"[FATAL] 缺少 SSH 密码: {e}")

    client = connect_ssh(args.host, args.port, args.user, args.password)
    try:
        if not args.fetch_only:
            upload_and_start(
                client,
                remote_work_dir=args.remote_dir,
                max_hours=args.max_hours,
                epochs=args.epochs,
                lr=args.lr,
                skip_smoke=args.skip_smoke,
                qlora=args.qlora,
            )
            stream_logs(client, remote_work_dir=args.remote_dir)
        fetch_deliverable(
            client,
            remote_work_dir=args.remote_dir,
            auto_deploy=args.auto_deploy,
            deploy_tag=args.deploy_tag,
            base_dir=args.base,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
