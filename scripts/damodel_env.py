"""Load Damodel SSH settings from the environment, never from source.

Required: DAMODEL_PASS and DAMODEL_PORT.
Optional: DAMODEL_HOST (default cn-north-b.ssh.damodel.com), DAMODEL_USER (root).
Password may also live in a gitignored `.damodel_pass` file at the repo root.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    host = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
    port = int(os.environ.get("DAMODEL_PORT", "0") or 0)
    user = os.environ.get("DAMODEL_USER", "root")
    password = os.environ.get("DAMODEL_PASS", "")
    if not password:
        password = _from_keyring(host, port)
    if not password:
        pfile = os.path.join(ROOT, ".damodel_pass")
        if os.path.isfile(pfile):
            with open(pfile, encoding="utf-8") as f:
                password = f.read().strip()
    if not password or not port:
        sys.exit(
            "[FATAL] 需要 DAMODEL_PORT 与 DAMODEL_PASS（或仓库根目录 .damodel_pass）。"
            "口令不得写入源码。"
        )
    return host, port, user, password


def _from_keyring(host: str, port: int) -> str:
    """Read the gitignored .damodel_pass.json mapping ({"host:port": "password"})."""
    json_file = os.path.join(ROOT, ".damodel_pass.json")
    if not os.path.isfile(json_file):
        return ""
    import json
    try:
        table = json.load(open(json_file, encoding="utf-8"))
    except Exception:
        sys.exit(f"[FATAL] {json_file} 无法解析，凭据读取失败。口令不得写入源码。")
    return table.get(f"{host}:{port}") or table.get(str(port)) or ""


def password_for(host: str, port: int) -> str:
    """Per-host keyring lookup for the helper scripts that target several rental ports.

    Resolution order: DAMODEL_PASS (single active box) -> gitignored `.damodel_pass.json`
    keyed by "host:port" -> gitignored `.damodel_pass`. Fails closed with a non-zero exit,
    because a silently empty password makes paramiko raise an auth error that reads like a
    network outage.
    """
    env_pass = os.environ.get("DAMODEL_PASS", "")
    if env_pass:
        return env_pass
    value = _from_keyring(host, port)
    if value:
        return value
    pfile = os.path.join(ROOT, ".damodel_pass")
    if os.path.isfile(pfile):
        value = open(pfile, encoding="utf-8").read().strip()
        if value:
            return value
    sys.exit(
        f"[FATAL] 找不到 {host}:{port} 的口令：请设 DAMODEL_PASS，或在 gitignored 的 "
        f".damodel_pass.json 里补 \"{host}:{port}\": \"...\"。口令不得写入源码。"
    )
