#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/start_train_now.py — Virtu 上线马上开训·统一调度与双阶看门狗

核心能力：
  1. 零等待预打包与离线自检（--prepare-only / --selftest）：
     - 自动校验并预打包各产线自包含归档包与 .sha256 伴随凭证，实盘上线 0 秒即传；
  2. 等机上线 TCP + SSH 就绪探针（--wait-online-seconds）：
     - 新租云端 GPU 实例开机中即可先执行本脚本，TCP 端口一通即秒连 SSH 并探测 GPU；
  3. SHA256 校验上传 + 后台单实例锁启动：
     - 远端强制 `sha256sum -c` + Unix LF 修复 + `flock` 单实例启动（若已在跑则无损挂载监控）；
  4. 双阶实时看门狗 + COMPLETED 才回收部署（--follow / --auto-deploy）：
     - Stage 1 (`verify_training_started`): 进程存活 + GPU 显存 >= 2000 MiB（或进入训练阶段）落盘 marker；
     - Stage 2 (`watch_training_health`): 识别 `[FATAL]` / Traceback / GPU<10% 且 >=420s 无步进真卡死；
     - 仅当 `status == "COMPLETED"` 且 SHA256 双验通过才拉回并调用 `deploy_trained_adapter.py`。

用法示例：
  # 1) 本地离线自检
  .venv\\Scripts\\python.exe cloud_train_pack\\start_train_now.py --selftest

  # 2) 本地提前预打包校验（生成 cloud_train_pack.tar.gz + .sha256，实例未开机也能先准备）
  .venv\\Scripts\\python.exe cloud_train_pack\\start_train_now.py --prepare-only --track master-8b

  # 3) 等云端实例一上线马上开训，并全程看门狗监控 + 完成后自动拉回真融合部署
  $env:DAMODEL_PASS="<SSH_PASSWORD>"
  .venv\\Scripts\\python.exe cloud_train_pack\\start_train_now.py ^
    --track master-8b --host cn-north-b.ssh.damodel.com --port 40526 --follow --auto-deploy
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PACK_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PACK_DIR)
for _p in (PACK_DIR, ROOT, os.path.join(ROOT, "scripts")):
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import local_one_click  # noqa: E402
import local_one_click_worldmodel  # noqa: E402

BENCHMARK_SUBDIRS = ("virtu_eval_v1", "virtu_eval_phys_v1", "virtu_eval_cl_v1")
FATAL_LOG_MARKERS = (
    "[FATAL]",
    "Traceback (most recent call last):",
    "RuntimeError:",
    "CUDA error",
    "OutOfMemoryError",
    "cudaError",
)


def find_active_fatal_marker(log_tail: str, markers=FATAL_LOG_MARKERS):
    """扫描日志中的致命异常标记，忽略已通过的 --selftest 反向测试产生的期望内 [FATAL] 噪音。"""
    lines = (log_tail or "").splitlines()
    selftest_pass_indices = [i for i, ln in enumerate(lines) if "[SELFTEST] PASS" in ln]
    for idx, line in enumerate(lines):
        for marker in markers:
            if marker not in line:
                continue
            if marker == "[FATAL]":
                if "[SELFTEST]" in line and "FAIL" not in line.upper():
                    continue
                if any(idx < p_idx <= idx + 15 for p_idx in selftest_pass_indices):
                    continue
            return marker
    return None
STARTED_LOG_MARKERS = (
    "Stage 4",
    "Stage 6",
    "STEP 4",
    "'loss':",
    '"loss":',
    "loss=",
    "train_loss",
)
STEP_RE = re.compile(r"(?:global_step|step)\s*[=:]\s*(\d+)|\|\s*(\d+)\s*/\s*\d+\s*\[", re.IGNORECASE)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _write_sha256_sidecar(archive_path: str) -> str:
    digest = sha256_file(archive_path)
    with open(archive_path + ".sha256", "w", encoding="utf-8", newline="\n") as sf:
        sf.write(f"{digest}  {os.path.basename(archive_path)}\n")
    return digest


def _verify_local_archive_sha(archive_path: str) -> Tuple[bool, str]:
    sidecar = archive_path + ".sha256"
    if not os.path.exists(archive_path) or not os.path.exists(sidecar):
        return False, "missing_archive_or_sidecar"
    try:
        recorded = open(sidecar, "r", encoding="utf-8").read().strip().split()[0]
    except Exception:
        return False, "unreadable_sidecar"
    if len(recorded) != 64:
        return False, "invalid_sidecar_sha256"
    actual = sha256_file(archive_path)
    if actual.lower() != recorded.lower():
        return False, f"sha_mismatch:{recorded[:12]}!={actual[:12]}"
    return True, actual


def _add_file_or_lf_script(tar: tarfile.TarFile, src: str, arcname: str) -> None:
    if src.endswith(".sh"):
        with open(src, "rb") as rf:
            data = rf.read().replace(b"\r\n", b"\n")
        info = tarfile.TarInfo(name=arcname)
        info.size = len(data)
        info.mode = 0o755
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(data))
    else:
        tar.add(src, arcname=arcname)


def _add_benchmarks(tar: tarfile.TarFile) -> int:
    count = 0
    for sub in BENCHMARK_SUBDIRS:
        sub_dir = os.path.join(ROOT, "data", "benchmark", sub)
        if not os.path.isdir(sub_dir):
            raise SystemExit(f"[FATAL] 打包缺少防污染评测基准目录: {sub_dir}")
        for fp in sorted(glob.glob(os.path.join(sub_dir, "*.jsonl"))):
            rel = os.path.relpath(fp, ROOT).replace("\\", "/")
            tar.add(fp, arcname=rel)
            count += 1
    return count


def _build_13b_bundle(archive_path: str, dataset_arg: Optional[str] = None) -> Tuple[str, str]:
    sft_path = (
        dataset_arg
        if dataset_arg
        else os.path.join(PACK_DIR, "dataset", "train_corpus_phase2_targeted.jsonl")
    )
    if not os.path.exists(sft_path):
        raise SystemExit(f"[FATAL] 13B 主训语料不存在: {sft_path}")
    dpo_path = os.path.join(PACK_DIR, "dataset", "dpo_phase2_targeted.jsonl")
    required = [
        (os.path.join(PACK_DIR, "train_cloud_virtu_13b.py"), "cloud_train_pack/train_cloud_virtu_13b.py"),
        (os.path.join(PACK_DIR, "run_13b_evolution_train.sh"), "cloud_train_pack/run_13b_evolution_train.sh"),
        (os.path.join(PACK_DIR, "dataset", "build_phase2_targeted_corpus.py"), "cloud_train_pack/dataset/build_phase2_targeted_corpus.py"),
        (sft_path, f"cloud_train_pack/dataset/{os.path.basename(sft_path)}"),
        (os.path.join(ROOT, "virtu_eval", "__init__.py"), "virtu_eval/__init__.py"),
        (os.path.join(ROOT, "virtu_eval", "contamination_check.py"), "virtu_eval/contamination_check.py"),
        (os.path.join(ROOT, "scripts", "corpus_unit_audit.py"), "scripts/corpus_unit_audit.py"),
    ]
    optional = [
        (dpo_path, "cloud_train_pack/dataset/dpo_phase2_targeted.jsonl"),
        (os.path.join(PACK_DIR, "dataset", "phase2_targeted_ledger.json"), "cloud_train_pack/dataset/phase2_targeted_ledger.json"),
    ]
    for src, _ in required:
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] 13B 打包缺少必需文件: {src}")

    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for src, arc in required:
            _add_file_or_lf_script(tar, src, arc)
        for src, arc in optional:
            if os.path.exists(src):
                _add_file_or_lf_script(tar, src, arc)
        _add_benchmarks(tar)
    digest = _write_sha256_sidecar(archive_path)
    return archive_path, digest


def _build_all90_bundle(archive_path: str, dataset_arg: Optional[str] = None) -> Tuple[str, str]:
    ds_path = local_one_click.resolve_primary_dataset(dataset_arg)
    ds_name = os.path.basename(ds_path)
    ds_sha = sha256_file(ds_path)
    ledger = {
        "output_path": f"dataset/{ds_name}",
        "output_sha256": ds_sha,
        "files": {ds_name: {"sha256": ds_sha, "size_bytes": os.path.getsize(ds_path)}},
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    required = [
        (os.path.join(PACK_DIR, "train_turnkey.py"), "train_turnkey.py"),
        (os.path.join(PACK_DIR, "run.sh"), "run.sh"),
        (os.path.join(ROOT, "virtu_eval", "__init__.py"), "virtu_eval/__init__.py"),
        (os.path.join(ROOT, "virtu_eval", "contamination_check.py"), "virtu_eval/contamination_check.py"),
        (os.path.join(ROOT, "virtu_eval", "tool_schema.py"), "virtu_eval/tool_schema.py"),
        (os.path.join(ROOT, "virtu_eval", "provenance.py"), "virtu_eval/provenance.py"),
        (os.path.join(ROOT, "virtu_eval", "derivation.py"), "virtu_eval/derivation.py"),
        (os.path.join(ROOT, "bridges", "tool_calling_specs.py"), "bridges/tool_calling_specs.py"),
        (os.path.join(ROOT, "scripts", "corpus_unit_audit.py"), "scripts/corpus_unit_audit.py"),
        (os.path.join(ROOT, "scripts", "wm_verifier.py"), "scripts/wm_verifier.py"),
        (os.path.join(ROOT, "scripts", "gate_all90_dataset.py"), "scripts/gate_all90_dataset.py"),
        (os.path.join(ROOT, "scripts", "collect_six_trajectories.py"), "scripts/collect_six_trajectories.py"),
        (os.path.join(ROOT, "scripts", "derive_trajectories.py"), "scripts/derive_trajectories.py"),
        (os.path.join(ROOT, "scripts", "build_six_holdout_200.py"), "scripts/build_six_holdout_200.py"),
        (os.path.join(ROOT, "scripts", "train_dpo_all90.py"), "scripts/train_dpo_all90.py"),
        (os.path.join(ROOT, "scripts", "eval_all90_three_boards.py"), "scripts/eval_all90_three_boards.py"),
    ]
    for src, _ in required:
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] All-90 打包缺少必需文件: {src}")

    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for src, arc in required:
            _add_file_or_lf_script(tar, src, arc)
        tool_map = os.path.join(ROOT, "scripts", "corpus_tool_map.json")
        if os.path.exists(tool_map):
            tar.add(tool_map, arcname="scripts/corpus_tool_map.json")
        tar.add(ds_path, arcname=f"dataset/{ds_name}")
        local_one_click._add_bytes_to_tar(
            tar,
            "dataset/dataset_ledger.json",
            json.dumps(ledger, ensure_ascii=False, indent=2).encode("utf-8"),
            mode=0o644,
        )
        _add_benchmarks(tar)
    digest = _write_sha256_sidecar(archive_path)
    return archive_path, digest


