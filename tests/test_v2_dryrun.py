# -*- coding: utf-8 -*-
"""V2 空运行阶段契约测试（包络实测、C 索引收敛、证据门坏样本必红）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import config  # noqa: E402

NC = ROOT / "production" / "nc" / "prod_5ax_fanuc_0imf"


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_v2", ROOT / "scripts" / "run_v2_dryrun.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_envelopes_measured_and_within_travel():
    v2 = _load()
    p = config.load()
    m = p.machines["prod_5ax_fanuc_0imf"]
    env1 = v2.envelope((NC / "AE-CI-258_OP1.nc").read_text(encoding="utf-8"), "fanuc")
    env2 = v2.envelope((NC / "AE-CI-258_OP2.nc").read_text(encoding="utf-8"), "fanuc")
    assert not env1["errors"] and not env2["errors"]
    # OP1 无 C 索引：Y 全跨度 ±138.5
    assert env1["y"][1] - env1["y"][0] >= 250
    # OP2 用 C 把流道转到主轴正前方：机床 Y 跨度显著收敛
    assert env2["y"][1] - env2["y"][0] <= 80
    for env in (env1, env2):
        for ax in ("x", "y", "z"):
            assert m.travel_mm[ax][0] <= env[ax][0]
            assert env[ax][1] <= m.travel_mm[ax][1]


def test_dryrun_gate_bad_samples():
    v2 = _load()
    good = {"程序": "P1", "报警数": "0", "超程数": "0", "最大主轴负载(%)": "60",
            "急停停止时间(s)": "0.3", "门锁测试(OK/NG)": "OK"}
    assert v2.evaluate_rows([good])["gate"] == "PASS"
    assert v2.evaluate_rows([{**good, "最大主轴负载(%)": "85"}])["gate"] == "FAIL"
    assert v2.evaluate_rows([{**good, "报警数": "2"}])["gate"] == "FAIL"
    assert v2.evaluate_rows([{**good, "急停停止时间(s)": "0.8"}])["gate"] == "FAIL"
    assert v2.evaluate_rows([{**good, "门锁测试(OK/NG)": "NG"}])["gate"] == "FAIL"
    assert v2.evaluate_rows([{"程序": "P1"}])["gate"] == "PENDING"
    assert v2.evaluate_rows([])["gate"] == "PENDING"
