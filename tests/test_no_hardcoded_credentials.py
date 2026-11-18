"""Cloud-host credentials must never live in source.

Fifteen of this repo's remote-helper scripts carried the damodel SSH password as a
literal, with four dead rental ports baked in. They now resolve DAMODEL_PORT /
DAMODEL_PASS (or a gitignored .damodel_pass) through scripts/damodel_env.py.

Enumeration is deliberately git-index + scripts/*.py rather than a recursive walk:
this repo's tree contains junctioned model/checkpoint dirs, and a full rglob scan took
>120 s and could not be trusted to have covered the files it claimed to police.
"""
import glob
import io
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_REMOTE_HELPERS = (
    "_check2.py", "_check3.py", "_check_real_job.py", "_check_remote.py",
    "_check_remote_progress.py", "_check_remote_progress2.py", "_diag2.py",
    "_diag_pip.py", "_finalize.py", "_fix_accel.py", "_post_train_v2.py",
    "_post_train_v3.py", "_post_train_v4.py", "_post_train_worldmodel.py",
    "_probe_cloud.py", "_proof.py", "_relaunch.py", "_relaunch2.py",
    "_status.py", "_train_done_pull_deploy.py", "_upload_and_launch.py",
    "_upload_and_launch_v2.py", "_upload_and_launch_v3.py",
    "_upload_and_launch_v4.py", "_upload_and_launch_worldmodel.py",
    "_upload_and_launch_wm_v2.py", "_verify_train.py",
)

CRED_RE = re.compile(
    r"""(?:password|passwd|secret|api_key|apikey|access_token)\s*[:=]\s*
    ["']([^"'$\s%{}]{6,})["']""",
    re.X)
# Measured 2026-11-05: scripts/deploy_and_cleanup.py and scripts/damodel_active.py carried
# a live root password as `PASS = "..."`, which CRED_RE cannot see (the key name is not in
# its alternation) and which the connect() test cannot see either (connect receives the
# variable, not a quoted literal). Match credential-shaped UPPERCASE assignments.
CRED_ASSIGN_RE = re.compile(
    r"""^(?:[A-Z][A-Z0-9]*_)?(?:PASS(?:WORD)?|SECRET|TOKEN|API_?KEY|CREDENTIAL)\s*=\s*["']([^"'$\s]{6,})["']""",
    re.M)
ALLOWED = {"changeme", "placeholder", "your_password", "redacted", "serverselected"}


def candidate_files():
    """Tracked Python files plus the untracked helpers in scripts/ and repo root."""
    paths = set()
    # 自指例外：本文件含「探测器必须响」的合成字面量（password='Sup3rSecretValue'），
    # 把它自己纳入扫描会让这项闸门永久红，从而失去意义。只排除本文件。
    self_path = Path(__file__).resolve()
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=str(ROOT),
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.strip():
            paths.add(ROOT / line.strip())
    for pattern in ("scripts/*.py", "bridges/*.py", "*.py", "virtu_eval/*.py",
                    "cloud_train_pack/*.py"):
        for hit in glob.glob(str(ROOT / pattern)):
            paths.add(Path(hit))
    return sorted(p for p in paths if p.resolve() != self_path)


class TestDetectorIsNotBlind:
    """Prove the scanner fires before trusting a green run."""

    def test_detector_catches_a_synthetic_literal(self):
        sample = ("import paramiko\n"
                  "ssh.connect('host', port=1, username='root', "
                  "password='Sup3rSecretValue')\n")
        found = [m.group(1) for m in CRED_RE.finditer(sample)
                 if m.group(1).lower() not in ALLOWED]
        assert found == ["Sup3rSecretValue"], "凭证探测器本身失效，后面的扫描不可信"

    def test_detector_ignores_env_lookups_and_placeholders(self):
        benign = ('password = DAMODEL_PASS\n'
                  'password="changeme"\n'
                  'api_key=os.environ["DASHSCOPE_API_KEY"]\n')
        hits = [m.group(1) for m in CRED_RE.finditer(benign)
                if m.group(1).lower() not in ALLOWED]
        assert not hits, f"误报：{hits}"

    def test_detector_catches_a_short_named_credential_variable(self):
        """The exact shape that used to slip through: PASS = "<literal>"."""
        sample = ('HOST = "cn-north-b.ssh.damodel.com"\n'
                  'PORT = 44910\n'
                  'USER = "root"\n'
                  'PASS = "UYV7XKIJHk"\n'
                  'c.connect(hostname=HOST, port=PORT, username=USER, password=PASS)\n')
        found = [m.group(1) for m in CRED_ASSIGN_RE.finditer(sample)
                 if m.group(1).lower() not in ALLOWED]
        assert found == ["UYV7XKIJHk"], "PASS = 字面量必须被探测到，否则扫描等于没扫"
        # and the old blind spot stays blind to nothing: HOST/PORT/USER are not secrets
        assert "root" not in found and "cn-north-b.ssh.damodel.com" not in found

    def test_assign_detector_does_not_flag_environment_wiring(self):
        benign = ('DAMODEL_PASS = os.environ["DAMODEL_PASS"]\n'
                  'TOKEN = ""\n'
                  'KEYWORD_PREFIX = "documentation"\n'
                  'PORT = 44910\n')
        hits = [m.group(1) for m in CRED_ASSIGN_RE.finditer(benign)
                if m.group(1).lower() not in ALLOWED]
        assert not hits, f"误报：{hits}"