def _build_safety_bundle(archive_path: str, dataset_arg: Optional[str] = None) -> Tuple[str, str]:
    required = [
        (os.path.join(PACK_DIR, "run_safety_repair.sh"), "cloud_train_pack/run_safety_repair.sh"),
        (os.path.join(PACK_DIR, "train_safety_cloud.py"), "cloud_train_pack/train_safety_cloud.py"),
        (os.path.join(PACK_DIR, "train_turnkey.py"), "cloud_train_pack/train_turnkey.py"),
        (os.path.join(PACK_DIR, "train_dpo_cloud.py"), "cloud_train_pack/train_dpo_cloud.py"),
        (os.path.join(PACK_DIR, "eval_safety_boundary.py"), "cloud_train_pack/eval_safety_boundary.py"),
        (os.path.join(PACK_DIR, "deploy_safety_repair.py"), "cloud_train_pack/deploy_safety_repair.py"),
        (os.path.join(PACK_DIR, "dataset", "build_safety_boundary_sft.py"), "cloud_train_pack/dataset/build_safety_boundary_sft.py"),
        (os.path.join(PACK_DIR, "dataset", "safety_boundary_sft.jsonl"), "cloud_train_pack/dataset/safety_boundary_sft.jsonl"),
        (os.path.join(PACK_DIR, "dataset", "safety_boundary_dpo_pairs.jsonl"), "cloud_train_pack/dataset/safety_boundary_dpo_pairs.jsonl"),
        (os.path.join(PACK_DIR, "dataset", "safety_boundary_manifest.json"), "cloud_train_pack/dataset/safety_boundary_manifest.json"),
        (os.path.join(ROOT, "virtu_eval", "__init__.py"), "virtu_eval/__init__.py"),
        (os.path.join(ROOT, "virtu_eval", "contamination_check.py"), "virtu_eval/contamination_check.py"),
        (os.path.join(ROOT, "scripts", "corpus_unit_audit.py"), "scripts/corpus_unit_audit.py"),
    ]
    for src, _ in required:
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] Safety 打包缺少必需文件: {src}")
    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for src, arc in required:
            _add_file_or_lf_script(tar, src, arc)
        _add_benchmarks(tar)
    digest = _write_sha256_sidecar(archive_path)
    return archive_path, digest


def _vericut_common_files() -> List[Tuple[str, str]]:
    return [
        (os.path.join(PACK_DIR, "train_turnkey.py"), "train_turnkey.py"),
        (os.path.join(ROOT, "virtu_eval", "__init__.py"), "virtu_eval/__init__.py"),
        (os.path.join(ROOT, "virtu_eval", "contamination_check.py"), "virtu_eval/contamination_check.py"),
        (os.path.join(ROOT, "virtu_eval", "tool_schema.py"), "virtu_eval/tool_schema.py"),
        (os.path.join(ROOT, "virtu_eval", "provenance.py"), "virtu_eval/provenance.py"),
        (os.path.join(ROOT, "virtu_eval", "derivation.py"), "virtu_eval/derivation.py"),
        (os.path.join(ROOT, "bridges", "tool_calling_specs.py"), "bridges/tool_calling_specs.py"),
        (os.path.join(ROOT, "scripts", "cad_tools_iface.py"), "scripts/cad_tools_iface.py"),
        (os.path.join(ROOT, "scripts", "corpus_unit_audit.py"), "scripts/corpus_unit_audit.py"),
        (os.path.join(ROOT, "scripts", "wm_verifier.py"), "scripts/wm_verifier.py"),
        (os.path.join(ROOT, "scripts", "wm_contract.py"), "scripts/wm_contract.py"),
        (os.path.join(ROOT, "scripts", "wm_schema.py"), "scripts/wm_schema.py"),
        (os.path.join(ROOT, "scripts", "distill_local_solver.py"), "scripts/distill_local_solver.py"),
        (os.path.join(ROOT, "scripts", "gate_all90_dataset.py"), "scripts/gate_all90_dataset.py"),
        (os.path.join(ROOT, "scripts", "train_dpo_all90.py"), "scripts/train_dpo_all90.py"),
    ]


def _pack_vericut_archive(
    archive_path: str,
    required: List[Tuple[str, str]],
    extra_bytes: List[Tuple[str, bytes]],
    optional: List[Tuple[str, str]],
    label: str,
) -> Tuple[str, str]:
    for src, _ in required:
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] {label} 打包缺少必需文件: {src}")
    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for src, arc in required:
            _add_file_or_lf_script(tar, src, arc)
        for arc, payload in extra_bytes:
            local_one_click._add_bytes_to_tar(tar, arc, payload, mode=0o644)
        bridges_init = os.path.join(ROOT, "bridges", "__init__.py")
        if not os.path.exists(bridges_init):
            local_one_click._add_bytes_to_tar(tar, "bridges/__init__.py", b"", mode=0o644)
        for src, arc in optional:
            if os.path.exists(src):
                _add_file_or_lf_script(tar, src, arc)
        _add_benchmarks(tar)
    digest = _write_sha256_sidecar(archive_path)
    return archive_path, digest


