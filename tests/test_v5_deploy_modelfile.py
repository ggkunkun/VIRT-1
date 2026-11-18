#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反证测试：v5 部署 Modelfile 必须与 v3/v4 已验证件同构（2026-11-16）。

缺陷复现：run_full_repair_v5.py 旧实现写裸 `FROM <gguf>`，丢 SYSTEM/TEMPLATE/
PARAMETER —— 与基线不同构，验收探针必然失真。修复后 build_modelfile 复用
v4 已验证 Modelfile 只换 FROM；参照件缺失必须 fail-closed，不得退回裸件。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "run_full_repair_v5", ROOT / "scripts" / "run_full_repair_v5.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

REF = ROOT / "checkpoints" / "_deploy_six_v4_local" / "virtu-six-software_v4.Modelfile"


def test_modelfile_keeps_verified_system_template_parameters():
    out = M.build_modelfile(ROOT / "checkpoints" / "_deploy_six_v5_repair" / "x.q4_0.gguf")
    ref = REF.read_text(encoding="utf-8")
    assert out.startswith("FROM "), out[:80]
    assert "x.q4_0.gguf" in out.splitlines()[0]
    # 除 FROM 外逐行同构
    assert out.splitlines()[1:] == ref.splitlines()[1:]
    assert "SYSTEM" in out and "TEMPLATE" in out
    assert 'PARAMETER stop "<|im_end|>"' in out
    assert "num_ctx 8192" in out


def test_bare_from_is_not_produced():
    out = M.build_modelfile(Path("D:/tmp/fake.gguf"))
    assert len(out.splitlines()) > 1, "bare FROM modelfile must not be produced"


def test_missing_reference_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "ROOT", tmp_path)
    try:
        M.build_modelfile(tmp_path / "fake.gguf")
    except FileNotFoundError:
        return
    raise AssertionError("missing verified reference must raise, not fall back to bare FROM")