class TestRepositoryIsClean:
    def test_scanned_set_is_not_empty(self):
        assert len(candidate_files()) > 100, "文件枚举失效，扫描等于没扫"

    def test_no_password_literals_in_source(self):
        offenders = []
        for path in candidate_files():
            try:
                text = io.open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for match in CRED_RE.finditer(text):
                if match.group(1).lower() in ALLOWED:
                    continue
                line = text[:match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
            for match in CRED_ASSIGN_RE.finditer(text):
                if match.group(1).lower() in ALLOWED:
                    continue
                line = text[:match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line} (credential-shaped literal)")
        assert not offenders, (
            "口令/密钥不得写进源码，请走环境变量或 gitignored 文件："
            + "; ".join(offenders[:20]))

    def test_no_quoted_password_reaches_connect(self):
        offenders = []
        for path in candidate_files():
            text = io.open(path, encoding="utf-8", errors="ignore").read()
            for match in re.finditer(r"\.connect\(([^)]*)\)", text, re.S):
                if re.search(r"password\s*=\s*[\"'][^\"']+[\"']", match.group(1)):
                    offenders.append(f"{path.name}:"
                                     f"{text[:match.start()].count(chr(10)) + 1}")
        assert not offenders, "connect() 的 password 必须来自变量/环境：" + "; ".join(offenders)

    def test_loader_refuses_to_run_without_credentials(self):
        env = dict(os.environ)
        env.pop("DAMODEL_PASS", None)
        env.pop("DAMODEL_PORT", None)
        env["PYTHONIOENCODING"] = "utf-8"
        passfile = ROOT / ".damodel_pass"
        hidden = None
        if passfile.exists():  # step aside, never delete a real secret file
            hidden = passfile.with_name(".damodel_pass.test-hidden")
            passfile.rename(hidden)
        try:
            proc = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.path.insert(0, r'%s'); import damodel_env; "
                 "damodel_env.load()" % (ROOT / "scripts")],
                capture_output=True, text=True, env=env,
                encoding="utf-8", errors="replace")
            assert proc.returncode != 0, "缺凭据必须非零退出，不能静默继续"
            assert "口令不得写入源码" in (proc.stdout + proc.stderr)
        finally:
            if hidden is not None:
                hidden.rename(passfile)

    def test_damodel_pass_file_is_gitignored(self):
        """scripts/damodel_env.py documents .damodel_pass as gitignored; assert it."""
        proc = subprocess.run(["git", "check-ignore", "-q", ".damodel_pass"],
                              cwd=str(ROOT), capture_output=True)
        assert proc.returncode == 0, ".damodel_pass 未被 .gitignore 覆盖"
        proc = subprocess.run(["git", "check-ignore", "-q", ".damodel_pass.json"],
                              cwd=str(ROOT), capture_output=True)
        assert proc.returncode == 0, ".damodel_pass.json（多端口钥匙环）未被 .gitignore 覆盖"
        proc = subprocess.run(["git", "check-ignore", "-q",
                               "cloud_artifacts/.damodel_pw.bak"],
                              cwd=str(ROOT), capture_output=True)
        assert proc.returncode == 0, "cloud_artifacts/.damodel_pw.bak 未被 .gitignore 覆盖"

    def test_keyring_resolves_each_port_and_refuses_unknown_ports(self):
        """13 helper scripts now read PASS = damodel_env.password_for(HOST, PORT).

        An unknown port must exit non-zero rather than hand paramiko an empty password,
        which fails as an authentication error that reads like a network outage.
        """
        env = dict(os.environ)
        env.pop("DAMODEL_PASS", None)
        env["PYTHONIOENCODING"] = "utf-8"
        probe = ("import sys; sys.path.insert(0, r'%s'); import damodel_env as e; "
                 "assert e.password_for('cn-north-b.ssh.damodel.com', 44228); "
                 "e.password_for('cn-north-b.ssh.damodel.com', 1)" % (ROOT / "scripts"))
        proc = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                              text=True, env=env,
                              encoding="utf-8", errors="replace")
        assert proc.returncode != 0, "未知端口必须失败关闭"
        assert "口令不得写入源码" in (proc.stdout + proc.stderr)

    def test_helper_scripts_no_longer_carry_the_literal(self):
        offenders = []
        for name in ("deploy_and_cleanup.py", "damodel_active.py", "auto_pull_and_merge.py",
                     "check_conda_env.py", "check_pid_etime.py", "check_real_train_log.py",
                     "check_running_train.py", "check_train_fds.py", "check_train_progress.py",
                     "do_download_lora.py", "inspect_v100_train.py",
                     "monitor_and_fetch_daemon.py", "relaunch_remote.py",
                     "remote_damodel_mgr.py", "remote_train_and_download.py"):
            path = ROOT / "scripts" / name
            text = io.open(path, encoding="utf-8", errors="ignore").read()
            if "damodel_env" not in text:
                offenders.append(f"{name} 未接钥匙环")
            for match in CRED_ASSIGN_RE.finditer(text):
                offenders.append(f"{name}:{text[:match.start()].count(chr(10)) + 1}")
        assert not offenders, "凭据仍留在源码里：" + "; ".join(offenders)

    def test_legacy_remote_helpers_use_environment_credentials_only(self):
        missing = []
        offenders = []
        for name in LEGACY_REMOTE_HELPERS:
            path = ROOT / "scripts" / name
            if not path.is_file():
                missing.append(name)
                continue
            text = io.open(path, encoding="utf-8", errors="ignore").read()
            if ".damodel_pw" in text or re.search(r"(?<!\w)--pw(?:\b|=)", text):
                offenders.append(name)
            if "DAMODEL_PW" not in text and "import _ssh_damodel as S" not in text:
                offenders.append(f"{name} (no environment-backed SSH helper)")
        assert not missing, "待审阅入口缺失：" + "; ".join(missing)
        assert not offenders, "旧辅助脚本不得读取密码文件或接受 CLI 口令：" + "; ".join(offenders)