def _build_vericut96_bundle(
    archive_path: str,
    dataset_arg: Optional[str] = None,
    *,
    version: str = "v1",
) -> Tuple[str, str]:
    is_v2 = version == "v2"
    sub_dir = "dataset_v2" if is_v2 else "dataset"
    prefix = "vericut96_v2" if is_v2 else "vericut96"
    sft_name = f"{prefix}_sft_mix.jsonl"
    sft_ledger_name = f"{prefix}_sft_mix_ledger.json"
    dpo_name = f"{prefix}_dpo_mix.jsonl"
    dpo_ledger_name = f"{prefix}_dpo_mix_ledger.json"

    sft_path = dataset_arg if dataset_arg else os.path.join(PACK_DIR, sub_dir, sft_name)
    sft_ledger = os.path.join(PACK_DIR, sub_dir, sft_ledger_name)
    dpo_path = os.path.join(PACK_DIR, sub_dir, dpo_name)
    dpo_ledger = os.path.join(PACK_DIR, sub_dir, dpo_ledger_name)
    if (
        not dataset_arg
        and (
            not os.path.exists(sft_path)
            or not os.path.exists(sft_ledger)
            or not os.path.exists(dpo_path)
            or not os.path.exists(dpo_ledger)
        )
    ):
        from build_vericut96_cloud_datasets import build_vericut96_cloud_datasets
        if is_v2:
            build_vericut96_cloud_datasets(
                out_dir=Path(PACK_DIR) / "dataset_v2",
                anchor_limit=64,
                dpo_anchor_limit=48,
                prefix="vericut96_v2",
            )
        else:
            build_vericut96_cloud_datasets(out_dir=Path(PACK_DIR) / "dataset")

    if not os.path.exists(sft_path) or not os.path.exists(dpo_path):
        raise SystemExit(f"[FATAL] VERICUT96({version}) 打包缺少语料: sft={sft_path}, dpo={dpo_path}")

    sft_sha = sha256_file(sft_path)
    if not os.path.exists(sft_ledger) or dataset_arg:
        ledger_obj = {
            "output_name": os.path.basename(sft_path),
            "output_sha256": sft_sha,
            "size_bytes": os.path.getsize(sft_path),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        sft_ledger_bytes = (json.dumps(ledger_obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    else:
        with open(sft_ledger, "rb") as lf:
            sft_ledger_bytes = lf.read()
        exp_sha = str(json.loads(sft_ledger_bytes.decode("utf-8")).get("output_sha256") or "").lower()
        if exp_sha and exp_sha != sft_sha.lower():
            raise SystemExit(f"[FATAL] VERICUT96({version}) SFT ledger SHA256 不匹配: {exp_sha[:16]} != {sft_sha[:16]}")

    required = _vericut_common_files() + [
        (os.path.join(PACK_DIR, "run_vericut96.sh"), "run_vericut96.sh"),
        (sft_path, f"{sub_dir}/{sft_name}"),
        (dpo_path, f"{sub_dir}/{dpo_name}"),
        (dpo_ledger, f"{sub_dir}/{dpo_ledger_name}"),
        (os.path.join(ROOT, "scripts", "build_vericut96_cloud_datasets.py"), "scripts/build_vericut96_cloud_datasets.py"),
    ]
    optional = [
        (os.path.join(ROOT, "bridges", "__init__.py"), "bridges/__init__.py"),
        (os.path.join(ROOT, "scripts", "corpus_tool_map.json"), "scripts/corpus_tool_map.json"),
        (
            os.path.join(ROOT, "data", "train", "vericut_e_training_v1", "holdout", "vericut_e_training_holdout.jsonl"),
            "data/train/vericut_e_training_v1/holdout/vericut_e_training_holdout.jsonl",
        ),
    ]
    if is_v2:
        optional.extend([
            (os.path.join(PACK_DIR, "start_cloud_train_now.sh"), "start_cloud_train_now.sh"),
            (os.path.join(PACK_DIR, "onboot_cloud_train.sh"), "onboot_cloud_train.sh"),
        ])
    return _pack_vericut_archive(
        archive_path,
        required,
        [(f"{sub_dir}/{sft_ledger_name}", sft_ledger_bytes)],
        optional,
        f"VERICUT96-{version.upper()}",
    )


def _build_vericut_e_bundle(archive_path: str, dataset_arg: Optional[str] = None) -> Tuple[str, str]:
    sft_path = dataset_arg if dataset_arg else os.path.join(PACK_DIR, "dataset", "vericut_e_training_sft.jsonl")
    sft_ledger = os.path.join(PACK_DIR, "dataset", "vericut_e_training_sft_ledger.json")
    dpo_path = os.path.join(PACK_DIR, "dataset", "vericut_e_training_dpo.jsonl")
    if not os.path.exists(sft_path) or not os.path.exists(dpo_path):
        raise SystemExit(f"[FATAL] VERICUT-E 打包缺少语料: sft={sft_path}, dpo={dpo_path}")

    sft_sha = sha256_file(sft_path)
    dpo_sha = sha256_file(dpo_path)
    if not os.path.exists(sft_ledger) or dataset_arg:
        ledger_obj = {
            "schema_version": "1.0",
            "dataset": "vericut_e_training_sft.jsonl",
            "output_sha256": sft_sha,
            "files": {
                "vericut_e_training_sft.jsonl": {"sha256": sft_sha, "size_bytes": os.path.getsize(sft_path)},
                "vericut_e_training_dpo.jsonl": {"sha256": dpo_sha, "size_bytes": os.path.getsize(dpo_path)},
            },
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        ledger_bytes = (json.dumps(ledger_obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    else:
        with open(sft_ledger, "rb") as lf:
            ledger_bytes = lf.read()
        meta = json.loads(ledger_bytes.decode("utf-8"))
        files = meta.get("files", {}) if isinstance(meta, dict) else {}
        exp_sft = str((files.get("vericut_e_training_sft.jsonl") or {}).get("sha256") or meta.get("output_sha256") or "").lower()
        exp_dpo = str((files.get("vericut_e_training_dpo.jsonl") or {}).get("sha256") or "").lower()
        if not exp_sft or exp_sft != sft_sha.lower():
            raise SystemExit(f"[FATAL] VERICUT-E SFT ledger SHA256 不匹配: {exp_sft[:16]} != {sft_sha[:16]}")
        if not exp_dpo or exp_dpo != dpo_sha.lower():
            raise SystemExit(f"[FATAL] VERICUT-E DPO ledger SHA256 不匹配: {exp_dpo[:16]} != {dpo_sha[:16]}")

    required = _vericut_common_files() + [
        (os.path.join(PACK_DIR, "run_vericut_e_training.sh"), "run_vericut_e_training.sh"),
        (sft_path, "dataset/vericut_e_training_sft.jsonl"),
        (dpo_path, "dataset/vericut_e_training_dpo.jsonl"),
    ]
    optional = [
        (os.path.join(ROOT, "bridges", "__init__.py"), "bridges/__init__.py"),
        (os.path.join(ROOT, "scripts", "corpus_tool_map.json"), "scripts/corpus_tool_map.json"),
        (os.path.join(PACK_DIR, "start_cloud_train_now.sh"), "start_cloud_train_now.sh"),
        (os.path.join(PACK_DIR, "onboot_cloud_train.sh"), "onboot_cloud_train.sh"),
        (
            os.path.join(ROOT, "data", "sft", "vericut_e_training", "vericut_e_holdout.jsonl"),
            "data/sft/vericut_e_training/vericut_e_holdout.jsonl",
        ),
    ]
    return _pack_vericut_archive(
        archive_path,
        required,
        [("dataset/vericut_e_training_sft_ledger.json", ledger_bytes)],
        optional,
        "VERICUT-E",
    )


def _build_six_software_bundle(
    archive_path: str,
    dataset_arg: Optional[str] = None,
    version: str = "v1",
) -> Tuple[str, str]:
    is_v2 = version == "v2"
    sft_name = "six_software_v2_sft.jsonl" if is_v2 else "six_software_real_assets_sft.jsonl"
    dpo_name = "six_software_v2_dpo.jsonl" if is_v2 else "six_software_real_assets_dpo.jsonl"
    ledger_name = "six_software_v2_sft_ledger.json" if is_v2 else "six_software_real_assets_sft_ledger.json"
    label = "SIX-SOFTWARE-V2" if is_v2 else "SIX-SOFTWARE"

    sft_path = dataset_arg if dataset_arg else os.path.join(PACK_DIR, "dataset", sft_name)
    ledger_path = os.path.join(PACK_DIR, "dataset", ledger_name)
    dpo_path = os.path.join(PACK_DIR, "dataset", dpo_name)
    if not os.path.exists(sft_path) or not os.path.exists(dpo_path):
        raise SystemExit(f"[FATAL] {label} 打包缺少语料: sft={sft_path}, dpo={dpo_path}")

    sft_sha = sha256_file(sft_path)
    dpo_sha = sha256_file(dpo_path)
    if not os.path.exists(ledger_path) or dataset_arg:
        ledger_obj = {
            "schema_version": "1.0",
            "dataset": sft_name,
            "output_sha256": sft_sha,
            "files": {
                sft_name: {"sha256": sft_sha, "size_bytes": os.path.getsize(sft_path)},
                dpo_name: {"sha256": dpo_sha, "size_bytes": os.path.getsize(dpo_path)},
            },
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        ledger_bytes = (json.dumps(ledger_obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    else:
        with open(ledger_path, "rb") as lf:
            ledger_bytes = lf.read()
        meta = json.loads(ledger_bytes.decode("utf-8"))
        files = meta.get("files", {}) if isinstance(meta, dict) else {}
        exp_sft = str((files.get(sft_name) or {}).get("sha256") or meta.get("output_sha256") or "").lower()
        exp_dpo = str((files.get(dpo_name) or {}).get("sha256") or "").lower()
        if not exp_sft or exp_sft != sft_sha.lower():
            raise SystemExit(f"[FATAL] {label} SFT ledger SHA256 不匹配: {exp_sft[:16]} != {sft_sha[:16]}")
        if not exp_dpo or exp_dpo != dpo_sha.lower():
            raise SystemExit(f"[FATAL] {label} DPO ledger SHA256 不匹配: {exp_dpo[:16]} != {dpo_sha[:16]}")

    required = _vericut_common_files() + [
        (os.path.join(PACK_DIR, "train_vericut_dpo.py"), "train_vericut_dpo.py"),
        (os.path.join(PACK_DIR, "deploy_trained_adapter.py"), "deploy_trained_adapter.py"),
        (os.path.join(PACK_DIR, "run_six_software_real.sh"), "run_six_software_real.sh"),
        (sft_path, f"dataset/{sft_name}"),
        (dpo_path, f"dataset/{dpo_name}"),
    ]
    optional = [
        (os.path.join(ROOT, "bridges", "__init__.py"), "bridges/__init__.py"),
        (os.path.join(ROOT, "scripts", "corpus_tool_map.json"), "scripts/corpus_tool_map.json"),
        (os.path.join(PACK_DIR, "start_cloud_train_now.sh"), "start_cloud_train_now.sh"),
        (os.path.join(PACK_DIR, "onboot_cloud_train.sh"), "onboot_cloud_train.sh"),
        (os.path.join(PACK_DIR, "dataset", f"{sft_name}.sha256"), f"dataset/{sft_name}.sha256"),
        (os.path.join(PACK_DIR, "dataset", f"{dpo_name}.sha256"), f"dataset/{dpo_name}.sha256"),
        (
            os.path.join(ROOT, "data", "sft", "six_software_real_assets", "six_software_holdout.jsonl"),
            "dataset/six_software_holdout.jsonl",
        ),
    ]
    return _pack_vericut_archive(
        archive_path,
        required,
        [(f"dataset/{ledger_name}", ledger_bytes)],
        optional,
        label,
    )


TRACKS: Dict[str, Dict[str, Any]] = {
    "master-8b": {
        "description": "Virtu 8.2B 主力模型 7 阶段硬门禁 SFT 闭环 (Qwen3-8B 非 Instruct)",
        "bundle_path": os.path.join(ROOT, "cloud_train_pack.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_train",
        "runner_sh": "run.sh",
        "background_self": True,
        "log_rel": "train_master.log",
        "receipt_rel": "output/virtu_lora_master/training_receipt.json",
        "deliverable_rel": "output/virtu_lora_master/virtu_lora_deliverable.tar.gz",
        "pgrep_pattern": r"run\.sh|train_turnkey\.py",
        "selftests": [
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
            ["cloud_train_pack/local_one_click.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "run.sh"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
        ],
    },
    "13b": {
        "description": "Virtu 13.63B / Qwen3-14B Phase-2 SFT+DPO 演进闭环",
        "bundle_path": os.path.join(PACK_DIR, "virtu_13b_train_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_13b_train",
        "runner_sh": "cloud_train_pack/run_13b_evolution_train.sh",
        "background_self": False,
        "log_rel": "cloud_train_pack/output_13b/train_13b_console.log",
        "receipt_rel": "cloud_train_pack/output_13b/training_summary.json",
        "deliverable_rel": "",
        "pgrep_pattern": r"run_13b_evolution_train\.sh|train_cloud_virtu_13b\.py",
        "selftests": [
            ["cloud_train_pack/train_cloud_virtu_13b.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_cloud_virtu_13b.py"),
            os.path.join(PACK_DIR, "run_13b_evolution_train.sh"),
        ],
    },
    "all90": {
        "description": "Virtu All-90 全链路 (含 8 道数据门禁 / DPO / 三榜留出验证包)",
        "bundle_path": os.path.join(PACK_DIR, "virtu_all90_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_all90",
        "runner_sh": "run.sh",
        "background_self": True,
        "log_rel": "train_master.log",
        "receipt_rel": "output/virtu_lora_master/training_receipt.json",
        "deliverable_rel": "output/virtu_lora_master/virtu_lora_deliverable.tar.gz",
        "pgrep_pattern": r"run\.sh|train_turnkey\.py|train_dpo_all90\.py",
        "selftests": [
            ["scripts/gate_all90_dataset.py", "--self-test"],
            ["scripts/build_six_holdout_200.py", "--self-test"],
            ["scripts/train_dpo_all90.py", "--self-test"],
            ["scripts/eval_all90_three_boards.py", "--self-test"],
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "run.sh"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "scripts", "train_dpo_all90.py"),
            os.path.join(ROOT, "scripts", "eval_all90_three_boards.py"),
        ],
    },
    "worldmodel": {
        "description": "Virtu 世界工程模型 (WorldModel) 物理/CAD/CAM 六步硬门禁修复线",
        "bundle_path": os.path.join(PACK_DIR, "virtu_worldmodel_fix_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_wm_fix",
        "runner_sh": "run_worldmodel_fix.sh",
        "background_self": False,
        "log_rel": "train_wm.log",
        "receipt_rel": "output/virtu_wm_lora_fix/final_adapter/training_receipt.json",
        "deliverable_rel": "output/virtu_wm_lora_fix/virtu_wm_lora_deliverable.tar.gz",
        "pgrep_pattern": r"run_worldmodel_fix\.sh|train_turnkey_worldmodel\.py",
        "selftests": [],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey_worldmodel.py"),
            os.path.join(PACK_DIR, "run_worldmodel_fix.sh"),
        ],
    },
    "safety": {
        "description": "Virtu 14 类安全边界 SFT+DPO 云端修复线",
        "bundle_path": os.path.join(PACK_DIR, "virtu_safety_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_safety",
        "runner_sh": "cloud_train_pack/run_safety_repair.sh",
        "background_self": False,
        "log_rel": "train_safety.log",
        "receipt_rel": "cloud_train_pack/output/virtu_safety/safety_receipt.json",
        "deliverable_rel": "",
        "pgrep_pattern": r"run_safety_repair\.sh|train_safety_cloud\.py",
        "selftests": [
            ["cloud_train_pack/dataset/build_safety_boundary_sft.py", "--selftest"],
            ["cloud_train_pack/train_safety_cloud.py", "--selftest"],
            ["cloud_train_pack/deploy_safety_repair.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "run_safety_repair.sh"),
            os.path.join(PACK_DIR, "train_safety_cloud.py"),
        ],
    },
    "vericut96": {
        "description": "VERICUT 9.6 (E:\\training) Agent SFT+DPO 云端硬门禁训练线",
        "bundle_path": os.path.join(PACK_DIR, "virtu_vericut96_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_vericut96",
        "runner_sh": "run_vericut96.sh",
        "background_self": True,
        "log_rel": "train_vericut96.log",
        "receipt_rel": "output/virtu_vericut96/training_receipt.json",
        "deliverable_rel": "output/virtu_vericut96/virtu_vericut96_deliverable.tar.gz",
        "pgrep_pattern": r"run_vericut96\.sh|train_turnkey\.py|train_dpo_all90\.py",
        "selftests": [
            ["scripts/build_vericut96_cloud_datasets.py", "--selftest"],
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["scripts/train_dpo_all90.py", "--self-test"],
            ["scripts/gate_all90_dataset.py", "--self-test"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "run_vericut96.sh"),
            os.path.join(PACK_DIR, "dataset", "vericut96_sft_mix.jsonl"),
            os.path.join(PACK_DIR, "dataset", "vericut96_dpo_mix.jsonl"),
            os.path.join(ROOT, "scripts", "train_dpo_all90.py"),
            os.path.join(ROOT, "scripts", "build_vericut96_cloud_datasets.py"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
        ],
    },
    "vericut96-v2": {
        "description": "VERICUT 9.6 v2 (防遗忘坐标系/Auto-Diff/Lamé/G71 SFT+DPO 增强版)",
        "bundle_path": os.path.join(PACK_DIR, "virtu_vericut96_v2_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_vericut96_v2",
        "runner_sh": "run_vericut96.sh",
        "background_self": True,
        "log_rel": "train_vericut96.log",
        "receipt_rel": "output/virtu_vericut96_v2/training_receipt.json",
        "deliverable_rel": "output/virtu_vericut96_v2/virtu_vericut96_v2_deliverable.tar.gz",
        "pgrep_pattern": r"run_vericut96\.sh|train_turnkey\.py|train_dpo_all90\.py",
        "selftests": [
            ["scripts/build_vericut96_cloud_datasets.py", "--selftest"],
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["scripts/train_dpo_all90.py", "--self-test"],
            ["scripts/gate_all90_dataset.py", "--self-test"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "run_vericut96.sh"),
            os.path.join(PACK_DIR, "dataset_v2", "vericut96_v2_sft_mix.jsonl"),
            os.path.join(PACK_DIR, "dataset_v2", "vericut96_v2_dpo_mix.jsonl"),
            os.path.join(ROOT, "scripts", "train_dpo_all90.py"),
            os.path.join(ROOT, "scripts", "build_vericut96_cloud_datasets.py"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
        ],
    },
    "vericut-e": {
        "description": "VERICUT + E:\\training + 五轴涡轮叶片样本反推毛坯 SFT+DPO 云端硬门禁训练线",
        "bundle_path": os.path.join(PACK_DIR, "virtu_vericut_e_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_vericut_e",
        "runner_sh": "run_vericut_e_training.sh",
        "background_self": True,
        "log_rel": "train_vericut_e.log",
        "receipt_rel": "output/virtu_vericut_e/training_receipt.json",
        "deliverable_rel": "output/virtu_vericut_e/virtu_vericut_e_deliverable.tar.gz",
        "pgrep_pattern": r"run_vericut_e_training\.sh|(train_turnkey|train_dpo_all90)\.py.*vericut_e_training|virtu_vericut_e/(scripts/)?(train_turnkey|train_dpo_all90)\.py",
        "selftests": [
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["scripts/train_dpo_all90.py", "--self-test"],
            ["scripts/gate_all90_dataset.py", "--self-test"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "run_vericut_e_training.sh"),
            os.path.join(PACK_DIR, "dataset", "vericut_e_training_sft.jsonl"),
            os.path.join(PACK_DIR, "dataset", "vericut_e_training_dpo.jsonl"),
            os.path.join(PACK_DIR, "dataset", "vericut_e_training_sft_ledger.json"),
            os.path.join(ROOT, "scripts", "train_dpo_all90.py"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
        ],
    },
    "six-software": {
        "description": "六大工业软件真图纸/真数模 (SOLIDWORKS/NX/AutoCAD/CIMCO/VERICUT/SSCNC) 850 SFT + 90 DPO 云端硬门禁训练线",
        "bundle_path": os.path.join(PACK_DIR, "virtu_six_software_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_six_software",
        "runner_sh": "run_six_software_real.sh",
        "background_self": True,
        "log_rel": "train_six_software.log",
        "receipt_rel": "output/six_software_real/training_receipt.json",
        "deliverable_rel": "output/six_software_real/six_software_real_deliverable.tar.gz",
        "pgrep_pattern": r"run_six_software_real\.sh|(train_turnkey|train_vericut_dpo)\.py.*six_software_real_assets|virtu_six_software/(train_turnkey|train_vericut_dpo)\.py",
        "selftests": [
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["cloud_train_pack/train_vericut_dpo.py", "--selftest"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "train_vericut_dpo.py"),
            os.path.join(PACK_DIR, "run_six_software_real.sh"),
            os.path.join(PACK_DIR, "deploy_trained_adapter.py"),
            os.path.join(PACK_DIR, "dataset", "six_software_real_assets_sft.jsonl"),
            os.path.join(PACK_DIR, "dataset", "six_software_real_assets_dpo.jsonl"),
            os.path.join(PACK_DIR, "dataset", "six_software_real_assets_sft_ledger.json"),
            os.path.join(ROOT, "data", "sft", "six_software_real_assets", "six_software_holdout.jsonl"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "scripts", "wm_verifier.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
            os.path.join(ROOT, "bridges", "tool_calling_specs.py"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "virtu_eval", "tool_schema.py"),
        ],
    },
    "six-software-v2": {
        "description": "六大工业软件真图纸/真数模+防遗忘回归修正 v2 (950 SFT + 150 DPO: Lamé/FANUC G71/Auto-Diff/Coord)",
        "bundle_path": os.path.join(PACK_DIR, "virtu_six_software_v2_bundle.tar.gz"),
        "remote_dir": "/root/autodl-tmp/virtu_six_software_v2",
        "runner_sh": "run_six_software_real.sh",
        "background_self": True,
        "log_rel": "train_six_software.log",
        "receipt_rel": "output/six_software_real/training_receipt.json",
        "deliverable_rel": "output/six_software_real/six_software_v2_deliverable.tar.gz",
        "pgrep_pattern": r"virtu_six_software_v2/(run_six_software_real\.sh|train_turnkey\.py|train_vericut_dpo\.py)|(train_turnkey|train_vericut_dpo)\.py.*six_software_v2|run_six_software_real\.sh.*six-software-v2",
        "selftests": [
            ["cloud_train_pack/train_turnkey.py", "--selftest"],
            ["cloud_train_pack/train_vericut_dpo.py", "--selftest"],
            ["cloud_train_pack/deploy_trained_adapter.py", "--selftest"],
        ],
        "source_deps": [
            os.path.join(PACK_DIR, "train_turnkey.py"),
            os.path.join(PACK_DIR, "train_vericut_dpo.py"),
            os.path.join(PACK_DIR, "run_six_software_real.sh"),
            os.path.join(PACK_DIR, "deploy_trained_adapter.py"),
            os.path.join(PACK_DIR, "dataset", "six_software_v2_sft.jsonl"),
            os.path.join(PACK_DIR, "dataset", "six_software_v2_dpo.jsonl"),
            os.path.join(PACK_DIR, "dataset", "six_software_v2_sft_ledger.json"),
            os.path.join(ROOT, "data", "sft", "six_software_real_assets", "six_software_holdout.jsonl"),
            os.path.join(ROOT, "scripts", "gate_all90_dataset.py"),
            os.path.join(ROOT, "scripts", "wm_verifier.py"),
            os.path.join(ROOT, "scripts", "corpus_unit_audit.py"),
            os.path.join(ROOT, "bridges", "tool_calling_specs.py"),
            os.path.join(ROOT, "virtu_eval", "contamination_check.py"),
            os.path.join(ROOT, "virtu_eval", "tool_schema.py"),
        ],
    },
}


def parse_ssh_command(ssh_cmd: str) -> Dict[str, Any]:
    """解析常见云主机 SSH 登录命令 (如 'ssh -p 40526 root@cn-north-b.ssh.damodel.com')。"""
    import re
    import shlex

    raw = (ssh_cmd or "").strip()
    if not raw:
        raise ValueError("empty ssh_cmd")
    for bad in (";", "&&", "||", "|", "`", "$(", "\n", "\r", "<", ">"):
        if bad in raw:
            raise ValueError(f"disallowed token in ssh_cmd: {bad!r}")

    tokens = shlex.split(raw)
    if tokens and tokens[0].lower() in ("ssh", "ssh.exe"):
        tokens = tokens[1:]
    if not tokens:
        raise ValueError("missing target host in ssh_cmd")

    port_val: Optional[int] = None
    user_val: Optional[str] = None
    target_tok: Optional[str] = None
    flags_with_arg = set("-i -l -o -F -J -W -b -c -E -I -L -m -O -Q -R -S -w -p".split())

    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "-p":
            if idx + 1 >= len(tokens):
                raise ValueError("missing port after -p")
            port_val = int(tokens[idx + 1])
            idx += 2
            continue
        if tok.startswith("-p") and len(tok) > 2:
            port_val = int(tok[2:])
            idx += 1
            continue
        if tok == "-l":
            if idx + 1 >= len(tokens):
                raise ValueError("missing user after -l")
            user_val = tokens[idx + 1].strip() or None
            idx += 2
            continue
        if tok in flags_with_arg:
            idx += 2
            continue
        if tok.startswith("-"):
            idx += 1
            continue
        if target_tok is not None:
            raise ValueError(f"unexpected extra positional token in ssh_cmd: {tok!r}")
        target_tok = tok
        idx += 1

    if not target_tok:
        raise ValueError("missing host target in ssh_cmd")

    if "@" in target_tok:
        u_part, h_part = target_tok.split("@", 1)
        if u_part.strip() and not user_val:
            user_val = u_part.strip()
    else:
        h_part = target_tok

    if ":" in h_part:
        h_only, p_part = h_part.rsplit(":", 1)
        if not p_part.isdigit():
            raise ValueError(f"invalid host:port target: {h_part!r}")
        if port_val is None:
            port_val = int(p_part)
        h_part = h_only

    h_part = h_part.strip()
    if not h_part or h_part.startswith("-") or not re.fullmatch(r"[A-Za-z0-9._-]+", h_part):
        raise ValueError(f"invalid hostname: {h_part!r}")
    if port_val is not None and not (1 <= port_val <= 65535):
        raise ValueError(f"port out of range: {port_val}")

    return {"host": h_part, "port": port_val, "user": user_val}


def resolve_cloud_credentials(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    ssh_cmd: Optional[str] = None,
    creds_file: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """按 CLI -> 环境变量 -> 本地 JSON 文件优先级解析云端 SSH 凭据，源码零硬编码密钥。"""
    env_map = env if env is not None else os.environ
    file_creds: Dict[str, Any] = {}
    cand_file = creds_file or os.path.join(PACK_DIR, ".cloud_creds.json")
    if cand_file and os.path.exists(cand_file):
        with open(cand_file, "r", encoding="utf-8") as cf:
            loaded = json.load(cf)
            if isinstance(loaded, dict):
                file_creds = loaded

    def _safe_parse(cmd_str: Optional[str], src_name: str) -> Dict[str, Any]:
        s = (cmd_str or "").strip()
        if not s:
            return {}
        try:
            return parse_ssh_command(s)
        except Exception as exc:
            raise SystemExit(f"[FATAL] {src_name} 解析失败: {exc}")

    cli_ssh = _safe_parse(ssh_cmd, "--ssh-cmd")
    env_ssh = _safe_parse(
        env_map.get("DAMODEL_SSH_CMD") or env_map.get("CLOUD_SSH_CMD"),
        "DAMODEL_SSH_CMD/CLOUD_SSH_CMD",
    )
    file_ssh = _safe_parse(str(file_creds.get("ssh_cmd", "")), "creds.ssh_cmd")

    resolved_host = (
        host
        or cli_ssh.get("host")
        or env_map.get("DAMODEL_HOST")
        or env_map.get("CLOUD_SSH_HOST")
        or env_ssh.get("host")
        or str(file_creds.get("host", "")).strip()
        or file_ssh.get("host")
        or ""
    )
    port_raw = (
        port
        if port is not None
        else (
            cli_ssh.get("port")
            or env_map.get("DAMODEL_PORT")
            or env_map.get("CLOUD_SSH_PORT")
            or env_ssh.get("port")
            or file_creds.get("port")
            or file_ssh.get("port")
            or 22
        )
    )
    resolved_port = int(port_raw)
    resolved_user = (
        user
        or cli_ssh.get("user")
        or env_map.get("DAMODEL_USER")
        or env_map.get("CLOUD_SSH_USER")
        or env_ssh.get("user")
        or str(file_creds.get("user", "")).strip()
        or file_ssh.get("user")
        or "root"
    )
    resolved_password = (
        password
        or env_map.get("DAMODEL_PASS")
        or env_map.get("DAMODEL_PW")
        or env_map.get("CLOUD_SSH_PASS")
        or str(file_creds.get("password", "")).strip()
    )
    return {
        "host": resolved_host,
        "port": resolved_port,
        "user": resolved_user,
        "password": resolved_password,
    }


def run_track_selftests(track: str, python_exe: Optional[str] = None) -> List[str]:
    cfg = TRACKS[track]
    py = python_exe or sys.executable
    executed: List[str] = []
    for cmd_rel in cfg["selftests"]:
        script_abs = os.path.join(ROOT, cmd_rel[0])
        if not os.path.exists(script_abs):
            raise SystemExit(f"[FATAL] 自检脚本不存在: {script_abs}")
        full_cmd = [py, script_abs, *cmd_rel[1:]]
        proc = subprocess.run(full_cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            raise SystemExit(
                f"[FATAL] 预检自检失败 ({' '.join(cmd_rel)} rc={proc.returncode}):\n"
                f"{proc.stdout}\n{proc.stderr}"
            )
        executed.append(" ".join(cmd_rel))
    return executed


def _bundle_is_fresh(bundle_path: str, source_deps: List[str]) -> bool:
    ok, _ = _verify_local_archive_sha(bundle_path)
    if not ok:
        return False
    b_mtime = os.path.getmtime(bundle_path)
    for dep in source_deps:
        if os.path.exists(dep) and os.path.getmtime(dep) > b_mtime:
            return False
    return True


def prepare_track_bundle(
    track: str,
    *,
    repack: bool = False,
    dataset_arg: Optional[str] = None,
) -> Dict[str, Any]:
    if track not in TRACKS:
        raise SystemExit(f"[FATAL] 未知产线 track={track!r}，可选: {', '.join(TRACKS)}")
    cfg = TRACKS[track]
    bundle_path = cfg["bundle_path"]
    source_deps = cfg.get("source_deps", [])

    if not repack and not dataset_arg and _bundle_is_fresh(bundle_path, source_deps):
        sha = sha256_file(bundle_path)
        size_mb = os.path.getsize(bundle_path) / (1024 ** 2)
        print(f"[Pack] 命中最新预打包件（0s 跳过重打）: {bundle_path} ({size_mb:.2f} MB | sha256={sha[:16]}...)")
        return {"bundle_path": bundle_path, "sha256": sha, "reused": True, "size_mb": size_mb}

    if track == "master-8b":
        arc, sha = local_one_click.make_master_bundle(archive_path=bundle_path, dataset_arg=dataset_arg)
    elif track == "13b":
        arc, sha = _build_13b_bundle(bundle_path, dataset_arg=dataset_arg)
    elif track == "all90":
        arc, sha = _build_all90_bundle(bundle_path, dataset_arg=dataset_arg)
    elif track == "worldmodel":
        meta = local_one_click_worldmodel.make_worldmodel_bundle(bundle_path)
        arc = bundle_path
        sha = meta["bundle_sha256"] if isinstance(meta, dict) and "bundle_sha256" in meta else sha256_file(bundle_path)
        if not os.path.exists(arc + ".sha256"):
            _write_sha256_sidecar(arc)
    elif track == "safety":
        arc, sha = _build_safety_bundle(bundle_path, dataset_arg=dataset_arg)
    elif track == "vericut96":
        arc, sha = _build_vericut96_bundle(bundle_path, dataset_arg=dataset_arg, version="v1")
    elif track == "vericut96-v2":
        arc, sha = _build_vericut96_bundle(bundle_path, dataset_arg=dataset_arg, version="v2")
    elif track == "vericut-e":
        arc, sha = _build_vericut_e_bundle(bundle_path, dataset_arg=dataset_arg)
    elif track == "six-software":
        arc, sha = _build_six_software_bundle(bundle_path, dataset_arg=dataset_arg, version="v1")
    elif track == "six-software-v2":
        arc, sha = _build_six_software_bundle(bundle_path, dataset_arg=dataset_arg, version="v2")
    else:
        raise SystemExit(f"[FATAL] 未实现的打包产线: {track}")

    ok, detail = _verify_local_archive_sha(arc)
    if not ok:
        raise SystemExit(f"[FATAL] 本地打包校验失败 ({arc}): {detail}")
    size_mb = os.path.getsize(arc) / (1024 ** 2)
    return {"bundle_path": arc, "sha256": sha, "reused": False, "size_mb": size_mb}


def probe_tcp_once(host: str, port: int, timeout: float = 3.0) -> Tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        err = sock.connect_ex((host, int(port)))
        if err == 0:
            return True, "tcp_open"
        return False, f"connect_ex={err}"
    except OSError as exc:
        return False, f"{type(exc).__name__}:{exc}"
    finally:
        sock.close()


def wait_for_instance_online(
    host: str,
    port: int,
    user: str,
    password: str,
    *,
    wait_online_seconds: float = 300.0,
    poll_interval: float = 3.0,
    tcp_probe_fn: Callable[[str, int, float], Tuple[bool, str]] = probe_tcp_once,
) -> Tuple[Any, str]:
    """轮询 TCP + SSH 直至云端 GPU 实例上线并响应 nvidia-smi。"""
    if not host:
        raise SystemExit("[FATAL] 缺少 --host 或环境变量 DAMODEL_HOST")
    if not password:
        raise SystemExit("[FATAL] 缺少 --password 或环境变量 DAMODEL_PASS")

    paramiko = local_one_click._ensure_paramiko()
    wait_forever = wait_online_seconds < 0.0
    deadline = None if wait_forever else (time.monotonic() + max(0.0, wait_online_seconds))
    attempt = 0

    while True:
        attempt += 1
        tcp_ok, tcp_msg = tcp_probe_fn(host, port, 3.0)
        if tcp_ok:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(hostname=host, port=port, username=user, password=password, timeout=15)
                _, out_s, err_s = client.exec_command(
                    "echo READY && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"
                )
                rc = out_s.channel.recv_exit_status()
                out_txt = out_s.read().decode("utf-8", errors="replace").strip()
                err_txt = err_s.read().decode("utf-8", errors="replace").strip()
                if rc == 0 and "READY" in out_txt:
                    print(f"[Online] SSH + GPU 已就绪 ({user}@{host}:{port}, attempt={attempt}):\n{out_txt}")
                    return client, out_txt
                last_err = f"gpu_probe_rc={rc} {err_txt or out_txt}"
                client.close()
            except Exception as exc:
                last_err = f"{type(exc).__name__}:{exc}"
                try:
                    client.close()
                except Exception:
                    pass
        else:
            last_err = tcp_msg

        now = time.monotonic()
        if wait_online_seconds == 0.0 or (deadline is not None and now >= deadline):
            raise SystemExit(
                f"[FATAL] 等待实例上线超时 ({host}:{port}, wait={wait_online_seconds}s, attempts={attempt}): {last_err}"
            )
        if deadline is None:
            print(f"  [WaitOnline #{attempt}] {host}:{port} 尚未就绪 ({last_err})，{poll_interval:.0f}s 后重试 (持续等待开机上线) ...")
            time.sleep(max(0.1, poll_interval))
        else:
            remaining = int(max(0.0, deadline - now))
            print(f"  [WaitOnline #{attempt}] {host}:{port} 尚未就绪 ({last_err})，{poll_interval:.0f}s 后重试 (剩余 {remaining}s) ...")
            time.sleep(min(poll_interval, max(0.1, deadline - time.monotonic())))


def evaluate_startup_state(
    ps_out: str,
    gpu_mem_mb: float,
    log_tail: str,
    *,
    elapsed_s: float = 0.0,
    boot_grace_s: float = 20.0,
) -> Dict[str, str]:
    """纯函数可证伪启动双证门：进程存活 + (显存>=2000MiB 或进入训练阶段) 才判 STARTED。"""
    active_marker = find_active_fatal_marker(log_tail)
    if active_marker:
        return {"state": "FATAL", "reason": f"fatal_marker:{active_marker}"}

    alive = bool(ps_out.strip())
    stage_active = any(m in log_tail for m in STARTED_LOG_MARKERS)

    if alive and (gpu_mem_mb >= 2000.0 or stage_active):
        return {
            "state": "STARTED",
            "reason": f"alive_vram_{int(gpu_mem_mb)}mb" if gpu_mem_mb >= 2000.0 else "alive_stage_active",
        }
    if not alive:
        if "COMPLETED" in log_tail or "[Stage7] PASS" in log_tail:
            return {"state": "STARTED", "reason": "completed_fast"}
        if elapsed_s >= boot_grace_s:
            return {"state": "FATAL", "reason": "process_exited_without_completion"}
        return {"state": "BOOTING", "reason": "awaiting_process_spawn"}
    return {"state": "BOOTING", "reason": f"initializing_vram_{int(gpu_mem_mb)}mb"}


def evaluate_health_tick(
    ps_alive: bool,
    log_tail: str,
    receipt_json: Optional[Dict[str, Any]],
    gpu_util_pct: float,
    seconds_since_step_advance: float,
    *,
    max_stall_seconds: float = 420.0,
) -> Dict[str, str]:
    """纯函数可证伪健康巡检判定器：拒绝空转/静默超时/僵尸进程。"""
    if receipt_json is not None:
        status = str(receipt_json.get("status", "")).strip()
        if status == "COMPLETED":
            return {"action": "COMPLETED", "reason": "receipt_completed"}
        if status == "TIME_BUDGET_STOPPED":
            return {"action": "TIME_BUDGET_STOPPED", "reason": "time_budget_stopped_not_deliverable"}
        if status in ("FAILED", "ERROR"):
            return {"action": "FATAL", "reason": f"receipt_status={status}"}

    active_marker = find_active_fatal_marker(log_tail)
    if active_marker:
        return {"action": "FATAL", "reason": f"fatal_marker:{active_marker}"}

    if seconds_since_step_advance >= max_stall_seconds and gpu_util_pct < 10.0:
        return {
            "action": "STALLED",
            "reason": f"no_step_progress_{int(seconds_since_step_advance)}s_gpu_util_{gpu_util_pct:.1f}%",
        }

    if not ps_alive:
        return {"action": "FATAL", "reason": "process_dead_without_completed_receipt"}

    return {"action": "HEALTHY", "reason": "training_progressing"}


def _extract_latest_step(log_tail: str) -> Optional[int]:
    latest: Optional[int] = None
    for m in STEP_RE.finditer(log_tail):
        val = m.group(1) or m.group(2)
        if val:
            latest = int(val)
    return latest


def _query_remote_gpu_metrics(client, gpu_id: Optional[str] = None) -> Tuple[float, float]:
    gpu_flag = ""
    if gpu_id is not None and str(gpu_id).strip():
        gpu_flag = f"-i {shlex.quote(str(gpu_id).strip())} "
    _, out_s, _ = client.exec_command(
        f"nvidia-smi {gpu_flag}--query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo '0, 0'"
    )
    raw = out_s.read().decode("utf-8", errors="replace").strip().splitlines()
    if not raw:
        return 0.0, 0.0
    mems: List[float] = []
    utils: List[float] = []
    for line in raw:
        parts = [p.strip() for p in line.split(",")]
        try:
            mems.append(float(parts[0]))
        except Exception:
            pass
        if len(parts) > 1:
            try:
                utils.append(float(parts[1]))
            except Exception:
                pass
    mem = max(mems) if mems else 0.0
    util = max(utils) if utils else 0.0
    return mem, util


def upload_and_launch_remote(
    client,
    track: str,
    bundle_path: str,
    *,
    remote_dir: Optional[str] = None,
    max_hours: float = 1.5,
    epochs: float = 2.0,
    lr: float = 1.5e-4,
    qlora: bool = False,
    skip_smoke: bool = False,
    base_arg: Optional[str] = None,
    gpu_id: Optional[str] = None,
    attach_if_running: bool = True,
) -> Dict[str, Any]:
    cfg = TRACKS[track]
    rdir = remote_dir or cfg["remote_dir"]
    rdir_q = shlex.quote(rdir)
    pgrep_pat = cfg["pgrep_pattern"]

    _, p_out, _ = client.exec_command(f"pgrep -f {shlex.quote(pgrep_pat)} || true")
    existing_pids = p_out.read().decode("utf-8", errors="replace").strip()
    if existing_pids and attach_if_running:
        print(f"[Launch] 检测到远端已有同产线进程存活 (PID={existing_pids.replace(chr(10), ',')})，直接附着看门狗！")
        return {"attached": True, "pids": existing_pids, "remote_dir": rdir}

    bundle_name = os.path.basename(bundle_path)
    sha_name = bundle_name + ".sha256"
    print(f"[Upload] 创建 {rdir} 并上传 {bundle_name} + .sha256 ...")
    local_one_click._exec_checked(client, f"mkdir -p {rdir_q}", "创建远端工作目录")

    sftp = client.open_sftp()
    try:
        sftp.put(bundle_path, f"{rdir}/{bundle_name}")
        sftp.put(bundle_path + ".sha256", f"{rdir}/{sha_name}")
    finally:
        sftp.close()

    local_one_click._exec_checked(
        client,
        (
            f"cd {rdir_q} && sed -i 's/\\r$//' {shlex.quote(sha_name)} && "
            f"sha256sum -c {shlex.quote(sha_name)} && "
            f"tar -zxf {shlex.quote(bundle_name)} && "
            f"find . -maxdepth 2 -name '*.sh' -exec sed -i 's/\\r$//' {{}} + -exec chmod +x {{}} +"
        ),
        "远端 SHA256 校验与解包",
    )

    runner = cfg["runner_sh"]
    log_rel = cfg["log_rel"]
    extra_flags: List[str] = []
    if track in ("master-8b", "all90", "vericut96", "vericut96-v2", "vericut-e", "six-software", "six-software-v2"):
        extra_flags = [
            f"--max-hours {shlex.quote(str(max_hours))}",
            f"--epochs {shlex.quote(str(epochs))}",
            f"--lr {shlex.quote(str(lr))}",
        ]
        if skip_smoke:
            extra_flags.append("--skip-smoke")
        if qlora:
            extra_flags.append("--qlora")
        if base_arg:
            extra_flags.append(f"--base {shlex.quote(base_arg)}")
        if gpu_id is not None and str(gpu_id).strip():
            extra_flags.append(f"--gpu-id {shlex.quote(str(gpu_id).strip())}")
        if track == "six-software-v2":
            extra_flags.extend([
                "--sft-data dataset/six_software_v2_sft.jsonl",
                "--dpo-data dataset/six_software_v2_dpo.jsonl",
                "--ledger dataset/six_software_v2_sft_ledger.json",
                "--deliverable-name six_software_v2_deliverable.tar.gz",
                "--track six-software-v2",
            ])
    elif track == "13b":
        extra_flags = [
            "--stage all",
            f"--epochs {shlex.quote(str(epochs))}",
            f"--lr {shlex.quote(str(lr))}",
            f"--max-hours {shlex.quote(str(max_hours))}",
        ]
        if base_arg:
            extra_flags.append(f"--base {shlex.quote(base_arg)}")
    elif track == "safety":
        extra_flags = [f"--max-hours={shlex.quote(str(max_hours))}"]
        if base_arg:
            extra_flags.append(f"--base={shlex.quote(base_arg)}")

    flag_str = " ".join(extra_flags)
    if cfg["background_self"]:
        cmd = f"cd {rdir_q} && rm -f {shlex.quote(log_rel)} && bash {shlex.quote(runner)} {flag_str}"
    else:
        log_dir = os.path.dirname(log_rel)
        mkdir_log = f"mkdir -p {shlex.quote(log_dir)} && " if log_dir else ""
        cmd = (
            f"cd {rdir_q} && {mkdir_log}"
            f"nohup bash {shlex.quote(runner)} {flag_str} > {shlex.quote(log_rel)} 2>&1 < /dev/null & "
            f"echo LAUNCHED_PID=$!"
        )

    print(f"[Launch] 立即启动云端训练: {runner} {flag_str}")
    launch_out = local_one_click._exec_checked(client, cmd, f"启动 {runner}")
    print("  ->", launch_out.strip())
    return {"attached": False, "launch_out": launch_out.strip(), "remote_dir": rdir}


def verify_training_started(
    client,
    track: str,
    remote_dir: str,
    *,
    timeout_s: float = 120.0,
    poll_s: float = 5.0,
    gpu_id: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = TRACKS[track]
    rdir_q = shlex.quote(remote_dir)
    log_q = shlex.quote(f"{remote_dir}/{cfg['log_rel']}")
    pgrep_q = shlex.quote(cfg["pgrep_pattern"])
    start_t = time.monotonic()

    gpu_label = f"GPU {gpu_id}" if (gpu_id is not None and str(gpu_id).strip()) else "GPU"
    print(f"[Watchdog-1] 验证启动双证门 (进程存活 + {gpu_label} 显存 >= 2000 MiB / 进入阶段, timeout={int(timeout_s)}s) ...")
    while True:
        elapsed = time.monotonic() - start_t
        _, p_out, _ = client.exec_command(f"pgrep -f {pgrep_q} || true")
        ps_out = p_out.read().decode("utf-8", errors="replace").strip()
        _, l_out, _ = client.exec_command(f"tail -n 60 {log_q} 2>/dev/null || true")
        log_tail = l_out.read().decode("utf-8", errors="replace")
        mem_mb, util_pct = _query_remote_gpu_metrics(client, gpu_id=gpu_id)

        res = evaluate_startup_state(ps_out, mem_mb, log_tail, elapsed_s=elapsed)
        if res["state"] == "FATAL":
            raise SystemExit(
                f"[FATAL] 启动双证门拦截 ({res['reason']}):\n--- 远端日志尾部 ---\n{log_tail}"
            )
        if res["state"] == "STARTED":
            marker_dir = os.path.join(ROOT, "runs")
            os.makedirs(marker_dir, exist_ok=True)
            marker_path = os.path.join(marker_dir, f"cloud_train_started_{track}.marker")
            with open(marker_path, "w", encoding="utf-8") as mf:
                json.dump(
                    {
                        "track": track,
                        "remote_dir": remote_dir,
                        "gpu_id": gpu_id,
                        "pids": ps_out.splitlines(),
                        "gpu_mem_mb": mem_mb,
                        "gpu_util_pct": util_pct,
                        "reason": res["reason"],
                        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    mf,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"[Watchdog-1] PASS ({res['reason']}): PIDs={ps_out.replace(chr(10), ',') or 'done'} | {gpu_label} VRAM={mem_mb:.0f} MiB | marker={marker_path}")
            return {"status": "STARTED", "marker": marker_path, "gpu_mem_mb": mem_mb}

        if elapsed >= timeout_s:
            raise SystemExit(
                f"[FATAL] {int(timeout_s)}s 内未达到启动双证门 ({res['reason']}):\n--- 远端日志尾部 ---\n{log_tail}"
            )
        print(f"  -> {int(elapsed)}s: {res['state']} ({res['reason']}) | GPU={mem_mb:.0f} MiB, util={util_pct:.0f}%")
        time.sleep(poll_s)


def _read_remote_receipt(client, remote_dir: str, receipt_rel: str) -> Optional[Dict[str, Any]]:
    if not receipt_rel:
        return None
    full = shlex.quote(f"{remote_dir}/{receipt_rel}")
    _, out_s, _ = client.exec_command(f"cat {full} 2>/dev/null || true")
    raw = out_s.read().decode("utf-8", errors="replace").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def watch_training_health(
    client,
    track: str,
    remote_dir: str,
    *,
    poll_s: float = 20.0,
    max_stall_seconds: float = 420.0,
    gpu_id: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = TRACKS[track]
    log_q = shlex.quote(f"{remote_dir}/{cfg['log_rel']}")
    pgrep_q = shlex.quote(cfg["pgrep_pattern"])

    last_step: Optional[int] = None
    last_advance_t = time.monotonic()
    last_printed_line = ""

    print(f"[Watchdog-2] 开启健康巡检与防卡死监控 (poll={int(poll_s)}s, stall_limit={int(max_stall_seconds)}s) ...")
    while True:
        _, p_out, _ = client.exec_command(f"pgrep -f {pgrep_q} || true")
        ps_alive = bool(p_out.read().decode("utf-8", errors="replace").strip())
        _, l_out, _ = client.exec_command(f"tail -n 60 {log_q} 2>/dev/null || true")
        log_tail = l_out.read().decode("utf-8", errors="replace")
        mem_mb, util_pct = _query_remote_gpu_metrics(client, gpu_id=gpu_id)
        receipt = _read_remote_receipt(client, remote_dir, cfg["receipt_rel"])

        cur_step = _extract_latest_step(log_tail)
        now = time.monotonic()
        if cur_step is not None and (last_step is None or cur_step > last_step):
            last_step = cur_step
            last_advance_t = now
        elif util_pct >= 10.0:
            # GPU 仍处于计算负载中，重置步进静默计时以免大 batch/eval 阶段误报
            last_advance_t = now

        tick = evaluate_health_tick(
            ps_alive,
            log_tail,
            receipt,
            util_pct,
            now - last_advance_t,
            max_stall_seconds=max_stall_seconds,
        )
        non_empty = [ln for ln in log_tail.splitlines() if ln.strip()]
        newest = non_empty[-1] if non_empty else ""
        if newest != last_printed_line:
            print(f"  [Health] step={cur_step} | VRAM={mem_mb:.0f}MiB util={util_pct:.0f}% | {newest[:120]}")
            last_printed_line = newest

        action = tick["action"]
        if action == "COMPLETED":
            print(f"[Watchdog-2] SUCCESS: 检测到收据 status=COMPLETED！")
            return {"status": "COMPLETED", "receipt": receipt}
        if action in ("TIME_BUDGET_STOPPED", "FATAL", "STALLED"):
            raise SystemExit(
                f"[FATAL] 看门狗停机 action={action} ({tick['reason']})\n--- 日志尾部 ---\n{log_tail}"
            )
        time.sleep(poll_s)


def pull_and_optional_deploy(
    client,
    track: str,
    remote_dir: str,
    *,
    auto_deploy: bool = False,
    deploy_tag: str = "virtu-master-fixed:latest",
    base_dir: Optional[str] = None,
) -> Optional[str]:
    cfg = TRACKS[track]
    deliv_rel = cfg.get("deliverable_rel", "")
    if not deliv_rel:
        print(f"[Pull] track={track} 无统一 tar.gz 交付件映射，请按训练日志指引查看 {remote_dir}")
        return None

    remote_tar = f"{remote_dir}/{deliv_rel}"
    remote_sha = remote_tar + ".sha256"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    pull_dir = os.path.join(ROOT, "runs", f"cloud_pull_{track}_{stamp}")
    os.makedirs(pull_dir, exist_ok=True)
    local_tar = os.path.join(pull_dir, os.path.basename(remote_tar))
    local_sha = local_tar + ".sha256"

    sftp = client.open_sftp()
    try:
        sftp.get(remote_tar, local_tar)
        sftp.get(remote_sha, local_sha)
    finally:
        sftp.close()

    ok, detail = _verify_local_archive_sha(local_tar)
    if not ok:
        raise SystemExit(f"[FATAL] 拉取交付包 SHA256 校验失败: {detail}")

    unpack_dir = os.path.join(pull_dir, "unpacked")
    with tarfile.open(local_tar, "r:gz") as tar:
        local_one_click.safe_extract(tar, unpack_dir)

    if track in ("master-8b", "all90", "vericut96", "vericut96-v2", "vericut-e", "six-software", "six-software-v2"):
        rdata = local_one_click.verify_deliverable_receipt(unpack_dir)
    elif track == "worldmodel":
        rdata = local_one_click_worldmodel.verify_deliverable_receipt(unpack_dir)
    else:
        rdata = {"status": "COMPLETED"}

    print(f"[Pull] SHA256 与 Receipt 双验通过 -> {local_tar} (status={rdata.get('status')})")

    if auto_deploy:
        if track in ("master-8b", "all90", "vericut96", "vericut96-v2", "vericut-e", "six-software", "six-software-v2"):
            cmd = [
                sys.executable,
                os.path.join(PACK_DIR, "deploy_trained_adapter.py"),
                "--deliverable",
                local_tar,
                "--tag",
                deploy_tag,
            ]
            if base_dir and os.path.isdir(base_dir):
                cmd.extend(["--base", base_dir])
            elif base_dir:
                print(f"[AutoDeploy] 跳过远端基座路径 {base_dir!r}，改用本地自动基座探测 ...")
            print(f"[AutoDeploy] 执行真融合部署: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=ROOT, check=True)
        elif track == "worldmodel":
            post_script = os.path.join(ROOT, "scripts", "_post_train_worldmodel.py")
            if os.path.exists(post_script):
                subprocess.run([sys.executable, post_script], cwd=ROOT, check=True)
    return local_tar


def run_selftest() -> int:
    """零 SSH 离线全链路自检：凭据优先级、启动双证门、420s 假死与伪完成拦截、SHA256 校验。"""
    with tempfile.TemporaryDirectory(prefix="virtu_start_now_selftest_") as td:
        # 1. 凭据解析优先级：CLI > ENV > JSON，且不含硬编码密钥
        creds_p = os.path.join(td, "creds.json")
        with open(creds_p, "w", encoding="utf-8") as cf:
            json.dump({"host": "json-host", "port": 2200, "user": "json-u", "password": "placeholder"}, cf)
        c_file = resolve_cloud_credentials(creds_file=creds_p, env={})
        assert c_file == {"host": "json-host", "port": 2200, "user": "json-u", "password": "placeholder"}
        c_env = resolve_cloud_credentials(
            creds_file=creds_p,
            env={"DAMODEL_HOST": "env-host", "DAMODEL_PORT": "40526", "DAMODEL_PASS": "redacted"},
        )
        assert c_env["host"] == "env-host" and c_env["port"] == 40526 and c_env["password"] == "redacted"
        c_cli = resolve_cloud_credentials(
            host="cli-host", port=30001, password="changeme",
            creds_file=creds_p,
            env={"DAMODEL_HOST": "env-host", "DAMODEL_PORT": "40526", "DAMODEL_PASS": "redacted"},
        )
        assert c_cli["host"] == "cli-host" and c_cli["port"] == 30001 and c_cli["password"] == "changeme"

        # 2. evaluate_startup_state 可证伪状态机
        assert evaluate_startup_state("1234", 12500.0, "Stage 4 smoke ok")["state"] == "STARTED"
        assert evaluate_startup_state("1234", 350.0, "loading weights")["state"] == "BOOTING"
        assert evaluate_startup_state("1234", 12500.0, "[FATAL] wrong base model")["state"] == "FATAL"
        assert evaluate_startup_state("1234", 12500.0, "Traceback (most recent call last):\nOSError")["state"] == "FATAL"
        assert evaluate_startup_state("", 0.0, "starting", elapsed_s=30.0)["state"] == "FATAL"

        # 3. evaluate_health_tick 可证伪巡检判定
        assert evaluate_health_tick(True, "step 120", None, 95.0, 10.0)["action"] == "HEALTHY"
        assert evaluate_health_tick(True, "step 120", None, 2.0, 425.0)["action"] == "STALLED"
        assert evaluate_health_tick(True, "done", {"status": "TIME_BUDGET_STOPPED"}, 0.0, 5.0)["action"] == "TIME_BUDGET_STOPPED"
        assert evaluate_health_tick(False, "killed", None, 0.0, 5.0)["action"] == "FATAL"
        assert evaluate_health_tick(False, "all done", {"status": "COMPLETED"}, 0.0, 0.0)["action"] == "COMPLETED"

        # 4. wait_for_instance_online fail-fast 超时拦截（无网络阻塞）
        try:
            wait_for_instance_online(
                "127.0.0.1",
                59999,
                "root",
                "pw",
                wait_online_seconds=0.0,
                tcp_probe_fn=lambda _h, _p, _t: (False, "refused"),
            )
            raise AssertionError("wait_for_instance_online 未拦截超时")
        except SystemExit:
            pass

        # 5. SHA256 伴随校验可证伪探针
        fake_tar = os.path.join(td, "fake.tar.gz")
        with open(fake_tar, "wb") as f:
            f.write(b"virtu-bundle-bytes")
        sha = _write_sha256_sidecar(fake_tar)
        ok, act = _verify_local_archive_sha(fake_tar)
        assert ok and act == sha
        with open(fake_tar + ".sha256", "w", encoding="utf-8") as sf:
            sf.write("0" * 64 + "  fake.tar.gz\n")
        bad_ok, _ = _verify_local_archive_sha(fake_tar)
        assert not bad_ok

        # 6. SSH 命令解析 + 多产线串联校验（含反向注入拒绝）
        parsed_a = parse_ssh_command("ssh -p 40526 root@cn-north-b.ssh.damodel.com")
        assert parsed_a == {"host": "cn-north-b.ssh.damodel.com", "port": 40526, "user": "root"}
        parsed_b = parse_ssh_command("ssh -o StrictHostKeyChecking=no ubuntu@10.2.3.4 -p2222")
        assert parsed_b == {"host": "10.2.3.4", "port": 2222, "user": "ubuntu"}
        for bad_cmd in ("", "ssh root@host; rm -rf /", "ssh -p 99999 root@host"):
            try:
                parse_ssh_command(bad_cmd)
                raise AssertionError(f"parse_ssh_command 未拦截非法输入: {bad_cmd!r}")
            except ValueError:
                pass
        c_ssh = resolve_cloud_credentials(
            ssh_cmd="ssh -p 31022 root@gpu-1.local",
            password="pw",
            creds_file=creds_p,
            env={},
        )
        assert c_ssh == {"host": "gpu-1.local", "port": 31022, "user": "root", "password": "pw"}
        assert resolve_track_list("master-8b", "vericut96-v2, vericut-e, six-software") == [
            "vericut96-v2",
            "vericut-e",
            "six-software",
        ]
        try:
            resolve_track_list("master-8b", "nonexistent-track")
            raise AssertionError("resolve_track_list 未拦截未知产线")
        except SystemExit:
            pass

    print("[SELFTEST] PASS: creds_priority / ssh_cmd_parse / startup_dual_proof / health_stall_gate / tcp_timeout / sha256_verify")
    return 0


_DEFAULT_DEPLOY_TAGS: Dict[str, str] = {
    "six-software": "virtu-six-software:v1",
    "six-software-v2": "virtu-six-software:v2",
    "vericut96-v2": "virtu-vericut96:v2",
    "vericut96": "virtu-vericut96:v1",
    "vericut-e": "virtu-vericut-e:latest",
}


def default_deploy_tag(track: str) -> str:
    return _DEFAULT_DEPLOY_TAGS.get(track, "virtu-master-fixed:latest")


def resolve_track_list(track: str, tracks_csv: Optional[str]) -> List[str]:
    if not tracks_csv:
        if track not in TRACKS:
            raise SystemExit(f"[FATAL] 未知产线: {track}")
        return [track]
    out: List[str] = []
    for raw in str(tracks_csv).split(","):
        t = raw.strip()
        if not t:
            continue
        if t not in TRACKS:
            raise SystemExit(f"[FATAL] --tracks 包含未知产线: {t!r} (可选: {', '.join(TRACKS.keys())})")
        if t not in out:
            out.append(t)
    if not out:
        raise SystemExit("[FATAL] --tracks 不能为空")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Virtu 上线马上开训·统一调度与双阶看门狗")
    parser.add_argument("--track", choices=tuple(TRACKS.keys()), default="master-8b", help="单条训练产线")
    parser.add_argument("--tracks", default=None, help="多产线顺序串联，逗号分隔 (如 vericut96-v2,vericut-e,six-software)")
    parser.add_argument("--ssh-cmd", default=None, help="直接粘贴云端 SSH 登录串 (如 'ssh -p 40526 root@host')")
    parser.add_argument("--host", default=None, help="云端 SSH 主机 (或 DAMODEL_HOST)")
    parser.add_argument("--port", type=int, default=None, help="云端 SSH 端口 (或 DAMODEL_PORT)")
    parser.add_argument("--user", default=None, help="SSH 用户名 (默认 root)")
    parser.add_argument("--password", default=None, help="SSH 密码 (或 DAMODEL_PASS)")
    parser.add_argument("--creds-file", default=None, help="可选凭据 JSON 文件")
    parser.add_argument("--remote-dir", default=None, help="覆盖远端工作目录")
    parser.add_argument("--dataset", default=None, help="覆盖主训语料路径 (仅单产线)")
    parser.add_argument("--base", default=None, help="云端/本地基座目录")
    parser.add_argument("--gpu-id", default=None, help="指定云端物理 GPU 卡号 (如 0 或 1；不传则由产线脚本默认)")
    parser.add_argument("--max-hours", type=float, default=1.5)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=1.5e-4)
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--repack", action="store_true", help="强制重打云端归档包")
    parser.add_argument("--skip-selftest", action="store_true", help="跳过预打包前本地自检（不推荐）")
    parser.add_argument("--prepare-only", action="store_true", help="仅运行本地预检与预打包，不连接 SSH")
    parser.add_argument("--wait-online-seconds", type=float, default=300.0, help="等云端实例上线最大秒数 (0=立即失败, -1=无限等待直到开机)")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="TCP 上线轮询间隔(秒)")
    parser.add_argument("--startup-timeout", type=float, default=120.0, help="Watchdog-1 启动双证超时(秒)")
    parser.add_argument("--follow", "--wait-finish", dest="follow", action="store_true", help="持续看门狗直到 COMPLETED")
    parser.add_argument("--stall-seconds", type=float, default=420.0, help="无步进+低GPU利用卡死阈值(秒)")
    parser.add_argument("--auto-deploy", action="store_true", help="完成后自动拉取并融合部署")
    parser.add_argument(
        "--deploy-tag",
        default=None,
        help="自动融合部署 Ollama tag (six-software 默认 virtu-six-software:v1，vericut96 默认 virtu-vericut96:v1，vericut96-v2 默认 virtu-vericut96:v2，vericut-e 默认 virtu-vericut-e:latest，其余默认 virtu-master-fixed:latest)",
    )
    parser.add_argument("--selftest", action="store_true", help="运行零 SSH 离线逻辑自检")
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()

    track_list = resolve_track_list(args.track, args.tracks)
    if len(track_list) > 1 and args.dataset:
        raise SystemExit("[FATAL] --tracks 多产线串联不支持同时传单个 --dataset")

    packed_tracks: Dict[str, Dict[str, Any]] = {}
    for trk in track_list:
        if not args.skip_selftest:
            ran = run_track_selftests(trk)
            print(f"[Preflight] track={trk} 离线自检通过 ({len(ran)} 项): {ran}")
        packed_tracks[trk] = prepare_track_bundle(trk, repack=args.repack, dataset_arg=args.dataset)

    if args.prepare_only:
        print("\n" + "=" * 72)
        for trk in track_list:
            pack_info = packed_tracks[trk]
            print(f"[READY] 产线 {trk} ({TRACKS[trk]['description']}) 已零等待就绪！")
            print(f"  * 归档包 : {pack_info['bundle_path']} ({pack_info['size_mb']:.2f} MB)")
            print(f"  * SHA256 : {pack_info['sha256']}")
            print(f"  * 伴随文件: {pack_info['bundle_path']}.sha256")
        print("  * 实例一上线(或开机等待中)，直接执行:")
        if len(track_list) > 1:
            tracks_flag = f"--tracks {','.join(track_list)}"
        else:
            tracks_flag = f"--track {track_list[0]}"
        print(
            f"    .venv\\Scripts\\python.exe cloud_train_pack\\start_train_now.py "
            f"{tracks_flag} --ssh-cmd \"ssh -p <PORT> root@<HOST>\" --wait-online-seconds -1 --follow --auto-deploy"
        )
        print("=" * 72)
        return 0

    creds = resolve_cloud_credentials(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        ssh_cmd=args.ssh_cmd,
        creds_file=args.creds_file,
    )
    if not creds["host"]:
        raise SystemExit("[FATAL] 缺少云端主机：请传 --ssh-cmd 或 --host，或设置 DAMODEL_HOST / DAMODEL_SSH_CMD，或用 --prepare-only 先预打包。")
    if not creds["password"]:
        try:
            import getpass
            creds["password"] = getpass.getpass("请输入云端实例 SSH 密码 (或设置 DAMODEL_PASS): ")
        except Exception as exc:
            raise SystemExit(f"[FATAL] 缺少 SSH 密码: {exc}")

    client, _ = wait_for_instance_online(
        creds["host"],
        creds["port"],
        creds["user"],
        creds["password"],
        wait_online_seconds=args.wait_online_seconds,
        poll_interval=args.poll_interval,
    )
    try:
        total = len(track_list)
        for idx, trk in enumerate(track_list, 1):
            pack_info = packed_tracks[trk]
            rdir_override = (
                f"{args.remote_dir.rstrip('/')}/{trk}"
                if (args.remote_dir and total > 1)
                else args.remote_dir
            )
            tag = args.deploy_tag if (args.deploy_tag and total == 1) else default_deploy_tag(trk)
            print(f"\n[Dispatch {idx}/{total}] 启动产线 track={trk} ...")
            launch_kwargs: Dict[str, Any] = {
                "remote_dir": rdir_override,
                "max_hours": args.max_hours,
                "epochs": args.epochs,
                "lr": args.lr,
                "qlora": args.qlora,
                "skip_smoke": args.skip_smoke,
                "base_arg": args.base,
            }
            verify_kwargs: Dict[str, Any] = {"timeout_s": args.startup_timeout}
            watch_kwargs: Dict[str, Any] = {"max_stall_seconds": args.stall_seconds}
            if args.gpu_id is not None:
                launch_kwargs["gpu_id"] = args.gpu_id
                verify_kwargs["gpu_id"] = args.gpu_id
                watch_kwargs["gpu_id"] = args.gpu_id
            launch_info = upload_and_launch_remote(
                client,
                trk,
                pack_info["bundle_path"],
                **launch_kwargs,
            )
            rdir = launch_info["remote_dir"]
            verify_training_started(client, trk, rdir, **verify_kwargs)

            must_wait = args.follow or (idx < total)
            if must_wait:
                watch_training_health(client, trk, rdir, **watch_kwargs)
                if args.auto_deploy or args.follow:
                    pull_and_optional_deploy(
                        client,
                        trk,
                        rdir,
                        auto_deploy=args.auto_deploy,
                        deploy_tag=tag,
                        base_dir=args.base,
                    )
            else:
                log_path = f"{rdir}/{TRACKS[trk]['log_rel']}"
                print(f"\n[OK] 云端已确认开训 ({trk})！查看实时日志: tail -f {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
