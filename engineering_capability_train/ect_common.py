#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ect_common.py — Engineering Capability Training 公共基础设施。

职责（全部标准库，保证云端 Linux / 本地 Windows 都能导入）：
  * repo root 定位：环境变量 > 向上搜索 AGENTS.md；不硬编码任何本机绝对路径
  * 配置装载与 schema 轻量校验
  * 可复现：一处设种，覆盖 random / numpy / torch（若已安装）
  * 完整性：sha256 / manifest / 原子写 / JSONL 流式读写
  * 资产复用：按文件路径动态加载工作区既有模块（virtu_tokenize / wm_verifier / report）

设计约束（来自工作区实测）：
  * 数据目录必须恰好 1 个训练 jsonl，且 sha256 与 manifest 一致才允许上云训练
  * 评测必须使用全新 run 目录，禁止复用旧目录造成"假刷新"
  * 所有产物写 receipt，SMOKE_ONLY 的 adapter 不得进入合并
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

PACKAGE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_DIR / "configs"

__all__ = [
    "repo_root", "load_config", "seed_everything", "sha256_file", "sha256_text",
    "atomic_write_json", "atomic_write_jsonl", "iter_jsonl", "write_manifest",
    "verify_manifest", "load_workspace_module", "now_iso", "timer", "log",
    "resolve", "CONFIG_DIR", "PACKAGE_DIR",
]


def repo_root() -> Path:
    """定位工作区根目录。优先环境变量，其次向上找 AGENTS.md / pyproject.toml。"""
    env = os.environ.get("VIRTU_REPO_ROOT")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "AGENTS.md").is_file() or (parent / "pyproject.toml").is_file():
            return parent
    # 退化：包目录的上一级（正常情况下不会走到这里）
    return here.parent.parent


def resolve(rel: str) -> Path:
    """把配置里的相对路径解析为工作区绝对路径；已是绝对路径则原样返回。"""
    p = Path(rel)
    return p if p.is_absolute() else (repo_root() / p)


def load_config(name: str) -> Dict[str, Any]:
    """装载 configs/<name>.json，name 可带或不带扩展名。"""
    p = CONFIG_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not p.is_file():
        raise FileNotFoundError(f"config not found: {p}")
    with p.open(encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict) or "schema_version" not in cfg:
        raise ValueError(f"invalid config (missing schema_version): {p}")
    return cfg


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """一次性设定所有随机源；torch 分支仅在已安装时执行，便于本地无 GPU 校验。"""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np  # type: ignore
        np.random.seed(seed % (2 ** 32 - 1))
    except Exception:
        pass
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            # 某些算子没有确定性实现时会抛错；由调用方决定是否需要严格模式
            try:
                torch.use_deterministic_algorithms(True, warn_only=True)
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
            except Exception:
                pass
    except Exception:
        pass


def sha256_file(path: os.PathLike | str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_json(path: os.PathLike | str, obj: Any, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent, default=str)
            f.write("\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_jsonl(path: os.PathLike | str, rows: Iterable[Dict[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    n = 0
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                n += 1
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return n


def iter_jsonl(path: os.PathLike | str) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} malformed JSON: {exc}") from exc


def write_manifest(path: os.PathLike | str, files: Iterable[os.PathLike | str],
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """为产物生成 sha256 账本。files 支持目录（自动展开其中的 .jsonl/.json）。"""
    entries: Dict[str, Dict[str, Any]] = {}
    for f in files:
        p = Path(f)
        targets: List[Path]
        if p.is_dir():
            targets = sorted(x for x in p.rglob("*")
                             if x.is_file() and x.suffix in (".jsonl", ".json"))
        elif p.is_file():
            targets = [p]
        else:
            continue
        for t in targets:
            key = str(t.resolve())
            entries[key] = {"sha256": sha256_file(t), "bytes": t.stat().st_size}
            if t.suffix == ".jsonl":
                entries[key]["lines"] = sum(1 for _ in iter_jsonl(t))
    manifest: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "generated_at": now_iso(),
        "seed": (extra or {}).get("seed"),
        "python": sys.version.split()[0],
        "files": entries,
        "extra": extra or {},
    }
    atomic_write_json(path, manifest)
    return manifest


def verify_manifest(manifest_path: os.PathLike | str) -> Dict[str, Any]:
    """逐文件比对 sha256；返回 {ok, checked, mismatches}，供云端开训前门禁。"""
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    bad = []
    checked = 0
    for key, meta in m.get("files", {}).items():
        p = Path(key)
        if not p.is_file():
            bad.append(f"missing: {key}")
            continue
        got = sha256_file(p)
        checked += 1
        if got != meta.get("sha256"):
            bad.append(f"sha256 mismatch: {key} (expected {meta.get('sha256')}, got {got})")
    return {"ok": not bad, "checked": checked, "mismatches": bad}


def load_workspace_module(rel_path: str, alias: Optional[str] = None):
    """按工作区相对路径动态加载一个既有 .py 模块（无需它属于可导入包）。

    例：load_workspace_module("scripts/virtu_tokenize.py")
        load_workspace_module("scripts/wm_verifier.py")
        load_workspace_module("virtu_eval/report.py")
    """
    p = resolve(rel_path)
    if not p.is_file():
        raise FileNotFoundError(f"workspace asset missing: {p}")
    name = alias or ("ect_" + p.stem)
    spec = importlib.util.spec_from_file_location(name, str(p))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build spec for {p}")
    mod = importlib.util.module_from_spec(spec)
    # wm_verifier 依赖同目录 distill_local_solver，需临时补 sys.path
    parent = str(p.parent)
    added = False
    if parent not in sys.path:
        sys.path.insert(0, parent)
        added = True
    try:
        spec.loader.exec_module(mod)
    finally:
        if added:
            try:
                sys.path.remove(parent)
            except ValueError:
                pass
    return mod


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class timer:
    """with timer() as t: ... ; t.elapsed"""
    def __init__(self) -> None:
        self.start = 0.0
        self.elapsed = 0.0

    def __enter__(self) -> "timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc) -> bool:
        self.elapsed = time.perf_counter() - self.start
        return False


def log(stage: str, msg: str) -> None:
    # 走 stderr：stdout 保留给机器可读的 JSON 结果，便于流水线直接管道消费
    print(f"[{datetime.now().strftime('%H:%M:%S')}][{stage}] {msg}",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    # 轻量自检：不依赖 GPU / 第三方库
    root = repo_root()
    print("repo_root =", root)
    for c in ("pipeline", "train", "metrics"):
        cfg = load_config(c)
        print(f"config {c}: schema={cfg['schema_version']}")
    print("self sha256 =", sha256_file(__file__)[:16])
    seed_everything(20261104)
    print("seed draw =", random.randint(0, 10 ** 6))
    print("SELFTEST OK")
