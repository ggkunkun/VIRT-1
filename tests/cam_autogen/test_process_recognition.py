"""M1 加工工艺识别模块单元测试：数据集精度 >=95%、低置信度异常处理与 REST API。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cam_autogen.contracts import ProcessType, WorkpieceSpec
from cam_autogen.process_recognition.api import app
from cam_autogen.process_recognition.dataset import build_benchmark_dataset
from cam_autogen.process_recognition.engine import (
    LowConfidenceError, evaluate, handle_low_confidence, recognize, recognize_dict,
)


def test_benchmark_accuracy_exceeds_95_percent_and_flags_ambiguous():
    ds = build_benchmark_dataset()
    report = evaluate(ds, threshold=0.90)
    assert report["n_labeled"] == 60
    assert report["accuracy"] >= 0.95, f"准确率不足95%: {report}"
    assert report["n_ambiguous"] == 8
    assert report["ambiguous_flag_rate"] == 1.0
    assert evaluate([])["accuracy"] is None


def test_low_confidence_exception_handling_halt_and_fallback():
    ds = build_benchmark_dataset()
    amb = [d["workpiece"] for d in ds if d["label"] == "AMBIGUOUS"]

    # 对置信度 < 0.90 的模糊样本：halt 必须抛 LowConfidenceError
    wp_thin = WorkpieceSpec.model_validate(amb[1])
    res_thin = recognize(wp_thin, threshold=0.90)
    assert res_thin.low_confidence is True
    assert res_thin.confidence < 0.90
    with pytest.raises(LowConfidenceError) as exc_info:
        handle_low_confidence(res_thin, policy="halt")
    assert exc_info.value.result.exception["action"] == "HALT"

    # 三向模糊样本即使 conservative_fallback 也必须阻断
    wp_block_cyl = WorkpieceSpec.model_validate(amb[2])  # prismatic + od_cylinder
    res_bc = recognize(wp_block_cyl, threshold=0.90)
    assert res_bc.low_confidence is True
    with pytest.raises(LowConfidenceError):
        handle_low_confidence(res_bc, policy="conservative_fallback")

    # 前两名含 TURN_MILL 且合并概率 >=0.97（amb[3]: od_cylinder + chamfer_edge），降级为 TURN_MILL 超集
    wp_sup = WorkpieceSpec.model_validate(amb[3])
    res_sup = recognize(wp_sup, threshold=0.90)
    assert res_sup.low_confidence is True
    resolved = handle_low_confidence(res_sup, policy="conservative_fallback")
    assert resolved.process_type == ProcessType.TURN_MILL
    assert resolved.exception["action"] == "FALLBACK_TO_SUPERSET_TURN_MILL"
    assert resolved.exception["resolved"] is True

    # 正常样本不受影响
    clear = WorkpieceSpec.model_validate(ds[0]["workpiece"])
    r_ok = recognize(clear)
    assert handle_low_confidence(r_ok, policy="halt").process_type == ProcessType.MILLING


def test_process_warnings_and_dict_helper():
    payload = {
        "part_id": "WARN-01",
        "material": {"name": "Hardened", "hardness_hb": 520},
        "envelope": {"type": "cylindrical", "diameter": 20, "length": 100},
        "stock": {"type": "bar", "diameter": 24, "length": 130},
        "features": [
            {"id": "F1", "type": "od_cylinder", "params": {"diameter": 18, "z_start": 0, "z_end": -80}, "ra_um": 0.2}
        ],
    }
    res = recognize_dict(payload)
    assert res["process_type"] == "TURNING"
    assert any("L/D" in w for w in res["warnings"])
    assert any("520" in w and "HB" in w for w in res["warnings"])
    assert any("Ra<0.4" in w for w in res["warnings"])


def test_m1_rest_api():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    info = client.get("/v1/info").json()
    assert info["module"] == "process_recognition"

    ds = build_benchmark_dataset()
    r1 = client.post("/v1/recognize", json={"workpiece": ds[0]["workpiece"]})
    assert r1.status_code == 200 and r1.json()["process_type"] == "MILLING"

    amb = [d for d in ds if d["label"] == "AMBIGUOUS"]
    r_halt = client.post("/v1/recognize", json={"workpiece": amb[0]["workpiece"], "low_confidence_policy": "halt"})
    assert r_halt.status_code == 409 and r_halt.json()["error"] == "LOW_CONFIDENCE"

    r_eval = client.post("/v1/evaluate", json={"dataset": ds[:10]})
    assert r_eval.status_code == 200 and r_eval.json()["accuracy"] >= 0.9
