# -*- coding: utf-8 -*-
"""Falsifiable verification tests for cloud instant-start & on-boot training scripts."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACK_DIR = ROOT / "cloud_train_pack"


def _find_git_bash() -> str | None:
    cand = Path(r"C:\Program Files\Git\bin\bash.exe")
    if cand.exists():
        return str(cand)
    return None


def test_cloud_shell_scripts_lf_syntax_and_safe_empty_array_expansion():
    shs = [
        ROOT / "launch_cloud_full_train.sh",
        PACK_DIR / "start_cloud_train_now.sh",
        PACK_DIR / "onboot_cloud_train.sh",
        PACK_DIR / "run_vericut96.sh",
        PACK_DIR / "run_vericut_e_training.sh",
        PACK_DIR / "run_six_software_real.sh",
    ]
    bash_exe = _find_git_bash()
    for p in shs:
        assert p.exists(), f"Missing script: {p}"
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"CRLF detected in Linux script: {p}"
        txt = raw.decode("utf-8")
        # Ensure nohup background launchers never pass bare empty arrays under set -u.
        for lineno, line in enumerate(txt.splitlines(), 1):
            if "nohup" in line and ("EXTRA_ARGS[@]}" in line or "ORIG_ARGS[@]}" in line):
                assert (
                    '${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}' in line
                    or '${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}' in line
                ), f"Unsafe empty array expansion under set -u at {p.name}:{lineno}: {line}"
        if bash_exe:
            proc = subprocess.run([bash_exe, "-n", str(p)], capture_output=True, text=True, encoding="utf-8")
            assert proc.returncode == 0, f"bash -n failed for {p}: {proc.stderr}"

    cmd_raw = (ROOT / "START_CLOUD_TRAIN_NOW.cmd").read_bytes()
    assert b"\r\n" in cmd_raw, "START_CLOUD_TRAIN_NOW.cmd must keep CRLF"
    assert "vericut96-v2" in cmd_raw.decode("utf-8")


def _run_bash_to_file(bash_exe, args, cwd, timeout_s):
    """跑一个 bash 子进程，stdout/stderr **落文件**而不是管道。

    2026-11-16 实测事故：``subprocess.run(capture_output=True, timeout=N)`` 在
    Windows 上会派生孙进程继承 stdout 管道；父进程一旦被 pytest-timeout 杀掉，
    管道永不 EOF，``communicate()`` 的 reader 线程无限 join()，**整个 pytest 进程
    被一起拖死**（日志停在 "++++ Timeout +++"，没有 summary、没有 FAILED 列表）。

    本仓的 ``start_cloud_train_now.sh --selftest`` 实测需要 ~130s，超过默认
    ``--timeout=120`` ⇒ 父进程被中途杀掉 ⇒ 触发上述死锁。两条都改：
      1. 输出走临时文件 ⇒ 没有管道，父进程被杀也不会死锁；
      2. 超时放宽到 300s ⇒ 正常路径下脚本能跑完，根本不会被中途杀。

    返回 (returncode, stdout_text, stderr_text)。
    """
    out_f = tempfile.NamedTemporaryFile(prefix="nx_sh_out_", suffix=".log",
                                        delete=False, mode="w+", encoding="utf-8")
    err_f = tempfile.NamedTemporaryFile(prefix="nx_sh_err_", suffix=".log",
                                        delete=False, mode="w+", encoding="utf-8")
    try:
        with out_f, err_f:
            proc = subprocess.run(
                [bash_exe, *args],
                cwd=str(cwd),
                stdout=out_f,
                stderr=err_f,
                timeout=timeout_s,
            )
        out_f = Path(out_f.name)
        err_f = Path(err_f.name)
        stdout_text = out_f.read_text(encoding="utf-8", errors="replace")
        stderr_text = err_f.read_text(encoding="utf-8", errors="replace")
        return proc.returncode, stdout_text, stderr_text
    finally:
        for p in (locals().get("out_f"), locals().get("err_f")):
            try:
                Path(str(p)).unlink(missing_ok=True)
            except Exception:
                pass


@pytest.mark.timeout(300)
def test_start_cloud_train_now_routes_v2_and_rejects_bad_track():
    sh_txt = (PACK_DIR / "start_cloud_train_now.sh").read_text(encoding="utf-8")
    for needle in (
        "vericut96-v2",
        "TRACK_VERSION=v2",
        "--tracks",
        "--wait-gpu-s",
        "flock",
        "torch.matmul",
        '"transformers>=4.51.0,<5.0.0"',
        '"peft>=0.13.0,<0.16.0"',
        '"datasets>=2.18.0,<4.0.0"',
        '"trl>=0.12.0,<0.18.0"',
    ):
        assert needle in sh_txt, f"Missing expected contract in start_cloud_train_now.sh: {needle}"

    bash_exe = _find_git_bash()
    if bash_exe:
        bad_rc, bad_out, bad_err = _run_bash_to_file(
            bash_exe,
            [str(PACK_DIR / "start_cloud_train_now.sh"), "--tracks",
             "vericut96-v2,nonexistent-track", "--selftest"],
            ROOT, timeout_s=300)
        assert bad_rc != 0, "Unknown track in --tracks must fail closed"

        good_rc, good_out, good_err = _run_bash_to_file(
            bash_exe,
            [str(PACK_DIR / "start_cloud_train_now.sh"), "--track",
             "vericut96-v2", "--selftest"],
            ROOT, timeout_s=300)
        assert good_rc == 0, f"vericut96-v2 selftest failed:\n{good_out}\n{good_err}"


def test_onboot_cloud_train_sha256_fail_closed_and_auto_unpack(tmp_path):
    bash_exe = _find_git_bash()
    if not bash_exe:
        pytest.skip("Git Bash unavailable on host")

    # Provide lightweight nvidia-smi shim on PATH
    bin_dir = tmp_path / "fake_bin"
    bin_dir.mkdir(parents=True)
    fake_nvidia = bin_dir / "nvidia-smi"
    fake_nvidia.write_text("#!/usr/bin/env bash\necho '0, FakeGPU, 49140 MiB, 48000 MiB'\n", encoding="utf-8", newline="\n")

    bundle = tmp_path / "virtu_vericut96_v2_bundle.tar.gz"
    fake_runner_src = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo \"track_version=${TRACK_VERSION:-unset}\" > \"$(dirname \"$0\")/ran.flag\"\n"
    ).encode("utf-8")
    with tarfile.open(bundle, "w:gz") as tar:
        info = tarfile.TarInfo("run_vericut96.sh")
        info.size = len(fake_runner_src)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(fake_runner_src))

    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    sha_file = tmp_path / (bundle.name + ".sha256")
    work_dir = tmp_path / "work"

    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    # 1. Tampered SHA256 MUST block extraction and execution with explicit SHA256 error
    sha_file.write_text("0" * 64 + f"  {bundle.name}\n", encoding="utf-8", newline="\n")
    bad_proc = subprocess.run(
        [
            bash_exe,
            str(PACK_DIR / "onboot_cloud_train.sh"),
            "--dir",
            str(work_dir),
            "--bundle",
            str(bundle),
            "--track",
            "vericut96-v2",
            "--fg",
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert bad_proc.returncode != 0, "Tampered bundle .sha256 was not blocked"
    assert "SHA256" in (bad_proc.stderr + bad_proc.stdout), f"Unexpected block reason: {bad_proc.stderr}"
    assert not (work_dir / "run_vericut96.sh").exists()
    assert not (work_dir / "ran.flag").exists()

    # 2. Valid SHA256 MUST unpack, wait/probe GPU, dispatch TRACK_VERSION=v2, and write receipt
    sha_file.write_text(f"{digest}  {bundle.name}\n", encoding="utf-8", newline="\n")
    ok_proc = subprocess.run(
        [
            bash_exe,
            str(PACK_DIR / "onboot_cloud_train.sh"),
            "--dir",
            str(work_dir),
            "--bundle",
            str(bundle),
            "--track",
            "vericut96-v2",
            "--fg",
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert ok_proc.returncode == 0, f"onboot auto-unpack failed:\n{ok_proc.stdout}\n{ok_proc.stderr}"
    assert (work_dir / "ran.flag").read_text(encoding="utf-8").strip() == "track_version=v2"
    receipt = json.loads((work_dir / "runs" / "onboot_receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "LAUNCHED"
    assert receipt["tracks"] == "vericut96-v2"


def test_start_train_now_ssh_parse_forever_wait_and_multitrack(tmp_path):
    pack_str = str(PACK_DIR)
    if pack_str not in sys.path:
        sys.path.insert(0, pack_str)
    import start_train_now

    # 1. SSH command parser positive + adversarial rejection
    assert start_train_now.parse_ssh_command("ssh -p 40526 root@cn-north-b.ssh.damodel.com") == {
        "host": "cn-north-b.ssh.damodel.com",
        "port": 40526,
        "user": "root",
    }
    assert start_train_now.parse_ssh_command("ubuntu@192.168.10.5:2202") == {
        "host": "192.168.10.5",
        "port": 2202,
        "user": "ubuntu",
    }
    for bad in ("", "ssh root@h; id", "ssh -p 70000 root@h", "ssh $(whoami)@h"):
        with pytest.raises(ValueError):
            start_train_now.parse_ssh_command(bad)

    # 2. Infinite wait (--wait-online-seconds -1) retries across failed probes then connects
    attempts = {"n": 0}

    def flaky_tcp(_h: str, _p: int, _t: float):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return False, "connection refused"
        return True, "open"

    class FakeChannel:
        def recv_exit_status(self):
            return 0

    class FakeOut:
        channel = FakeChannel()

        def read(self):
            return b"READY\nA100, 81920 MiB, 550.54\n"

    class FakeErr:
        def read(self):
            return b""

    class FakeSSH:
        def set_missing_host_key_policy(self, _policy):
            pass

        def connect(self, **_kwargs):
            pass

        def exec_command(self, _cmd):
            return None, FakeOut(), FakeErr()

        def close(self):
            pass

    fake_paramiko = mock.MagicMock()
    fake_paramiko.SSHClient.return_value = FakeSSH()
    fake_paramiko.AutoAddPolicy.return_value = object()

    with (
        mock.patch.object(start_train_now.local_one_click, "_ensure_paramiko", return_value=fake_paramiko),
        mock.patch.object(start_train_now.time, "sleep", return_value=None),
    ):
        client, gpu_info = start_train_now.wait_for_instance_online(
            "demo.host",
            2200,
            "root",
            "secret",
            wait_online_seconds=-1.0,
            poll_interval=0.1,
            tcp_probe_fn=flaky_tcp,
        )
    assert attempts["n"] == 3
    assert "READY" in gpu_info and client is not None

    # 3. 0.0s must still fail fast
    with pytest.raises(SystemExit):
        start_train_now.wait_for_instance_online(
            "demo.host",
            2200,
            "root",
            "secret",
            wait_online_seconds=0.0,
            tcp_probe_fn=lambda _h, _p, _t: (False, "refused"),
        )

    # 4. Multi-track resolution deduplicates while preserving order & rejects unknown tracks
    assert start_train_now.resolve_track_list("master-8b", "vericut96-v2, vericut-e, vericut96-v2, six-software") == [
        "vericut96-v2",
        "vericut-e",
        "six-software",
    ]
    with pytest.raises(SystemExit):
        start_train_now.resolve_track_list("master-8b", "vericut96-v2,bad-track")
